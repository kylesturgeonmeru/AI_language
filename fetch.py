"""Fetch: download candidate PDFs from CourtListener storage to data/raw/.

Reads data/candidates.csv, selects in-window documents for the requested
tracks, and downloads each available one. Documents not in RECAP go on
data/manual_pull_list.csv. Every PDF is validated after download; bad
files are logged as failures and not kept.

Usage: python fetch.py --tracks B B_related [--ids-file data/fetch_list_b.csv] [--dry-run]
"""
import argparse
import csv
import re
import io
from pathlib import Path

import pymupdf

from common import (CL_STORAGE, DATA, Session, SourceStopped, atomic_write_bytes, atomic_write_text,
                    cl_usage, log_request, read_log, require_env, sha256_bytes)

DOWNLOAD_CAP = 400  # approved at Checkpoint 1, 10/09/2026
RAW = DATA / "raw"
MANIFEST = DATA / "fetch_manifest.csv"
MANUAL = DATA / "manual_pull_list.csv"
MANIFEST_FIELDS = ["recap_doc_id", "track", "court_id", "case_name", "docket_number", "document_number",
                   "attachment_number", "description", "url", "path", "status", "error", "sha256",
                   "bytes", "pages", "expected_pages"]
MANUAL_FIELDS = ["track", "court_id", "case_name", "docket_number", "document_number", "attachment_number",
                 "description", "doc_url", "claims_agent_docket_url", "reason"]


def read_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    atomic_write_text(path, buf.getvalue())


def validate_pdf(data):
    """Return (pages, error). error is None for a usable PDF."""
    if not data.startswith(b"%PDF"):
        return 0, "not a PDF (missing %PDF header)"
    if b"%%EOF" not in data[-2048:]:
        return 0, "truncated (no %%EOF trailer)"
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.page_count == 0:
                return 0, "PDF has no pages"
            doc[doc.page_count - 1].get_text()  # forces a parse of the last page
            return doc.page_count, None
    except Exception as e:  # pymupdf raises several types for damaged files
        return 0, f"unreadable PDF: {type(e).__name__}"


def select(cands, tracks):
    rows = [c for c in cands if c["in_window"] == "True" and set(c["track"].split("|")) & set(tracks)]
    seen, out = set(), []
    for c in rows:
        if c["recap_doc_id"] not in seen:
            seen.add(c["recap_doc_id"])
            out.append(c)
    return out


def user_daily_used(sess):
    for row in cl_usage(sess.http):
        if row["window_seconds"] >= 86400:
            return row["used"]
    return None


RANK_MANIFEST = DATA / "ranking_manifest.csv"
RANK_FIELDS = ["recap_doc_id", "docket_id", "document_number", "description", "url", "path", "status",
               "error", "sha256", "bytes", "pages", "expected_pages"]


def fetch_ranking(dry_run):
    """First-day declarations used only to rank Track A cases by funded debt.

    Kyle exempted these from DOWNLOAD_CAP on 10/09/2026; they have their own
    manifest so they never count toward it.
    """
    rows = {r["recap_doc_id"]: r for r in read_csv(DATA / "track_a_funded_debt.csv")}
    manifest = {m["recap_doc_id"]: m for m in read_csv(RANK_MANIFEST)}
    pending = [r for k, r in rows.items() if r["is_available"] == "True" and r["filepath_local"]
               and not (k in manifest and manifest[k]["status"] == "ok" and Path(manifest[k]["path"]).exists())]
    print(f"{len(rows)} ranking documents; {len(pending)} to fetch")
    if dry_run:
        return
    sess = Session()
    for i, r in enumerate(pending):
        url = CL_STORAGE + r["filepath_local"]
        path = RAW / "ranking" / r["docket_id"] / f"{r['recap_doc_id']}.pdf"
        entry = {k: r.get(k, "") for k in RANK_FIELDS}
        entry.update(url=url, path=str(path.relative_to(DATA.parent)), expected_pages=r["page_count"])
        try:
            data = sess.get(url, "cl_storage", purpose=f"ranking {r['recap_doc_id']}")
        except SourceStopped as e:
            print(f"Stopped: {e}")
            break
        except Exception as e:
            entry.update(status="failed", error=str(e)[:200])
            manifest[r["recap_doc_id"]] = entry
            continue
        pages, err = validate_pdf(data)
        entry.update(sha256=sha256_bytes(data), bytes=len(data), pages=pages, status="failed" if err else "ok",
                     error=err or "")
        if err:
            log_request(url, 200, body=data, error=f"validation: {err}", source="cl_storage",
                        purpose=f"validate ranking {r['recap_doc_id']}")
        else:
            atomic_write_bytes(DATA.parent / entry["path"], data)
        manifest[r["recap_doc_id"]] = entry
        print(f"  [{i + 1}/{len(pending)}] {entry['status']} docket {r['docket_id']} ({pages} pp) {err or ''}")
    write_csv(RANK_MANIFEST, sorted(manifest.values(), key=lambda m: m["recap_doc_id"]), RANK_FIELDS)
    ok = sum(1 for m in manifest.values() if m["status"] == "ok")
    print(f"Ranking manifest: {ok} ok, {len(manifest) - ok} failed.")


# Claims agent sites (CLAUDE.md source rule 3, changed 10/11/2026): polite,
# logged downloads only where terms and robots.txt allow automated access.
AGENT_HOSTS = {
    "kroll": "https://restructuring.ra.kroll.com",
    "stretto": "https://cases.stretto.com",
    "epiq": "https://dm.epiq11.com",
    "epiq_docs": "https://document.epiq11.com",
    "omni": "https://omniagentsolutions.com",
    "verita": "https://www.veritaglobal.net",
}
AGENTS = DATA / "agents"
CHROMIUM = "/opt/pw-browsers/chromium"  # preinstalled; do not run "playwright install"


def agent_preflight():
    """Fetch and save each agent's robots.txt (logged) for review before any download."""
    sess = Session()
    for name, host in AGENT_HOSTS.items():
        url = host + "/robots.txt"
        try:
            body = sess.get(url, "agent_" + name, purpose=f"preflight robots.txt {name}")
            atomic_write_bytes(AGENTS / "robots" / f"{name}.txt", body)
            print(f"{name}: robots.txt {len(body)} bytes")
        except Exception as e:
            print(f"{name}: robots.txt not retrieved ({str(e)[:120]})")


def agent_page(agent, url):
    """GET one claims agent page with plain HTTP (logged, paced) and save it for review."""
    from urllib.parse import urlparse
    sess = Session()
    body = sess.get(url, "agent_" + agent, purpose="agent page")
    name = re.sub(r"[^A-Za-z0-9]+", "_", urlparse(url).path + "_" + urlparse(url).query).strip("_") or "index"
    out = AGENTS / "pages" / agent / f"{name}.html"
    atomic_write_bytes(out, body)
    print(f"{url}: {len(body)} bytes -> {out}")
    return out


def agent_render(agent, url):
    """Render one claims agent page in headless Chromium (logged, paced) and save it.

    For sites that build pages with JavaScript (Epiq; approved by Kyle 10/11/2026).
    No logins and no CAPTCHA handling: a challenge page is saved as-is and is a block.
    """
    import os
    import time
    from urllib.parse import urlparse
    from playwright.sync_api import sync_playwright
    time.sleep(3.0)
    name = re.sub(r"[^A-Za-z0-9]+", "_", urlparse(url).path).strip("_") or "index"
    out = AGENTS / "pages" / agent / name
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, proxy={"server": os.environ["HTTPS_PROXY"]})
        page = browser.new_page(user_agent=os.environ.get("SEC_USER_AGENT", "MERU research"))
        page.on("response", lambda r: seen.append(f"{r.status} {r.url}"))
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=90000)
            html = page.content().encode("utf-8")
            log_request(url, resp.status if resp else None, body=html, source="agent_" + agent,
                        purpose="render page")
            atomic_write_bytes(out.with_suffix(".html"), html)
            page.screenshot(path=str(out.with_suffix(".png")), full_page=False)
        except Exception as e:
            log_request(url, None, error=type(e).__name__, source="agent_" + agent, purpose="render page")
            raise
        finally:
            browser.close()
    atomic_write_text(out.with_suffix(".responses.txt"), "\n".join(seen) + "\n")
    print(f"rendered {url}: {len(html)} bytes, {len(seen)} responses -> {out}")
    return out


def epiq_docket_search(project, docket_numbers, debug=False):
    """Use Epiq's public docket page like a visitor: clear the case filter, enter
    docket numbers, and read the result cards (docket number, case, text, links).

    Approved by Kyle 10/11/2026. Paced, logged; no API calls of our own.
    """
    import os
    import time
    from playwright.sync_api import sync_playwright
    url = f"https://dm.epiq11.com/case/{project}/dockets"
    shots = AGENTS / "pages" / "epiq" / f"{project}_search"
    shots.mkdir(parents=True, exist_ok=True)
    time.sleep(3.0)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, proxy={"server": os.environ["HTTPS_PROXY"]})
        page = browser.new_page(user_agent=os.environ.get("SEC_USER_AGENT", "MERU research"),
                                viewport={"width": 1280, "height": 1600})
        resp = page.goto(url, wait_until="networkidle", timeout=90000)
        log_request(url, resp.status if resp else None, source="agent_epiq", purpose="docket page")
        if debug:
            page.screenshot(path=str(shots / "1_loaded.png"), full_page=True)
        # Remove every preset case-number chip so all debtors' dockets are searched.
        for _ in range(5):
            chip = page.locator("button.epiq-tag-remove >> visible=true")
            if chip.count() == 0:
                break
            chip.first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(3.0)
        page.locator("#caseDocketNumberFilter >> visible=true").fill(",".join(str(n) for n in docket_numbers))
        page.locator("#caseDocketFilterButton >> visible=true").click()
        page.wait_for_load_state("networkidle")
        time.sleep(3.0)
        if debug:
            page.screenshot(path=str(shots / "2_searched.png"), full_page=True)
        html = page.content()
        log_request(url + "#docket-search", 200, body=html.encode("utf-8"), source="agent_epiq",
                    purpose=f"docket search {docket_numbers}")
        atomic_write_text(shots / "results.html", html)
        browser.close()
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", nargs="+", default=[])
    ap.add_argument("--ranking", action="store_true",
                    help="fetch first-day declarations for the Track A ranking (exempt from the cap)")
    ap.add_argument("--ids-file", help="CSV with a recap_doc_id column; fetch only these (curated list)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--agent-preflight", action="store_true", help="save claims agents' robots.txt for review")
    ap.add_argument("--agent-page", nargs=2, metavar=("AGENT", "URL"), help="save one claims agent page (plain HTTP)")
    ap.add_argument("--agent-render", nargs=2, metavar=("AGENT", "URL"), help="render one claims agent page (headless)")
    ap.add_argument("--epiq-search", nargs=2, metavar=("PROJECT", "DOCKETS"),
                    help="Epiq docket search by comma-separated docket numbers (debug screenshots)")
    args = ap.parse_args()
    if args.agent_preflight:
        return agent_preflight()
    if args.agent_page:
        return agent_page(*args.agent_page)
    if args.agent_render:
        return agent_render(*args.agent_render)
    if args.epiq_search:
        return epiq_docket_search(args.epiq_search[0], args.epiq_search[1].split(","), debug=True)
    require_env("COURTLISTENER_TOKEN")
    if args.ranking:
        return fetch_ranking(args.dry_run)
    if not args.tracks:
        ap.error("--tracks is required unless --ranking is given")

    todo = select(read_csv(DATA / "candidates.csv"), args.tracks)
    if args.ids_file:
        ids = {r["recap_doc_id"] for r in read_csv(args.ids_file)}
        todo = [c for c in todo if c["recap_doc_id"] in ids]
    manifest = {m["recap_doc_id"]: m for m in read_csv(MANIFEST)}
    manual = {(m["docket_number"], m["document_number"], m["attachment_number"]): m for m in read_csv(MANUAL)}

    available = [c for c in todo if c["is_available"] == "True" and c["filepath_local"]]
    for c in todo:
        if c not in available:
            manual[(c["docket_number"], c["document_number"], c["attachment_number"])] = dict(
                c, claims_agent_docket_url="", reason="not in RECAP")
    done = {k for k, m in manifest.items() if m["status"] == "ok" and Path(m["path"]).exists()}
    pending = [c for c in available if c["recap_doc_id"] not in done]
    room = DOWNLOAD_CAP - len(done)
    print(f"{len(todo)} selected; {len(available)} in RECAP; {len(done)} already fetched; "
          f"{len(pending)} to fetch; cap room {room}; {len(todo) - len(available)} to manual pull list")
    if len(pending) > room:
        print(f"Cap reached: fetching only {room} of {len(pending)}.")
        pending = pending[:max(room, 0)]
    if args.dry_run:
        return

    sess = Session()
    probe_before = user_daily_used(sess) if pending else None
    for i, c in enumerate(pending):
        url = CL_STORAGE + c["filepath_local"]
        path = RAW / c["court_id"] / c["docket_id"] / f"{c['recap_doc_id']}.pdf"
        entry = {k: c.get(k, "") for k in MANIFEST_FIELDS}
        entry.update(url=url, path=str(path.relative_to(DATA.parent)), expected_pages=c["page_count"],
                     track=c["track"])
        try:
            data = sess.get(url, "cl_storage", purpose=f"fetch {c['recap_doc_id']}")
        except SourceStopped as e:
            print(f"Stopped: {e}")
            break
        except Exception as e:
            entry.update(status="failed", error=str(e)[:200])
            manifest[c["recap_doc_id"]] = entry
            continue
        pages, err = validate_pdf(data)
        entry.update(sha256=sha256_bytes(data), bytes=len(data), pages=pages)
        if err:
            # A later failure row makes this URL count as not succeeded (see common.succeeded_urls).
            log_request(url, 200, body=data, error=f"validation: {err}", source="cl_storage",
                        purpose=f"validate {c['recap_doc_id']}")
            entry.update(status="failed", error=err)
        else:
            atomic_write_bytes(DATA.parent / entry["path"], data)
            entry.update(status="ok", error="")
        manifest[c["recap_doc_id"]] = entry
        print(f"  [{i + 1}/{len(pending)}] {entry['status']} {c['case_name'][:40]} "
              f"Dkt {c['document_number']}-{c['attachment_number'] or 0} ({pages} pp) {err or ''}")

        if i == 0 and probe_before is not None:
            after = user_daily_used(sess)
            if after is not None and after > probe_before:
                print("Storage downloads count against the CourtListener API budget. "
                      "Stopping so the budget can be re-planned.")
                break
            print("Storage downloads do not count against the API budget.")

    write_csv(MANIFEST, sorted(manifest.values(), key=lambda m: (m["case_name"], m["recap_doc_id"])),
              MANIFEST_FIELDS)
    write_csv(MANUAL, list(manual.values()), MANUAL_FIELDS)
    ok = sum(1 for m in manifest.values() if m["status"] == "ok")
    print(f"Manifest: {ok} ok, {len(manifest) - ok} failed. Manual pull list: {len(manual)}.")


if __name__ == "__main__":
    main()

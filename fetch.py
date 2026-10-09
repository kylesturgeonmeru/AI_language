"""Fetch: download candidate PDFs from CourtListener storage to data/raw/.

Reads data/candidates.csv, selects in-window documents for the requested
tracks, and downloads each available one. Documents not in RECAP go on
data/manual_pull_list.csv. Every PDF is validated after download; bad
files are logged as failures and not kept.

Usage: python fetch.py --tracks B B_related [--ids-file data/fetch_list_b.csv] [--dry-run]
"""
import argparse
import csv
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", nargs="+", default=[])
    ap.add_argument("--ranking", action="store_true",
                    help="fetch first-day declarations for the Track A ranking (exempt from the cap)")
    ap.add_argument("--ids-file", help="CSV with a recap_doc_id column; fetch only these (curated list)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
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

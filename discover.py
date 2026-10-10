"""Discovery: find candidate filings and write data/candidates.csv.

Track B: full-text search of RECAP for each AI term, limited to docket
entries whose description reads as a retention filing.
Track A (phase 1): the universe of chapter 11 cases in scope that have a
claims agent retention in RECAP, from which the census cases get picked
at Checkpoint 1. Phase 2 (retention filings per census case) runs only
after Kyle approves the "largest cases" measure.
SEC: EDGAR full-text search for engagement letters filed as exhibits.

Every page is cached in data/discovery/cache/, so reruns spend no API
calls on pages already fetched. Usage: python discover.py [--max-pages N]
"""
import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date

from common import (CL_BASE, COURTS, DATA, WINDOW_START, Session, SourceStopped,
                    atomic_write_json, atomic_write_text, require_env)

CACHE = DATA / "discovery" / "cache"

AI_TERMS = [
    "artificial intelligence", "generative AI", "large language model", "AI Tools",
    "AI-assisted", "machine learning", "ChatGPT", "Copilot",
]
# Docket-entry description filter for retention filings. Applications,
# supplemental declarations, orders, and UST objections all name the
# retention in the entry text ("Application to Employ/Retain ...").
RETENTION_DESC = ('employ OR retain OR retention OR "ordinary course" OR '
                  '"claims agent" OR "noticing agent" OR "engagement letter"')
CLAIMS_AGENT_DESC = '"claims and noticing agent" OR "claims agent" OR "noticing agent" OR "156(c)"'

SEC_TERMS = AI_TERMS
SEC_FTS = "https://efts.sec.gov/LATEST/search-index"


# ---------------------------------------------------------------- fetching

def cache_path(url):
    return CACHE / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")


def cached_get(sess, url, source, params=None, purpose=None):
    from requests import Request
    full = Request("GET", url, params=params).prepare().url
    path = cache_path(full)
    if path.exists():
        return json.loads(path.read_text())["response"]
    body = sess.get(full, source, purpose=purpose)
    data = json.loads(body)
    atomic_write_json(path, {"url": full, "response": data})
    return data


def cl_search(sess, params, purpose, max_pages):
    """Yield result rows across pages of /search/, following cursors."""
    url, p = CL_BASE + "search/", dict(params)
    for page in range(max_pages):
        data = cached_get(sess, url, "courtlistener", params=p, purpose=f"{purpose} p{page + 1}")
        yield from data.get("results", [])
        if not data.get("next"):
            return
        url, p = data["next"], None
    print(f"  [cap] {purpose}: stopped at {max_pages} pages; more results exist")


def base_params(search_type, q, description=None):
    p = {"type": search_type, "q": q, "court": " ".join(COURTS),
         "filed_after": "01/01/2025", "highlight": "on"}
    if description:
        p["description"] = description
    return p


# ---------------------------------------------------------------- tagging

def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"</?mark>", "", s or "")).strip()


ROLE_RULES = [
    ("claims_agent", r"claims and noticing|claims agent|noticing agent|156\(c\)|administrative advisor"),
    ("ocp", r"ordinary course"),
    ("cro", r"chief restructuring|\bcro\b|interim management|chief transformation"),
    ("ib", r"investment bank|placement agent"),
    ("fa", r"financial advis"),
    ("counsel", r"counsel|attorneys? for|as special|as conflicts|as local"),
]
FILING_RULES = [
    ("ust_objection", r"objection.*(united states trustee|u\.s\. trustee)|(united states trustee|u\.s\. trustee).*objection"),
    ("order", r"^\s*order\b|order (authorizing|approving|granting|signed)"),
    ("supplemental_declaration", r"supplemental (declaration|affidavit)"),
    ("rule_2014_declaration", r"^(affidavit|declaration)"),
    ("retention_application", r"application|motion"),
    ("notice", r"notice"),
]
FIRM_RE = re.compile(
    r"(?:employ(?:ment)?(?:/retain)?|retain|retention(?: and employment)?)\s+(?:of\s+)?(.+?)\s+as\s+", re.I)


def guess(rules, text, default="other"):
    t = text.lower()
    for label, pat in rules:
        if re.search(pat, t):
            return label
    return default


def retained_by(text):
    t = text.lower()
    if "committee" in t:
        return "committee"
    if "debtor" in t:
        return "debtor"
    return "unknown"


def firm_guess(text):
    m = FIRM_RE.search(text)
    return m.group(1).strip(" ,.")[:80] if m else ""


# ---------------------------------------------------------------- tracks

def docket_row(r):
    return {
        "docket_id": r["docket_id"], "court_id": r.get("court_id"),
        "case_name": clean(r.get("caseName")), "docket_number": r.get("docketNumber"),
        "petition_date": r.get("dateFiled"), "chapter": r.get("chapter"),
        "docket_url": "https://www.courtlistener.com" + (r.get("docket_absolute_url") or ""),
    }


def doc_row(d, track, query):
    desc = clean(d.get("description"))
    return {
        "track": track, "query": query, "docket_id": d.get("docket_id"),
        "recap_doc_id": d.get("id"), "entry_date": d.get("entry_date_filed"),
        "document_number": d.get("document_number"), "attachment_number": d.get("attachment_number"),
        "description": desc, "short_description": clean(d.get("short_description")),
        "is_available": d.get("is_available"), "page_count": d.get("page_count"),
        "filepath_local": d.get("filepath_local") or "",
        "doc_url": "https://www.courtlistener.com" + (d.get("absolute_url") or ""),
        "role_guess": guess(ROLE_RULES, desc), "filing_type_guess": guess(FILING_RULES, desc),
        "retained_by_guess": retained_by(desc), "firm_guess": firm_guess(desc),
        "snippet": clean(d.get("snippet"))[:500],
    }


def track_b(sess, dockets, docs, max_pages):
    for term in AI_TERMS:
        q = f'"{term}" AND chapter:11'
        print(f"Track B: {term}")
        for r in cl_search(sess, base_params("r", q, RETENTION_DESC), f"B dockets {term}", max_pages):
            dockets[r["docket_id"]] = docket_row(r)
        for d in cl_search(sess, base_params("rd", q, RETENTION_DESC), f"B docs {term}", max_pages):
            docs.append(doc_row(d, "B", term))


def track_a_universe(sess, dockets, docs, max_pages):
    print("Track A phase 1: chapter 11 cases with a claims agent retention")
    universe = set()
    for r in cl_search(sess, base_params("r", "chapter:11", CLAIMS_AGENT_DESC), "A universe", max_pages):
        dockets[r["docket_id"]] = docket_row(r)
        universe.add(r["docket_id"])
        for d in r.get("recap_documents", []):
            d = dict(d, docket_id=r["docket_id"])
            docs.append(doc_row(d, "A_universe", "claims agent retention"))
    return universe


def track_b_related(sess, dockets, docs, max_pages):
    """For each in-window Track B hit, find the rest of its docket entry and the entered order."""
    hits = {}
    for d in docs:
        if d["track"] == "B" and in_window(dockets.get(d["docket_id"], {})) is True:
            hits.setdefault((d["docket_id"], d["document_number"]), d)
    for (docket_id, doc_num), d in sorted(hits.items()):
        print(f"Track B related: docket {docket_id}, entry {doc_num}")
        q = f"docket_id:{docket_id} AND document_number:{doc_num}"
        for r in cl_search(sess, {"type": "rd", "q": q}, f"B entry {docket_id}/{doc_num}", max_pages):
            docs.append(doc_row(dict(r, docket_id=docket_id), "B_related", f"entry {doc_num}"))
        firm = d["firm_guess"].split(",")[0].split()[0] if d["firm_guess"] else ""
        desc = "order AND (retain OR employ OR retention OR appoint)" + (f' AND "{firm}"' if firm else "")
        for r in cl_search(sess, {"type": "rd", "q": f"docket_id:{docket_id}", "description": desc},
                           f"B order {docket_id}/{doc_num}", max_pages):
            row = doc_row(dict(r, docket_id=docket_id), "B_related", f"order for entry {doc_num}")
            if row["filing_type_guess"] == "order":
                docs.append(row)


MONEY_RE = re.compile(r"\$\s?([\d,.]+)\s*(billion|million)?", re.I)


def funded_debt(snippet):
    """Largest dollar figure in a snippet that mentions funded debt, in $ millions."""
    best = None
    for m in MONEY_RE.finditer(snippet):
        try:
            v = float(m.group(1).replace(",", "").rstrip("."))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        v = v * 1000 if unit == "billion" else v if unit == "million" else v / 1e6
        best = v if best is None else max(best, v)
    return best


def track_a_rank(sess, dockets, max_pages):
    """First-day declarations that state funded debt; snippet carries the figure."""
    print("Track A ranking: funded debt in first-day declarations")
    rows = []
    desc = '"first day" OR "in support of chapter 11" OR "in support of the chapter 11" OR "in support of debtors"'
    # Many declarations describe the capital structure without the phrase
    # "funded debt", so a second query catches those (deduplicated below).
    queries = [('"funded debt" AND chapter:11', "A rank funded debt"),
               ('("aggregate principal amount" OR indebtedness) AND chapter:11', "A rank principal amount")]
    seen = set()
    results = []
    for q, purpose in queries:
        for r in cl_search(sess, base_params("rd", q, desc), purpose, max_pages):
            if r.get("id") not in seen:
                seen.add(r.get("id"))
                results.append(r)
    for r in results:
        snip = clean(r.get("snippet"))
        rows.append({"docket_id": r["docket_id"], "recap_doc_id": r.get("id"),
                     "document_number": r.get("document_number"),
                     "description": clean(r.get("description"))[:200],
                     "funded_debt_musd": funded_debt(snip), "snippet": snip[:600],
                     "is_available": r.get("is_available"), "page_count": r.get("page_count"),
                     "filepath_local": r.get("filepath_local") or "",
                     "doc_url": "https://www.courtlistener.com" + (r.get("absolute_url") or "")})
    return rows


MIN_AVAILABLE_APPLICATIONS = 3  # census qualification (Kyle chose re-pick by coverage, 10/09/2026)


def track_a_census(sess, dockets, docs, top_n, max_pages):
    """Phase 2: walk the funded-debt ranking and take the first top_n cases whose
    retention filings are reasonably covered by RECAP.

    One search per case returns only retention-described entries that have a
    PDF in RECAP. A case qualifies with at least MIN_AVAILABLE_APPLICATIONS
    retention applications (main documents) available. Filings not in RECAP
    are outside the prevalence denominator anyway (CLAUDE.md rule 8).
    """
    from select_census import kind  # same rules used to pick documents to fetch
    path = DATA / "track_a_ranking.csv"
    if top_n <= 0 or not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        ranked = sorted((r for r in csv.DictReader(f) if r["rank"]), key=lambda r: int(r["rank"]))
    coverage = []
    for r in ranked:
        if sum(1 for c in coverage if c["qualifies"]) >= top_n:
            break
        params = {"type": "rd", "q": f"docket_id:{r['docket_id']} AND is_available:true",
                  "description": RETENTION_DESC}
        found = list(cl_search(sess, params, f"A coverage {r['docket_id']}", max_pages))
        rows = [doc_row(dict(d, docket_id=int(r["docket_id"])), "A_available", f"rank {r['rank']}") for d in found]
        apps = {x["document_number"] for x in rows
                if x["attachment_number"] in ("", "0", None) and kind(x) == "application"}
        q = len(apps) >= MIN_AVAILABLE_APPLICATIONS
        coverage.append({"rank": r["rank"], "docket_id": r["docket_id"], "debtor": r["debtor"],
                         "court_id": r["court_id"], "case_number": r["case_number"],
                         "funded_debt_musd": r["funded_debt_musd"], "available_retention_docs": len(rows),
                         "available_applications": len(apps), "qualifies": q})
        print(f"Track A coverage: #{r['rank']} {r['debtor'][-30:]}: {len(apps)} applications in RECAP"
              f"{' (qualifies)' if q else ''}")
        if q:
            for x in rows:
                x["track"] = "A"
            docs.extend(rows)
    census = [c for c in coverage if c["qualifies"]]
    if census:
        ids = " OR ".join(c["docket_id"] for c in census)
        for d in cl_search(sess, {"type": "d", "q": f"docket_id:({ids})"}, "A census metadata", 2):
            dockets[d["docket_id"]] = docket_row(d)
    return coverage


def sec_search(sess, max_pages):
    rows = []
    for term in SEC_TERMS:
        q = f'"{term}" "engagement letter" "restructuring"'
        print(f"SEC: {term}")
        for page in range(max_pages):
            params = {"q": q, "dateRange": "custom", "startdt": WINDOW_START,
                      "enddt": date.today().isoformat(), "from": page * 100}
            data = cached_get(sess, SEC_FTS, "sec", params=params, purpose=f"SEC {term} p{page + 1}")
            hits = data.get("hits", {}).get("hits", [])
            for h in hits:
                s = h["_source"]
                adsh, _, fname = h["_id"].partition(":")
                cik = (s.get("ciks") or [""])[0].lstrip("0")
                rows.append({
                    "query": term, "form": s.get("form"), "file_type": s.get("file_type"),
                    "file_date": s.get("file_date"), "company": "; ".join(s.get("display_names") or []),
                    "file_description": s.get("file_description"),
                    "exhibit": (s.get("file_type") or "").upper().startswith("EX-"),
                    "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{adsh.replace('-', '')}/{fname}",
                })
            total = data.get("hits", {}).get("total", {}).get("value", 0)
            if (page + 1) * 100 >= total:
                break
    return rows


# ---------------------------------------------------------------- outputs

def write_csv(path, rows, fields):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    atomic_write_text(path, buf.getvalue())


def in_window(row):
    """True/False on petition date and venue; "unknown" if docket metadata is missing.

    The search API's date filter let a 2023 case through in testing, so the
    window is enforced here as well.
    """
    pd = row.get("petition_date")
    if not pd:
        return "unknown"
    # Reopened cases and adversary proceedings can carry a recent dateFiled
    # on an old case number (e.g., 17-12082), so check the case-number year too.
    m = re.match(r"(?:\d+:)?(\d{2})-", row.get("docket_number") or "")
    if m and 2000 + int(m.group(1)) < int(WINDOW_START[:4]):
        return False
    return pd >= WINDOW_START and row.get("court_id") in COURTS


def merge_docs(docs, dockets):
    """One row per RECAP document; tracks and queries that found it are joined."""
    merged = {}
    for d in docs:
        key = d["recap_doc_id"]
        if key in merged:
            m = merged[key]
            for f in ("track", "query"):
                vals = set(m[f].split("|")) | {d[f]}
                m[f] = "|".join(sorted(vals))
            continue
        k = dict(d)
        k.update({f: dockets.get(d["docket_id"], {}).get(f) for f in
                  ("court_id", "case_name", "docket_number", "petition_date", "docket_url")})
        k["in_window"] = in_window(k)
        merged[key] = k
    return sorted(merged.values(), key=lambda r: (r["court_id"] or "", r["case_name"] or "",
                                                   int(r["document_number"] or 0), int(r["attachment_number"] or 0)))


DOC_FIELDS = ["track", "query", "in_window", "court_id", "case_name", "docket_number", "petition_date",
              "docket_id", "recap_doc_id", "entry_date", "document_number", "attachment_number",
              "role_guess", "filing_type_guess", "retained_by_guess", "firm_guess", "description",
              "short_description", "is_available", "page_count", "filepath_local", "doc_url",
              "docket_url", "snippet"]
CASE_FIELDS = ["docket_id", "court_id", "case_name", "docket_number", "petition_date", "chapter",
               "in_window", "in_track_a_universe", "track_b_hits", "docket_url"]
RANK_FIELDS = ["docket_id", "recap_doc_id", "document_number", "funded_debt_musd", "description",
               "snippet", "is_available", "page_count", "filepath_local", "doc_url"]
SEC_FIELDS = ["query", "exhibit", "form", "file_type", "file_date", "company", "file_description", "url"]


def summarize(cands, cases, sec_rows, stopped):
    inw = [c for c in cands if c["in_window"] is True]
    b = [c for c in inw if "B" in c["track"].split("|")]
    lines = ["# Discovery summary (Checkpoint 1 input)", ""]
    if stopped:
        lines += [f"**Incomplete:** {stopped}", ""]
    lines += [f"Generated {date.today().strftime('%m/%d/%Y')}. Counts are discovery candidates, "
              "not confirmed AI provisions; role, filing type, and firm are guesses from the docket text.", ""]
    lines += ["## Track B (AI terms in retention filings)", "",
              f"- Documents in window: {len(b)} across {len({c['docket_id'] for c in b})} cases",
              f"- Available in RECAP: {sum(1 for c in b if c['is_available'] in (True, 'True'))}",
              f"- Pages, if all available docs are fetched: "
              f"{sum(int(c['page_count'] or 0) for c in b if c['is_available'] in (True, 'True'))}",
              f"- Dropped as out of window or venue: "
              f"{sum(1 for c in cands if 'B' in c['track'].split('|') and c['in_window'] is False)}",
              f"- Missing docket metadata (window unknown): "
              f"{sum(1 for c in cands if 'B' in c['track'].split('|') and c['in_window'] == 'unknown')}", ""]
    for label, key in (("venue", "court_id"), ("role", "role_guess"), ("filing type", "filing_type_guess")):
        lines += [f"By {label}:", ""] + [f"- {k}: {v}" for k, v in Counter(c[key] for c in b).most_common()] + [""]
    lines += ["By AI term (a document can match several):", ""]
    terms = Counter(t for c in b for t in c["query"].split("|") if t in AI_TERMS)
    lines += [f"- {t}: {terms.get(t, 0)}" for t in AI_TERMS] + [""]
    uni = [c for c in cases if c["in_track_a_universe"] and c["in_window"] is True]
    lines += ["## Track A phase 1 (case universe)", "",
              f"- Chapter 11 cases in window with a claims agent retention in RECAP: {len(uni)}", ""]
    lines += [f"- {k}: {v}" for k, v in Counter(c["court_id"] for c in uni).most_common()] + [""]
    ex = [r for r in sec_rows if r["exhibit"]]
    lines += ["## SEC EDGAR", "",
              f"- Hits: {len(sec_rows)} ({len({r['url'] for r in sec_rows})} unique files), "
              f"of which exhibits: {len({r['url'] for r in ex})}", ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-pages", type=int, default=10)
    ap.add_argument("--sec", action="store_true",
                    help="rerun SEC EDGAR search (dropped as a source 10/09/2026; off by default)")
    ap.add_argument("--track-a-top", type=int, default=10,
                    help="census size for Track A phase 2 (approved 10/09/2026: top 10)")
    ap.add_argument("--census-max-pages", type=int, default=25)
    ap.add_argument("--max-wait", type=int, default=3700,
                    help="longest pause (seconds) for a rate window before stopping; use a small value "
                         "to rebuild outputs from cache without waiting")
    args = ap.parse_args()
    require_env("COURTLISTENER_TOKEN", "SEC_USER_AGENT")

    # Every stage runs every time; pages already fetched come from cache.
    sess = Session(max_wait=args.max_wait)
    dockets, docs, universe, sec_rows, rank_rows, census, stopped = {}, [], set(), [], [], [], ""
    try:
        track_b(sess, dockets, docs, args.max_pages)
        universe = track_a_universe(sess, dockets, docs, args.max_pages)
        track_b_related(sess, dockets, docs, args.max_pages)
        rank_rows = track_a_rank(sess, dockets, args.max_pages)
        census = track_a_census(sess, dockets, docs, args.track_a_top, args.census_max_pages)
    except SourceStopped as e:
        stopped = f"CourtListener stopped: {e}. Rerun later; cached pages are reused."
        print(stopped)
    if args.sec:
        try:
            sec_rows = sec_search(sess, args.max_pages)
        except SourceStopped as e:
            stopped += f" SEC stopped: {e}."

    cands = merge_docs(docs, dockets)
    b_hits = Counter(c["docket_id"] for c in cands if "B" in c["track"].split("|"))
    cases = []
    for k, v in dockets.items():
        cases.append(dict(v, in_window=in_window(v),
                          in_track_a_universe=k in universe, track_b_hits=b_hits.get(k, 0)))
    cases.sort(key=lambda c: (c["court_id"] or "", c["case_name"] or ""))

    write_csv(DATA / "candidates.csv", cands, DOC_FIELDS)
    write_csv(DATA / "cases.csv", cases, CASE_FIELDS)
    if sec_rows:
        write_csv(DATA / "sec_candidates.csv", sec_rows, SEC_FIELDS)
    if rank_rows:
        write_csv(DATA / "track_a_funded_debt.csv", rank_rows, RANK_FIELDS)
    if census:
        write_csv(DATA / "track_a_coverage.csv", census, list(census[0]))
    atomic_write_text(DATA / "discovery_summary.md", summarize(cands, cases, sec_rows, stopped))
    print(f"Wrote {len(cands)} candidates, {len(cases)} cases, {len(sec_rows)} SEC hits, "
          f"{len(rank_rows)} funded-debt rows.")


if __name__ == "__main__":
    main()

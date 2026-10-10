"""Select Track A census documents to fetch (reads saved files only).

Option 1 approved at Checkpoint 1 (10/09/2026): for each retention, the
application with all its exhibits and the entered order. Ordinary course
professionals are covered by the OCP procedures motion and its order;
individual OCP declarations are listed for the coverage report but not
fetched. Writes data/fetch_list_a.csv (with a reason per row) and
data/census_retentions.csv (one row per retention filing found).

Usage: python select_census.py
"""
import csv
import io
import re
from collections import Counter

from common import DATA, atomic_write_text

RETAIN = r"employ|retain|retention|appoint|claims and noticing|claims agent|noticing agent|ordinary course"
APPLICATION = re.compile(r"^(sealed )?(application|motion)\b.*?(" + RETAIN + ")", re.I)
ORDER = re.compile(r"^order\b.*?(" + RETAIN + ")", re.I)
NOT_RETENTION = re.compile(r"compensation|interim fee|monthly fee|shorten|prepetition (trade|wages|taxes)|"
                           r"pro hac|seal(ing)? (the|certain)|bar date|key employee|incentive|"
                           r"critical vendor|reject|assum|cash management|insurance|utilit", re.I)
OCP_DECL = re.compile(r"ordinary course professional|disinterestedness", re.I)


def kind(c):
    d = re.sub(r"^[^A-Za-z]+", "", c["description"])
    # Normalize docket-text prefixes but keep the retention verb the rules below need.
    d = re.sub(r"^Application/Motion to Employ/Retain\s*", "Application to employ ", d)
    d = re.sub(r"^Motion to Authorize\s*/?\s*", "Motion ", d)
    if NOT_RETENTION.search(d[:250]) and not re.search(r"employ|retain|retention", d[:120], re.I):
        return None
    if ORDER.search(d[:250]):
        return "entered_order"
    if APPLICATION.search(d[:250]):
        return "application"
    if OCP_DECL.search(d[:200]) and re.search(r"declaration|affidavit|questionnaire", d[:120], re.I):
        return "ocp_declaration"
    return None


def main():
    with open(DATA / "candidates.csv", newline="", encoding="utf-8") as f:
        cands = [c for c in csv.DictReader(f) if "A" in c["track"].split("|") and c["in_window"] == "True"]
    entries = {}
    for c in cands:
        if c["attachment_number"] in ("", "0"):
            k = kind(c)
            if k:
                entries[(c["docket_id"], c["document_number"])] = k
    rows, fetch = [], []
    for c in cands:
        k = entries.get((c["docket_id"], c["document_number"]))
        if not k:
            continue
        main_doc = c["attachment_number"] in ("", "0")
        if main_doc:
            rows.append({"kind": k, **{f: c[f] for f in ("case_name", "court_id", "docket_number", "docket_id",
                                                           "document_number", "entry_date", "role_guess",
                                                           "retained_by_guess", "firm_guess", "description")}})
        take = (k == "application") or (k == "entered_order" and main_doc)
        if take:
            fetch.append({"recap_doc_id": c["recap_doc_id"], "case_name": c["case_name"],
                          "docket_number": c["docket_number"], "document_number": c["document_number"],
                          "attachment_number": c["attachment_number"], "is_available": c["is_available"],
                          "page_count": c["page_count"],
                          "reason": "application or its exhibit" if k == "application" else "entered order"})
    for path, data in ((DATA / "census_retentions.csv", rows), (DATA / "fetch_list_a.csv", fetch)):
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
        atomic_write_text(path, buf.getvalue())
    print("Retention filings by kind:", dict(Counter(r["kind"] for r in rows)))
    avail = [f for f in fetch if f["is_available"] == "True"]
    print(f"Fetch list: {len(fetch)} documents, {len(avail)} in RECAP, "
          f"{sum(int(f['page_count'] or 0) for f in avail)} pages")
    for case, n in Counter(f["case_name"][:30] for f in fetch).most_common():
        print(f"  {n:4} {case}")


if __name__ == "__main__":
    main()

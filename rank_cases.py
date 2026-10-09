"""Rank Track A candidate cases by funded debt in their first-day declarations.

Reads only saved files (data/text/ranking/). For each declaration it takes
the caption (court, case number, debtor) from the first page and every
sentence that states a dollar figure for funded debt, skipping sentences
about debt eliminated in a past deal or remaining after emergence. The
case figure is the largest qualifying amount; the sentence it came from is
kept so every number can be checked by hand.

Writes data/track_a_ranking.csv. Usage: python rank_cases.py
"""
import csv
import io
import re
from pathlib import Path

from common import COURTS, DATA, WINDOW_START, atomic_write_text

TEXT = DATA / "text" / "ranking"
OVERRIDES = DATA / "ranking_overrides.csv"

COURT_NAMES = {
    "deb": r"district of delaware", "njb": r"district of new jersey",
    "txsb": r"southern district of texas", "txnb": r"northern district of texas",
    "nysb": r"southern district of new york", "vaeb": r"eastern district of virginia",
    "ganb": r"northern district of georgia",
}
CASE_NO = re.compile(r"Case\s+No\.?\s*:?\s*((?:\d+:)?(\d{2})-(\d{4,5}))", re.I)
IN_RE = re.compile(r"In\s+re\s*:?\s*\n?\s*(.{3,120}?)(?:,?\s+et\s+al\.?|\n\s*Debtors?)", re.I | re.S)
MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)\s*(billion|million)?", re.I)
EXCLUDE = re.compile(r"eliminat|reduc|deleverag|upon emergence|post-emergence|exit facility|"
                     r"following (the )?(consummation|effective date)|was \$|previously", re.I)


# A figure stated "as of the Petition Date" or as currently outstanding is
# reliable; anything else (a past maturity wall, a table total) gets a manual check.
CURRENT = re.compile(r"petition date|as of|currently|outstanding|has approximately|have approximately", re.I)


def sentences(text):
    flat = re.sub(r"\s+", " ", text)
    return re.split(r"(?<=[.;])\s+(?=[A-Z(])", flat)


def amount_musd(m):
    v = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit == "billion":
        return v * 1000
    if unit == "million":
        return v
    return v / 1e6


# Phrases that state the size of the prepetition debt, in order of preference.
MEASURES = [("funded debt", re.compile(r"funded[- ]debt", re.I)),
            ("principal or indebtedness", re.compile(r"aggregate (outstanding )?principal amount|"
                                                     r"outstanding indebtedness|total (outstanding )?"
                                                     r"(debt|indebtedness)|prepetition indebtedness", re.I))]


def funded_debt(text):
    """Return (largest qualifying $ millions, sentence, candidate count, measure).

    Uses the "funded debt" figure when the declaration states one; otherwise
    falls back to sentences about aggregate principal or total indebtedness.
    """
    sents = sentences(text)
    for name, pat in MEASURES:
        best, best_s, n = None, "", 0
        for s in sents:
            if not pat.search(s) or EXCLUDE.search(s):
                continue
            for m in MONEY.finditer(s):
                v = amount_musd(m)
                if v < 0.1 or v > 200_000:  # under $100k or over $200bn is a parse error
                    continue
                n += 1
                if best is None or v > best:
                    best, best_s = v, s
        if best is not None:
            return best, best_s[:400], n, name
    return None, "", 0, ""


def caption(text):
    head = text[:4000]
    low = head.lower()
    court = next((c for c, pat in COURT_NAMES.items() if re.search(pat, low)), "")
    m = CASE_NO.search(head)
    case_no, year = (m.group(1), int(m.group(2))) if m else ("", None)
    d = IN_RE.search(head)
    debtor = re.sub(r"\s+", " ", d.group(1)).strip(" ,") if d else ""
    return court, case_no, year, debtor


def main():
    rows = []
    for txt in sorted(TEXT.rglob("*.txt")):
        text = txt.read_text(encoding="utf-8")
        court, case_no, year, debtor = caption(text)
        amt, sent, n, measure = funded_debt(text)
        rows.append({"docket_id": txt.parent.name, "recap_doc_id": txt.stem, "court_id": court,
                     "case_number": case_no, "debtor": debtor[:100],
                     "in_scope": bool(court in COURTS and year is not None and 2000 + year >= int(WINDOW_START[:4])),
                     "funded_debt_musd": round(amt, 1) if amt is not None else "",
                     "candidates": n, "measure": measure, "sentence": sent,
                     "needs_check": bool(sent) and not CURRENT.search(sent), "text": str(txt.relative_to(DATA.parent))})
    # Hand-checked corrections, each with its source sentence and a note.
    overrides = {}
    if OVERRIDES.exists():
        with open(OVERRIDES, newline="", encoding="utf-8") as f:
            overrides = {o["case_number"]: o for o in csv.DictReader(f)}
    for r in rows:
        o = overrides.get(r["case_number"])
        if o:
            r.update(funded_debt_musd=float(o["funded_debt_musd"]), measure=o["measure"],
                     sentence=o["sentence"], needs_check=False, note=o["note"])
    # One row per docket: the declaration with the largest figure.
    best = {}
    for r in rows:
        cur = best.get(r["docket_id"])
        if cur is None or (r["funded_debt_musd"] or 0) > (cur["funded_debt_musd"] or 0):
            best[r["docket_id"]] = r
    ranked = sorted(best.values(), key=lambda r: (not r["in_scope"], -(r["funded_debt_musd"] or 0)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i if r["in_scope"] and r["funded_debt_musd"] != "" else ""
    fields = ["rank", "funded_debt_musd", "court_id", "case_number", "debtor", "in_scope", "measure", "needs_check", "candidates",
              "sentence", "note", "docket_id", "recap_doc_id", "text"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, restval="")
    w.writeheader()
    w.writerows(ranked)
    atomic_write_text(DATA / "track_a_ranking.csv", buf.getvalue())
    print(f"{len(rows)} declarations, {len(best)} dockets, "
          f"{sum(1 for r in ranked if r['rank'] != '')} ranked in scope.")


if __name__ == "__main__":
    main()

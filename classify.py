"""Classify: work packets in, validated rubric JSON out.

Classification is done in-session by Claude (CLAUDE.md), so this script does
the mechanical parts and reads only saved files:

  python classify.py packets    write one packet per filing with AI passages, or
                                with none, to data/classify/packets/ (metadata,
                                parts searched, and every located passage with
                                context)
  python classify.py validate   check every data/classify/results/*.json against
                                the rubric and the source text, then write
                                data/classifications.jsonl

Validation rules: every R1 to R14 field has a value; any value other than
"silent" or "not_available" must carry an excerpt that appears verbatim
(whitespace-normalized) in one of the filing's documents (for R14, any fetched
document in the case, since court treatment sits in orders and objections);
"silent" and "not_available" carry no excerpt. The Anthropic
API path is not built: it runs only if ANTHROPIC_API_KEY is set and Kyle
asks for it.
"""
import csv
import json
import re
import sys
from collections import defaultdict

from common import DATA, atomic_write_text

LOC = DATA / "located"
PACKETS = DATA / "classify" / "packets"
RESULTS = DATA / "classify" / "results"

RUBRIC = {
    "R1": "Disclosure of use: general, specific tasks, or named tools",
    "R2": "Human review or validation requirement",
    "R3": "Liability posture: firm fully responsible, client bears AI-error risk, tied to liability cap, or silent",
    "R4": "Confidentiality: no training, no retention, enterprise-grade, approved-tool list, DPA referenced",
    "R5": "AI providers treated as permitted recipients under the confidentiality clause",
    "R6": "Access to client systems (read-only, scope, disconnection)",
    "R7": "MNPI, deal data, or data room restrictions",
    "R8": "Consent mechanism: signature acknowledgment, separate consent, or none",
    "R9": "Client opt-out right and any stated effect on fees or timing",
    "R10": "Billing: treatment of time, AI costs as expense vs. overhead, efficiency pass-through",
    "R11": "Court filings, declarations, testimony, and local AI disclosure orders",
    "R12": "AI-specific incident notification",
    "R13": "Firm reserves rights to use client data (even de-identified) for analytics or model training",
    "R14": "Court or UST treatment: objection filed, provision modified or struck in the entered order",
}
DOC_FIELDS = ["case_name", "case_number", "court", "petition_date", "filing_date", "docket_number",
              "document_url", "professional_firm", "role", "retained_by", "filing_type", "el_attached",
              "ai_provision_present", "location", "track"]
# "silent": the text does not address the field. "not_available": the document
# that would answer it (usually the entered order) is not in RECAP; a gap, not a "no".
NO_EXCERPT = {"silent", "not_available"}
ROLES = {"FA", "IB", "CRO", "claims agent", "administrative advisor", "OCP", "debtor counsel",
         "committee counsel", "committee FA", "other"}


def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def filing_key(p):
    return f"{p['docket_number']}_{p['document_number']}"


def packets():
    passages = [json.loads(l) for l in open(LOC / "passages.jsonl", encoding="utf-8")]
    by_filing = defaultdict(list)
    for p in passages:
        by_filing[filing_key(p)].append(p)
    with open(LOC / "filings.csv", newline="", encoding="utf-8") as f:
        filings = list(csv.DictReader(f))
    for fl in filings:
        key = f"{fl['docket_number']}_{fl['document_number']}"
        lines = [f"# Filing {key}", "", *(f"- {k}: {fl[k]}" for k in fl), "", "## AI passages", ""]
        ps = by_filing.get(key, [])
        if not ps:
            lines.append("None located. Code every rubric field silent and ai_provision_present N, "
                         "after checking the documents listed in the manifest for this entry.")
        for p in ps:
            lines += [f"### {p['passage_id']} ({p['part']}, attachment {p['attachment_number'] or 0}, "
                      f"page {p['page']}) flags: {p['fp_flags'] or 'none'}", "",
                      f"> before: {p['context_before']}", "", f"**{p['passage']}**", "",
                      f"> after: {p['context_after']}", "", f"source: {p['text']}", ""]
        atomic_write_text(PACKETS / f"{key}.md", "\n".join(lines) + "\n")
    print(f"{len(filings)} packets, {sum(1 for fl in filings if by_filing.get(f'{fl['docket_number']}_{fl['document_number']}'))} with AI passages")


def filing_texts(docket_number, document_number=None):
    """Normalized text of a filing's documents, or of every fetched document in the
    case when document_number is None (R14 evidence sits in orders and objections)."""
    with open(DATA / "fetch_manifest.csv", newline="", encoding="utf-8") as f:
        paths = [m["path"] for m in csv.DictReader(f)
                 if m["docket_number"] == docket_number and m["status"] == "ok"
                 and (document_number is None or m["document_number"] == document_number)]
    out = []
    for p in paths:
        t = DATA.parent / p.replace("data/raw/", "data/text/").replace(".pdf", ".txt")
        if t.exists():
            out.append(norm(re.sub(r"=== page \d+ ===", " ", t.read_text(encoding="utf-8"))))
    return out


def validate():
    rows, errors = [], []
    for path in sorted(RESULTS.glob("*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        errs = [f"missing {k}" for k in DOC_FIELDS if k not in r]
        if r.get("role") not in ROLES:
            errs.append(f"role {r.get('role')!r} not in {sorted(ROLES)}")
        texts = filing_texts(str(r.get("docket_number", "")), str(r.get("document_number", "")))
        case_texts = filing_texts(str(r.get("docket_number", "")))
        if not texts:
            errs.append("no extracted text found for this filing")
        for code in RUBRIC:
            field = r.get("rubric", {}).get(code)
            if not isinstance(field, dict) or "value" not in field:
                errs.append(f"{code}: missing value")
                continue
            ex = field.get("excerpt", "")
            if field["value"] in NO_EXCERPT:
                if ex:
                    errs.append(f"{code}: {field['value']} must not carry an excerpt")
            elif not ex:
                errs.append(f"{code}: coded {field['value']!r} without an excerpt")
            elif texts and not any(norm(ex) in t for t in (case_texts if code == "R14" else texts)):
                errs.append(f"{code}: excerpt not found verbatim in the "
                            f"{'case' if code == 'R14' else 'filing'}'s text")
        if errs:
            errors.append((path.name, errs))
        else:
            rows.append(r)
    atomic_write_text(DATA / "classifications.jsonl",
                      "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))
    for name, errs in errors:
        print(f"INVALID {name}:")
        for e in errs:
            print(f"  - {e}")
    print(f"{len(rows)} valid, {len(errors)} invalid")
    return not errors


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "packets":
        packets()
    elif cmd == "validate":
        sys.exit(0 if validate() else 1)
    else:
        sys.exit(__doc__)

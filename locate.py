"""Locate: find AI passages in every fetched filing and record EL status.

Reads only saved files (data/text/, data/fetch_manifest.csv,
data/candidates.csv). Searches the full text of every document in a filing
(application, declaration, proposed order, exhibits), whether or not an
engagement letter is attached. Each hit is pulled with one paragraph of
context on each side, tagged with the part of the filing it came from, and
screened against the known false positives in CLAUDE.md.

Writes:
  data/located/passages.jsonl  one row per AI passage
  data/located/filings.csv     one row per filing (docket entry): EL attached,
                               AI passages found, documents searched
Usage: python locate.py
"""
import csv
import io
import json
import re
from collections import defaultdict

from common import DATA, atomic_write_text

OUT = DATA / "located"

AI_RE = re.compile(
    r"artificial[- ]intelligence|generative\s+(?:AI|artificial)|large[- ]language[- ]models?|\bLLMs?\b|"
    r"machine[- ]learning|ChatGPT|\bCopilot\b|\bGen\s?AI\b|"
    r"\bAI\b(?=[\s-]*(?:tools?|technolog|enabled|assisted|powered|based|platforms?|systems?|models?|"
    r"solutions?|software|applications?|services?|capabilit|use|usage|providers?|vendors?|products?))|"
    r"(?:use|uses|using|utiliz\w*|leverag\w*|deploy\w*)\s+(?:of\s+)?(?:\w+\s+){0,3}\bAI\b|"
    r"\(\s*[\"“]?AI[\"”]?\s*\)",
    re.I)

# Known false positives (CLAUDE.md). Flagged, not dropped, so a human can check.
FP_RULES = [
    ("conflicts_schedule", re.compile(r"parties[- ]in[- ]interest|potential parties|conflicts? (search|check|list)|"
                                      r"schedule\s+\d|interested parties|searched parties", re.I)),
    ("ediscovery_tar", re.compile(r"technology[- ]assisted review|predictive coding|\bTAR\b|e-?discovery", re.I)),
    ("electronic_comms_consent", re.compile(r"electronic (mail|communications?)|e-mail|unencrypted", re.I)),
]
COMPANY_SUFFIX = re.compile(r"\b(Inc|LLC|L\.?P|Corp|Ltd|GmbH|S\.?A|Co)\b\.?")

EL_RE = re.compile(r"engagement (letter|agreement)|letter agreement|standard (terms|business terms)|"
                   r"terms and conditions|terms of (business|engagement)|services agreement|"
                   r"general (business )?terms", re.I)
# Page openings that start a new section inside a multi-part exhibit.
SECTION_RULES = [
    ("engagement_letter", re.compile(r"engagement (letter|agreement)|services agreement|standard (business )?terms|"
                                     r"terms and conditions|general (business )?terms|^dear\b|re:\s+engagement", re.I)),
    ("proposed_order", re.compile(r"\[proposed\]|proposed order|^order\b|it is hereby ordered", re.I)),
    ("declaration", re.compile(r"^(declaration|affidavit)\b|declaration of|affidavit of", re.I)),
]


def location_tag(desc, short_desc, attachment, text_head):
    """Which part of the filing a document is."""
    d = f"{short_desc} {desc}".lower()
    head = text_head.lower()
    if attachment in ("", "0", None):
        sd, dd = short_desc.lower().strip(), desc.lower().strip()
        if re.match(r"(generic )?order\b", sd) or re.match(r"order\b", dd):
            return "entered_order"
        if "notice" in sd or re.search(r"\bnotice of\b", dd[:80]):
            return "notice"
        if "declaration" in sd or "affidavit" in sd:
            return "declaration"
        return "application_body"
    if re.search(r"proposed order", d) or re.search(r"\[proposed\]|proposed\s+order", head[:1500]):
        return "proposed_order"
    if re.search(r"redline|blackline|revised", d):
        return "revised_order"
    if EL_RE.search(short_desc) or EL_RE.search(head[:3000]):
        return "engagement_letter"
    if re.search(r"declaration|affidavit", d) or re.search(r"declaration of|affidavit of", head[:1500]):
        return "declaration"
    return "exhibit_other"


def page_sections(text, default):
    """Map page number to the section it belongs to, carried forward from the last section start."""
    sections, current = {}, default
    for m in re.finditer(r"=== page (\d+) ===\n(.*?)(?=\n=== page \d+ ===|\Z)", text, re.S):
        body = re.sub(r"^Case \d+[-:].*?\n", "", m.group(2))  # running header
        opening = re.sub(r"\s+", " ", body)[:150]  # titles sit at the top of a page
        # A page that opens mid-sentence or on a numbered paragraph continues
        # the current section, even if it mentions "the Engagement Letter".
        continues = re.match(r"\s*([a-z]|\(?\d+[.)]\s)", opening)
        for name, pat in ([] if continues else SECTION_RULES):
            if pat.search(opening):
                current = name
                break
        sections[int(m.group(1))] = current
    return sections


def paragraphs(text):
    """(page, paragraph) pairs from page-marked text with blank lines between blocks."""
    out = []
    for m in re.finditer(r"=== page (\d+) ===\n(.*?)(?=\n=== page \d+ ===|\Z)", text, re.S):
        page = int(m.group(1))
        for p in re.split(r"\n\s*\n", m.group(2)):
            p = re.sub(r"\s+", " ", p).strip()
            if p and not re.match(r"^Case \d+[-:]", p):  # drop running headers
                out.append((page, p))
    return out


def screen(par, context):
    flags = [name for name, pat in FP_RULES if pat.search(par)]
    # A conflicts list is many short company names; real provisions are prose.
    if len(COMPANY_SUFFIX.findall(par)) >= 4 and len(par) / max(1, par.count(",") + 1) < 60:
        flags.append("entity_list")
    if flags and "electronic_comms_consent" in flags and not AI_RE.search(par):
        flags.remove("electronic_comms_consent")
    return flags


def main():
    cands = {}
    with open(DATA / "candidates.csv", newline="", encoding="utf-8") as f:
        for c in csv.DictReader(f):
            cands.setdefault(c["recap_doc_id"], c)
    with open(DATA / "fetch_manifest.csv", newline="", encoding="utf-8") as f:
        fetched = [m for m in csv.DictReader(f) if m["status"] == "ok"]

    passages, filings = [], defaultdict(lambda: {"documents": 0, "el_attached": False, "ai_passages": 0,
                                                 "ai_passages_flagged": 0, "parts_searched": set()})
    for m in fetched:
        c = cands.get(m["recap_doc_id"], {})
        txt_path = DATA.parent / m["path"].replace("data/raw/", "data/text/").replace(".pdf", ".txt")
        if not txt_path.exists():
            continue
        text = txt_path.read_text(encoding="utf-8")
        flat_head = re.sub(r"\s+", " ", text[:5000])
        part = location_tag(c.get("description", ""), c.get("short_description", ""),
                            c.get("attachment_number", ""), flat_head)
        key = (c.get("docket_id"), c.get("document_number"))
        fl = filings[key]
        fl.update({k: c.get(k, "") for k in ("track", "court_id", "case_name", "docket_number", "document_number",
                                             "entry_date", "role_guess", "filing_type_guess", "retained_by_guess",
                                             "firm_guess")})
        if c.get("attachment_number") in ("", "0", None):
            fl["description"] = c.get("description", "")[:300]
        fl["documents"] += 1
        # Attachments often bundle several parts (proposed order, then the EL as
        # its exhibit), so tag by page; main documents keep their doc-level tag.
        # Notices and entered orders also carry ELs as exhibits inside the same PDF.
        # Application bodies keep the doc-level tag: their opening pages mention
        # the "Proposed Order" and would be mis-tagged.
        is_attachment = c.get("attachment_number") not in ("", "0", None)
        sections = page_sections(text, part) if is_attachment or part in ("notice", "entered_order") else {}
        if part == "entered_order":
            sections = {pg: "entered_order" if sec == "proposed_order" else sec for pg, sec in sections.items()}
        parts = set(sections.values()) or {part}
        fl["parts_searched"] |= parts
        if "engagement_letter" in parts:
            fl["el_attached"] = True

        pars = paragraphs(text)
        hit_idx = [i for i, (_, p) in enumerate(pars) if AI_RE.search(p)]
        for i in hit_idx:
            page, par = pars[i]
            before = pars[i - 1][1] if i > 0 else ""
            after = pars[i + 1][1] if i + 1 < len(pars) else ""
            flags = screen(par, before + " " + after)
            passages.append({
                "passage_id": f"{m['recap_doc_id']}-{i}", "recap_doc_id": m["recap_doc_id"],
                "track": c.get("track", ""), "case_name": c.get("case_name", ""),
                "docket_number": c.get("docket_number", ""), "document_number": c.get("document_number", ""),
                "attachment_number": c.get("attachment_number", ""), "part": sections.get(page, part),
                "page": page,
                "matched_terms": sorted({x.group(0).strip() for x in AI_RE.finditer(par)}),
                "context_before": before, "passage": par, "context_after": after,
                "fp_flags": flags, "text": str(txt_path.relative_to(DATA.parent)),
            })
            fl["ai_passages"] += 1
            fl["ai_passages_flagged"] += bool(flags)

    OUT.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUT / "passages.jsonl", "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in passages))
    fields = ["track", "court_id", "case_name", "docket_number", "document_number", "entry_date", "role_guess",
              "filing_type_guess", "retained_by_guess", "firm_guess", "documents", "parts_searched",
              "el_attached", "ai_passages", "ai_passages_flagged", "description"]
    rows = []
    for fl in filings.values():
        fl = dict(fl, parts_searched="|".join(sorted(fl["parts_searched"])))
        rows.append(fl)
    rows.sort(key=lambda r: (r["case_name"], int(r["document_number"] or 0)))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    atomic_write_text(OUT / "filings.csv", buf.getvalue())
    print(f"{len(fetched)} documents, {len(rows)} filings, {len(passages)} passages "
          f"({sum(1 for p in passages if p['fp_flags'])} flagged as possible false positives)")


if __name__ == "__main__":
    main()

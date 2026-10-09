# Research Brief: AI Provisions in Chapter 11 Professional Engagement Letters

## Objective

Build a small, evidence-based benchmark of how restructuring professionals address AI use in engagement letters filed with retention applications in recent chapter 11 cases, and compare the results to MERU's draft clause (Appendix A).

Questions to answer:

1. **Prevalence.** In a defined set of recent large cases, what share of professional retention applications include any AI provision? Break down by professional type and by firm.
2. **Content.** For those that do, which elements appear (see rubric) and in what language?
3. **Court treatment.** Did the U.S. Trustee object to, or did the entered retention order modify or strike, any AI provision?
4. **Billing.** Do any ELs, retention orders, fee applications, or fee examiner reports address how AI affects billed time or reimbursable expenses?
5. **Gap analysis.** Where is MERU's clause ahead of, behind, or out of step with what others file?

## Scope

- **Window:** petitions filed 2025-01-01 to present.
- **Venues:** D. Del., D.N.J., S.D. Tex., N.D. Tex., S.D.N.Y., E.D. Va., N.D. Ga.
- **Professionals:** financial advisors, CROs and interim management (363(b)), investment bankers, and committee FAs (1103). Debtor and committee counsel as a comparison set (law firms are further along on AI disclosure because of ABA Formal Opinion 512). Claims and noticing agents (28 U.S.C. § 156(c) and administrative advisor retentions under 327) and ordinary course professionals as secondary sets, coded but reported separately.
- **Documents:** retention applications, Rule 2014 declarations, EL exhibits, supplemental declarations, proposed and entered retention orders, UST objections, § 156(c) claims agent applications, and ordinary course professional declarations. A filing is in scope whether or not it attaches an engagement letter; many firms state their terms only in the application or declaration. Fee applications and fee examiner reports only in the optional Phase 5.
- **Size:** 40 to 60 retention applications total, at least 25 of them FA/IB/CRO. Hard cap of 150 downloaded documents without checking in.

## Two-track sampling

- **Track A (census, for prevalence):** pick the 20 to 25 largest chapter 11 cases in the window and venues with good RECAP coverage. Pull every professional retention application in each, including those with no EL attached, plus the § 156(c) application and ordinary course professional declarations. This gives a clean denominator.
- **Track B (discovery, for content):** full-text search across all cases in scope for AI terms combined with retention terms. This finds the firms that are doing it, even outside the census cases.

Report Track A and Track B results separately so prevalence is not inflated by the discovery search.

## Data sources (priority order)

1. **CourtListener REST API (v4).** Free; requires an API token in `COURTLISTENER_TOKEN`. Use the RECAP search endpoint with full-text queries and court/date filters. Read the current API docs before writing any request code and confirm parameter names rather than assuming them. Coverage is limited to documents in the RECAP archive, so track what is missing.
2. **SEC EDGAR full-text search.** Public-company engagement letters with restructuring firms are sometimes filed as 8-K or 10-K exhibits. Set a descriptive User-Agent with a contact email (`SEC_USER_AGENT`) and stay under SEC's request rate limit.
3. **Claims agent websites (Kroll, Stretto, Epiq, Omni, Verita).** Do not scrape these automatically. Instead, produce a manual-pull list of retention documents that were not in RECAP, with the case name, docket number, and claims agent docket URL.
4. **PACER.** Not used unless Kyle approves a budget. If approved, enforce a hard dollar cap in code.

## Search terms

- **AI terms:** "artificial intelligence", "generative AI", "large language model", "AI Tools", "AI-assisted", "machine learning", "ChatGPT", "Copilot".
- **Retention terms:** "retain and employ", "engagement letter", "Rule 2014", "chief restructuring officer", "financial advisor", "investment banker", "section 1103", "156(c)", "claims and noticing agent", "administrative advisor", "ordinary course professional".
- Do not require "engagement letter" to appear in a document for it to qualify; it is one retention term among several.

## Known false positives (filter these out)

- Parties-in-interest and conflicts schedules listing vendors or counterparties with "AI" or "Artificial Intelligence" in their names. This will be the largest source of noise.
- eDiscovery "technology-assisted review" language.
- Debtors whose own business involves AI.
- Generic electronic communications consent language that does not mention AI.

## Pipeline

Keep scripts small, idempotent, and cached so re-runs do not re-download anything.

- `discover.py`: run Track A and Track B queries, write `data/candidates.csv`.
- `fetch.py`: download PDFs to `data/raw/`, log every request to `run_log.jsonl`.
- `extract.py`: text extraction (PyMuPDF), OCR fallback (ocrmypdf/tesseract) for scanned exhibits, write to `data/text/`.
- `locate.py`: search the full text of every filing (application, declaration, proposed order, and any exhibits) for AI-related passages, whether or not an EL exhibit exists. Pull each passage with one paragraph of context on each side and tag which part of the filing it came from. Separately, record whether an EL or standard terms exhibit is attached. Never skip a filing because no EL exhibit is found.
- `classify.py`: send each located passage to Claude via the Anthropic API with the rubric below; require JSON output with a verbatim supporting excerpt for every coded field. Use "silent" when the text does not address a field. Never infer.
- `report.py`: build the deliverables.

## Classification rubric

Per document: case name, case number, court, petition date, filing date, docket number, document URL, professional firm, role (FA / IB / CRO / claims agent / debtor counsel / committee counsel / other), retained by (debtor / committee / other), filing type (retention application / Rule 2014 declaration / supplemental declaration / § 156(c) application / OCP declaration / order / UST objection), EL or standard terms attached (Y/N), AI provision present (Y/N), and location (standalone EL section / inside EL confidentiality / inside standard terms / application body / declaration only / proposed or entered order).

Per AI provision, code each of the following with a value and a verbatim excerpt:

| Code | Element |
|---|---|
| R1 | Disclosure of use: general, specific tasks, or named tools |
| R2 | Human review or validation requirement |
| R3 | Liability posture: firm fully responsible, client bears AI-error risk, tied to liability cap, or silent |
| R4 | Confidentiality: no training, no retention, enterprise-grade, approved-tool list, DPA referenced |
| R5 | AI providers treated as permitted recipients under the confidentiality clause |
| R6 | Access to client systems (read-only, scope, disconnection) |
| R7 | MNPI, deal data, or data room restrictions |
| R8 | Consent mechanism: signature acknowledgment, separate consent, or none |
| R9 | Client opt-out right and any stated effect on fees or timing |
| R10 | Billing: treatment of time, AI costs as expense vs. overhead, efficiency pass-through |
| R11 | Court filings, declarations, testimony, and local AI disclosure orders |
| R12 | AI-specific incident notification |
| R13 | Firm reserves rights to use client data (even de-identified) for analytics or model training |
| R14 | Court or UST treatment: objection filed, provision modified or struck in the entered order (diff proposed vs. entered order) |

## Deliverables

1. `output/ai_el_benchmark.xlsx` with tabs: Provisions (one row per document), Prevalence (Track A summary by role and firm, split by EL attached vs. not, so "no AI language" is distinguishable from "no EL to check"), Case List, Manual Pull List.
2. `output/clause_library.md`: verbatim AI provisions grouped by firm, each with case name, docket number, and date.
3. `output/benchmark_memo.md`: two to three pages covering prevalence, common elements, outliers, court and UST treatment, billing findings, and a side-by-side gap table against MERU's clause with suggested redlines. Flag any finding resting on fewer than three examples as low confidence.

## Checkpoints (stop and report to Kyle)

1. **After discovery:** candidate counts by venue, role, and track, plus estimated download volume. Wait for approval before fetching.
2. **After the first 10 documents are classified:** show three sample classifications with excerpts for review before running the full set. Make sure the first 10 include at least two filings with no EL attached.

## Optional Phase 5: fee applications

Search fee applications and fee examiner reports in the census cases for AI references (time entries describing AI use, AI subscription charges in expense detail, examiner objections). Same rubric fields R10 and R14 only.

## Guardrails

- Respect rate limits with exponential backoff; cache everything.
- No PACER spend without approval. No automated scraping of claims agent sites.
- API keys live in environment variables and are never printed or logged.
- Use public court and SEC records only.

## Setup

Python 3.11+, `requests`, `pymupdf`, `pandas`, `openpyxl`, `anthropic`; optional `ocrmypdf` and `tesseract`. Environment variables: `COURTLISTENER_TOKEN`, `ANTHROPIC_API_KEY`, `SEC_USER_AGENT`.

---

## Appendix A: MERU draft clause (save as `meru_clause.txt`)

> **Use of Artificial Intelligence Tools**
>
> In connection with the Services, MERU may use artificial intelligence-based tools, including generative AI and large language models ("AI Tools"), to support research, drafting, data analysis, and other work product. Any use of AI Tools remains subject to professional review and validation by MERU personnel, and MERU retains full responsibility for the accuracy and quality of all deliverables regardless of the tools used to produce them.
>
> MERU will not input Client confidential or proprietary information into any AI Tool that retains, trains on, or otherwise uses such information beyond the scope of performing the Services, and will use only enterprise-grade or otherwise vetted AI Tools with appropriate data protection safeguards consistent with MERU's confidentiality obligations under this engagement letter. Where MERU connects an AI Tool to Client's systems, software, or data environments to assist in analysis, MERU will limit such access to the systems, credentials, and data Client makes available for the Services, will use read-only access unless Client agrees otherwise, will comply with Client's applicable security and access policies, and will disconnect such access upon completion of the Services. Where the Services involve non-public transaction data, deal terms, diligence materials, or other market-sensitive information, MERU will restrict AI Tool use to tools and workflows approved for such data and will not process such information through any AI Tool absent those safeguards.
>
> Client acknowledges and consents to MERU's use of AI Tools on these terms. Client may request that AI Tools not be used on specific workstreams by providing written notice to MERU's engagement lead.

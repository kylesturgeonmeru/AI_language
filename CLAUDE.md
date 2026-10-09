# Project: AI provisions in chapter 11 professional engagement letters

## Purpose
Benchmark how restructuring professionals address AI use in engagement letters and retention filings in recent chapter 11 cases, and compare the results to MERU's draft clause (`meru_clause.txt`). The full research brief is `docs/brief.md` and is the source of truth for scope, search terms, the R1 to R14 rubric, and deliverables. This file holds the working rules and the decisions made since the brief was written.

## Scope (summary; see brief for detail)
- Petitions filed 01/01/2025 to present in D. Del., D.N.J., S.D. Tex., N.D. Tex., S.D.N.Y., E.D. Va., and N.D. Ga.
- Primary set: FAs, CROs and interim management, investment bankers, and committee FAs. Comparison set: debtor and committee counsel. Secondary sets (reported separately): claims and noticing agents, administrative advisors, and ordinary course professionals.
- A filing is in scope whether or not an engagement letter is attached. Never skip a filing because no EL exhibit is found.
- Track A (census of the largest cases, for prevalence) and Track B (full-text discovery, for content) are always reported separately.

## Pipeline rules (non-negotiable)
1. Stages are separate. `discover.py` and `fetch.py` are the only scripts that touch the network. `extract.py`, `locate.py`, `classify.py`, and `report.py` only read saved files.
2. Every request is logged to `data/run_log.jsonl`: url, status, timestamp, sha256, bytes, error. Never log API keys or auth headers.
3. Resumable and idempotent: skip URLs already logged as successful; never duplicate rows.
4. Atomic writes: write to a temp file, then rename.
5. Polite access: honor documented API rate limits, exponential backoff on 429 and 5xx, and stop a source after repeated 403s or 429s. SEC requests send `SEC_USER_AGENT` and stay under SEC's published rate limit.
6. Validate PDFs after download; log truncated or unreadable files as failures.
7. The VM is disposable. Commit progress in small batches: run log, candidates, extracted text, located passages, and classifications. Do not commit raw PDFs in `data/raw/` (gitignored) unless Kyle asks.
8. Before any summary, memo, or chart, produce `data/coverage_report.md`: attempted, succeeded, failed, and gaps by venue, case, and role. A filing not in RECAP goes on the Manual Pull List and is excluded from the prevalence denominator. Treat gaps as unknown, never as "no AI provision."

## Sources
1. CourtListener REST API v4 with `COURTLISTENER_TOKEN`. Read the current API docs before writing request code; confirm parameter names instead of assuming them. The anonymous quota is shared and exhausted, so never call without the token.
2. SEC EDGAR full-text search with `SEC_USER_AGENT`.
3. Claims agent sites (Kroll, Stretto, Epiq, Omni, Verita): never scraped. Missing documents go on the Manual Pull List with case name, docket number, and claims agent docket URL.
4. PACER: not used without Kyle's approval and a hard dollar cap enforced in code.
Public records only. No logins, paywalls, or CAPTCHA workarounds.

## Decisions since the brief
- Classification: done in-session by Claude by default, applying the rubric and writing JSON with a verbatim excerpt for every coded field. `classify.py` calls the Anthropic API only if `ANTHROPIC_API_KEY` is set and Kyle asks for it. Either way: "silent" when the text does not address a field, never infer.
- Download cap: 400 documents, enforced in `fetch.py` (approved at Checkpoint 1, 10/09/2026).
- "Largest cases" for Track A: ranked by funded debt stated in the first-day declaration; where none is stated, fall back to the petition liabilities range and flag the case. Kyle reviews the ranked list before Track A phase 2 (approved 10/09/2026).
- Track A census, revised 10/09/2026: RECAP holds PDFs for only 20 of 181 application and order documents in the original strict top 10 (DISH DBS, Sunnova, Ligado, Wolfspeed, Signal National, Pine Gate, Eddie Bauer, F21, FAT Brands, and ModivCare), so Kyle chose to re-pick by coverage. Walk `data/track_a_ranking.csv` in funded-debt order and take the first 10 cases with at least 3 retention applications (main documents) available in RECAP (`data/track_a_coverage.csv`). The original top 10 (`data/original_top10_retentions.csv`) and large cases without a first-day declaration in RECAP (Spirit, Saks Global, At Home, New Rite Aid, Hughes Satellite, Azul, and Multi-Color) are known gaps for the coverage report.
- Track A size: the 10 largest cases, every retention in the primary, comparison, and secondary sets. For each retention fetch the application with its exhibits and the entered order only (approved 10/09/2026).
- Track B: fetch each hit's full docket entry (all attachments) and the entered retention order (approved 10/09/2026).
- SEC EDGAR: dropped as a systematic source (nearly all hits were noise). Check individual leads by hand; the one open lead is Sleep Number Corporation, 8-K EX-10.1 filed 07/23/2026 (approved 10/09/2026).
- CourtListener budget: this token has 5 requests/minute, 50/hour, and 125/day. `common.py` paces from the live `/api-usage/` endpoint and stops cleanly when the day is spent; reruns reuse cached pages.
- Subagents, if any, run on Sonnet.

## Checkpoints (stop and wait for Kyle)
1. After discovery: candidate counts by venue, role, and track, plus estimated download volume. No fetching before approval.
2. After the first 10 documents are classified: three sample classifications with excerpts. The first 10 must include at least two filings with no EL attached.

## Known false positives
Conflicts and parties-in-interest schedules listing AI-named entities (the biggest source of noise), eDiscovery "technology-assisted review" language, debtors whose business is AI, and generic electronic communications consents that do not mention AI.

## Environment
- Python 3.11+. Install as needed: `requests`, `pymupdf`, `pandas`, `openpyxl`; `anthropic` only if using the API; `ocrmypdf` and `tesseract-ocr` for scanned exhibits (apt for tesseract).
- Environment variables: `COURTLISTENER_TOKEN` (required), `SEC_USER_AGENT` (required), `ANTHROPIC_API_KEY` (optional). If a required one is missing, say so and stop; do not mock results.

## Style
No em-dashes. Oxford commas. Dates MM/DD/YYYY. Flag any finding resting on fewer than three examples as low confidence.

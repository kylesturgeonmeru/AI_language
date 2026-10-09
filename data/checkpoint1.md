# Checkpoint 1: discovery results (10/09/2026)

No documents have been fetched. This report asks for approval before `fetch.py` runs, plus decisions on the two PENDING items in CLAUDE.md.

## Track B (full-text discovery, for content)

Eight AI terms searched in RECAP, chapter 11 cases in the seven venues with petitions on or after 01/01/2025, limited to docket entries whose text reads as a retention filing.

| Case | Venue | Filing | Firm (guess) | Role | AI language in snippet |
|---|---|---|---|---|---|
| Zen JV, LLC (25-11195) | D. Del. | Application to retain, Dkt 145, attachment 3 | AlixPartners | FA (primary set) | "AlixPartners' Artificial Intelligence (AI) technologies" |
| At Home Group Inc. (25-11120) | D. Del. | Notice of additional engagement letter, Dkt 604 | Ernst & Young | other (to be confirmed) | "the use of generative artificial intelligence" |
| Pine Gate Renewables, LLC (25-90669) | S.D. Tex. | Application to employ, Dkt 228, attachment 1 | Latham & Watkins | debtor co-counsel (comparison set) | "software that utilizes artificial intelligence (AI)" |
| Pacifica of the Valley Corporation (26-11060) | D. Del. | Claims agent application, Dkt 15, attachment 1 | Verita (KCC) | claims agent (secondary set) | "VIII. ARTIFICIAL INTELLIGENCE (AI) Verita may use AI-assisted tools" |
| Alliance Farm and Ranch, LLC (25-30155) | S.D. Tex. | Exhibit to exhibit/witness list, Dkt 83, attachment 5 | unknown | unknown | "17. Software and Artificial Intelligence: Unless otherwise advised by the Client" |

- 5 documents in 5 cases, all available in RECAP, 124 pages in total. All 5 matched "artificial intelligence"; "AI Tools" and "AI-assisted" matched one each; the other five terms matched nothing.
- **Sensitivity check of the retention filter.** The same "artificial intelligence" search without the docket-text filter returns 287 documents. The filter keeps 6 (5 in window plus one 2023 case). The 281 it drops are publication affidavits, sale motions, protective orders, operating reports, and fee statements, with no retention filings among them. Nine dropped documents are fee statements or fee applications, which are relevant only to optional Phase 5.
- **Reading:** AI language in RECAP-available retention filings is rare. Only one hit (AlixPartners) is in the primary FA/IB/CRO set. Track B on its own cannot reach the brief's target of 40 to 60 retentions; content findings will rest mostly on Track A. Every Track B finding is low confidence until confirmed against the full documents.

## Track A (census, for prevalence): phase 1 universe

- 150 chapter 11 cases in window and venue have a claims agent retention in RECAP: D. Del. 84, D.N.J. 20, N.D. Tex. 18, S.D. Tex. 13, S.D.N.Y. 10, N.D. Ga. 4, E.D. Va. 1. List in `data/cases.csv` (`in_track_a_universe`).
- Known gap: some large 2025 cases are missing (for example JOANN and Wolfspeed), likely because their claims agent application is not in RECAP or is described differently. The proposal below closes most of this gap.

### Proposed "largest cases" measure (PENDING item)

Rank by **funded debt as stated in the first-day declaration**. One RECAP search for first-day declarations containing "funded debt", with highlighting on, returns the dollar figure in the snippet for most large cases. Cost: about 8 to 10 API requests. It also adds cases missing from the universe above. Where a declaration gives no figure, fall back to the liabilities range on the petition and flag the case. Kyle reviews the top 25 before phase 2.

Alternatives: the liability range on the petition (coarse, since the top bracket is "more than $1 billion" and many cases sit there), or the number of professional retentions on the docket (circular for a prevalence measure).

## SEC EDGAR

3,555 hits (1,873 unique files), 191 of them exhibits. Nearly all are noise: merger agreements, Canadian annual information forms, and proxy circulars from companies whose business involves AI. One lead is worth a manual look: **Sleep Number Corporation** (in chapter 11 in S.D.N.Y., 26-11399), 8-K EX-10.1 filed 07/23/2026. Recommendation: drop SEC as a systematic source and check individual leads by hand.

## Download volume and the cap (PENDING item)

- **Track B:** 5 documents now. To code each hit properly, also fetch the rest of its docket entry (application, declaration, EL exhibit) and the entered order: about 20 to 30 documents.
- **Track A phase 2:** the brief asks for every professional retention in 20 to 25 cases. At about 10 to 15 retentions per large case (including OCP and claims agent filings) and 3 to 5 documents each, that is 600 to 1,800 documents, far over the 150 cap. It also conflicts with the brief's own target of 40 to 60 retention applications.
- **Options:**
  1. **(Recommended)** 10 largest cases, all retentions in the primary, comparison, and secondary sets; fetch the application (with its exhibits) and the entered order only. About 120 retentions and 250 to 350 documents. Cap raised to 400.
  2. 20 to 25 largest cases, primary set (FA, IB, CRO, committee FA) only, with counsel and secondary sets skipped. About 60 to 90 retentions and 150 to 250 documents.
  3. Keep the 150 cap and take whatever the 5 to 6 largest cases yield.

## API budget

- This CourtListener token has no membership: 5 requests per minute, 50 per hour, 125 per day. Discovery used about 45 requests today; 80 remain.
- Track A phase 2 discovery costs about 1 to 3 requests per case (25 to 75 in total). Downloads come from `storage.courtlistener.com`; whether those count against the API limit is unknown, and `fetch.py` will test it on the first file before continuing.
- At these limits, phase 2 plus the funded-debt ranking takes one to two days. A Free Law Project membership would raise the limits.

## Decisions needed

1. Approve fetching the Track B documents (about 20 to 30).
2. Approve the funded-debt measure for "largest cases", or pick an alternative.
3. Pick a Track A size and download cap (option 1, 2, or 3 above).
4. Approve dropping SEC search apart from the Sleep Number lead.

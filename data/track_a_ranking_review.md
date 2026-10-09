# Track A ranking for review (10/09/2026)

Measure: funded debt stated in the first-day declaration (approved at Checkpoint 1). Figures come from the full text of 132 first-day declarations covering 100 dockets. 63 in-scope cases have a figure. Every figure in `data/track_a_ranking.csv` carries the sentence it came from; four were corrected or confirmed by hand (`data/ranking_overrides.csv`).

## Proposed census: top 10 by funded debt

| Rank | Case | Venue | Case no. | Funded debt | Note |
|---|---|---|---|---|---|
| 1 | DISH DBS Corporation | S.D. Tex. | 26-90627 | ~$11.75 billion | From the refinancing summary; plausible, not exact |
| 2 | Sunnova Energy International | S.D. Tex. | 25-90160 | $8.9 billion | |
| 3 | Ligado Networks | D. Del. | 25-10006 | $8.6 billion | Hand-corrected from $8.9 billion (a 2020 figure) |
| 4 | Wolfspeed | S.D. Tex. | 25-90163 | $6.5 billion | |
| 5 | Signal National | N.D. Tex. | 26-90190 | $2.7 billion | |
| 6 | Pine Gate Renewables | S.D. Tex. | 25-90669 | $2.0 billion | Also a Track B case; tracks stay reported separately |
| 7 | Eddie Bauer | D.N.J. | 26-11422 | ~$1.7 billion | |
| 8 | F21 OpCo (Forever 21) | D. Del. | 25-10469 | $1.58 billion | |
| 9 | FAT Brands | S.D. Tex. | 26-90126 | $1.45 billion | |
| 10 | ModivCare | S.D. Tex. | 25-90309 | $1.42 billion | |

Next five: DocuData Solutions ($1.32 billion, S.D. Tex.), MLN US HoldCo / Marelli ($1.31 billion, S.D. Tex.), Office Properties Income Trust ($1.3 billion principal, S.D. Tex.), Del Monte Foods ($1.24 billion, D.N.J.), and Broadway Realty I ($1.1 billion, S.D.N.Y.).

## Things to weigh

1. **Venue skew.** Six of the top 10 are S.D. Tex., and S.D.N.Y., E.D. Va., and N.D. Ga. have none. A strict top 10 measures prevalence in the largest cases, which skew to Houston. An alternative is the top 10 with at least one case from each venue that has a qualifying case, at the cost of including smaller cases.
2. **Large cases missing from the ranking.** Spirit Aviation, Saks Global, At Home, New Rite Aid, Hughes Satellite, Azul, and Multi-Color have no first-day declaration in RECAP that matched the searches. These are likely large enough to rank, but their RECAP coverage looks thin, and the brief asks for census cases with good RECAP coverage. I propose leaving them out of the census and listing them as a known gap in the coverage report.
3. **Cost of phase 2.** Finding retention filings costs about 1 to 3 API requests per case (10 to 30 in total), and downloads are free. Under option 1 (application with exhibits plus the entered order), 10 cases should come to roughly 250 to 350 documents, inside the 400 cap.

## Decision needed

Approve the strict top 10 above, or the venue-balanced alternative.

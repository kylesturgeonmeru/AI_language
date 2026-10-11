# AI Provisions in Chapter 11 Engagement Letters: Benchmark Memo

**To:** Kyle Sturgeon | **Date:** 10/11/2026 | **Sources:** RECAP via CourtListener; see `data/coverage_report.md` for coverage and gaps

## Bottom line

AI language is rare in large-case chapter 11 retention filings, and where it appears it is inconsistent. In the census, 2 of 32 retention applications (6%) contain any AI provision. Full-text discovery across all cases in the seven venues found four firms that address their own AI use: AlixPartners, Latham & Watkins, Verita, and Deborah L. Crain / E-Merger Law. One audit letter (EY) addresses the client's AI use instead. MERU's draft clause is more complete than anything filed. It covers systems access, deal data, and liability, which no filed provision does. Its main gaps are an express ban on training its own models with client data, AI vendors' status under confidentiality, and court-filing obligations.

Every finding below rests on small numbers and on RECAP, which holds only documents someone bought or that were free. Treat the prevalence figures as directional.

## 1. Prevalence (Track A census)

Scope: every retention application in RECAP across the 63 chapter 11 cases in scope that state funded debt in a first-day declaration. That is 32 applications in 17 cases. 46 ranked cases had no retention application in RECAP, and RECAP held only 20 of 181 application and order documents for the 10 largest cases.

| Set | Applications | With AI provision |
|---|---|---|
| Primary: FA, committee FA, IB, CRO | 9 | 1 (AlixPartners) |
| Comparison: debtor and committee counsel | 11 | 1 (Latham, Pine Gate) |
| Secondary: claims agents, administrative advisor, OCP motions | 10 | 0 |
| Other: tax services, board counsel | 2 | 0 |
| **Total** | **32** | **2 (6%)** |

- **EL status matters.** Both provisions sit in attached engagement letters: 2 of 18 applications with an EL, 0 of 13 without one. When there is no EL, the application states the terms, and none mentions AI.
- **No investment banker or CRO** in the census (Lazard, PJT, Jefferies, Alvarez & Marsal, BRG, and Ankura) addresses AI. *Low confidence: 3 of each.*
- **Firms are not consistent across cases.** Latham's 07/2025 EL in Zen JV has no AI language; its 11/2025 EL in Pine Gate does. This suggests AI terms entered firm templates during 2025. *Low confidence: one firm.*
- **Claims agents:** Donlin Recano, Omni (two claims agent filings and one administrative advisor filing), Stretto, and Epiq in the census are silent; Verita's 07/2026 agreement (Track B) is not. *Low confidence.*

## 2. Content (Track B and census provisions)

Four firms address their own AI use. The elements they include:

| Element | Count (of 4) | Who |
|---|---|---|
| R1 Disclosure of use | 4 | All. Crain and Verita name tasks; AlixPartners and Latham are general. |
| R4 Confidentiality safeguards | 4 | All, but they diverge sharply (below). |
| R2 Human review or validation | 3 | Latham (lawyer review of all output), Crain (verifies cited case law), Verita (no automated decisions about individuals). |
| R8 Consent mechanism | 2 | Crain (consent by signing, unless the client objects in writing); Latham (consent only for matter-specific vendors). |
| R5 AI vendors as permitted recipients | 1 | Latham |
| R9 Client opt-out | 1 | Crain (written notice; no stated effect on fees) |
| R13 Firm rights to client data | 1 | AlixPartners (reserves training rights) |
| R3, R6, R7, R10, R11, R12 | 0 | No one addresses liability, systems access, MNPI, billing, court filings, or AI-specific incident notice. |

**Outliers**

- **AlixPartners (FA, Zen JV)** goes the other way: "AlixPartners may use Confidential Information (i) for benchmarking and related activities, and (ii) to train, enhance or test AlixPartners' Artificial Intelligence (AI) technologies to augment or enhance its services." Its only safeguards are a firewall and aggregated, anonymized output. It sits in the confidentiality section of the EL terms, not under an AI heading.
- **Latham** bars training only on "large language models ... made publicly available or hosted on open platforms," so private-model training is not addressed.
- **Verita** promises no training of "shared or third-party AI models," which is silent on its own models.
- **EY (At Home audit EL)** is client-side. Management must identify "the use of generative artificial intelligence" in preparing information for the audit, and failure "may cause us to delay our report, modify our procedures, or even terminate." Expect this in auditor ELs.

## 3. Court and U.S. Trustee treatment

One observable instance. In Zen JV the U.S. Trustee's comments on the AlixPartners order were resolved by a revised order that does not touch confidentiality or AI ("the U.S. Trustee does not object to the entry of the Revised Order"). The entered order approved the EL with its AI-training clause intact. For the other three provisions, the entered order is not in RECAP. *Low confidence: one case. No evidence yet that U.S. Trustees or courts scrutinize AI terms.*

## 4. Billing

No filing addresses how AI affects billed time or expenses (R10: 0 of 35 filings classified). Fee applications and fee examiner reports (optional Phase 5) were not reviewed.

## 5. Gap analysis: MERU's clause against the market

| Element | MERU draft | Filed market (n = 4) | Assessment |
|---|---|---|---|
| R1 Disclosure | General plus tasks (research, drafting, data analysis) | 4 of 4; 2 name tasks | In line |
| R2 Human review | Professional review and validation | 3 of 4 | In line |
| R3 Liability | Full responsibility for deliverables | 0 of 4 | **Ahead.** Unique; a selling point. |
| R4 Confidentiality | No tools that retain or train; enterprise-grade or vetted tools | 4 of 4, mostly weaker | Ahead of Latham and Verita, and the opposite of AlixPartners |
| R5 AI vendors as recipients | Not addressed expressly | 1 of 4 (Latham) | **Behind.** Confidentiality clauses usually list permitted recipients. |
| R6 Client systems access | Read-only, scoped, disconnect at end | 0 of 4 | **Ahead.** Unique. |
| R7 MNPI and deal data | Approved tools and workflows only | 0 of 4 | **Ahead.** Unique; matters for FA and IB work. |
| R8 Consent | Acknowledgment and consent | 2 of 4 | In line (similar to Crain) |
| R9 Opt-out | Per workstream, by written notice | 1 of 4 | In line; neither states the effect on fees or timing |
| R10 Billing | Silent | 0 of 4 | Market silent; optional addition |
| R11 Court filings | Silent | 0 of 4 | **Out of step for chapter 11 work.** Declarations and testimony are under oath, and some courts require AI certifications. |
| R12 Incident notice | Silent | 0 of 4 | Market silent; optional |
| R13 Firm use of client data | Implied by the no-retain/no-train tool rule, but MERU's own models and benchmarking are not addressed | 1 of 4 reserves rights | **Gap.** Make the no-training promise explicit and cover MERU's own models. |

## 6. Suggested redlines to `meru_clause.txt`

1. **R13 (explicit no-training, own models).** Add after the second sentence of paragraph 2: "MERU will not use Client's confidential or proprietary information to train, fine-tune, or benchmark any AI Tool or model, including any model developed or operated by MERU, without Client's prior written consent."
2. **R5 (vendors as permitted recipients).** Add: "Providers of AI Tools used in accordance with this paragraph may receive Client information only to the extent necessary to perform the Services and only under confidentiality and data protection obligations no less protective than those in this engagement letter."
3. **R11 (court filings).** Add: "MERU will comply with any court order, local rule, or chambers procedure requiring disclosure or certification of AI use, and MERU personnel will independently verify any AI-assisted content in declarations, reports, or testimony submitted in any proceeding."
4. **R9 (effect of opt-out).** Amend the last sentence: "...by providing written notice to MERU's engagement lead, and MERU will advise Client of any expected effect on timing or fees."
5. **Optional (R10 and R12).** Billing: "Fees reflect professional time actually incurred; AI Tool subscription and usage costs are MERU overhead and are not charged as expenses." Incident notice: "MERU will promptly notify Client if it becomes aware that Client confidential information was disclosed through an AI Tool other than as permitted by this engagement letter." Both go beyond the market; include them if they fit MERU's commercial posture.

## Confidence and next steps

- **Low confidence throughout.** The provisions come from 4 firms, court treatment from 1 case, and census prevalence from 32 RECAP filings in 17 cases.
- **Known gap, left open (Kyle, 10/11/2026).** The original top 10 cases' applications (78 documents on the Manual Pull List) are not in RECAP. All five claims agents are closed to automated retrieval: Kroll and Stretto block automated requests, Omni's robots.txt excludes Claude agents, Verita's TLS chain is broken, and Epiq's terms prohibit automated searches. A manual pull or a capped PACER budget remains possible later.
- **Optional Phase 5.** Search fee applications and examiner reports for AI time entries and charges.

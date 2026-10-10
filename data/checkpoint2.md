# Checkpoint 2: first 10 classifications (10/10/2026)

Ten filings are classified in `data/classify/results/` and validated by `classify.py validate`: every coded field carries an excerpt that appears verbatim in the source text. They cover the primary, comparison, and secondary sets. Two have no EL attached (M3 Advisory Partners and Richards, Layton & Finger, both in Zen JV).

| # | Case | Firm | Role | EL | AI provision | Track |
|---|---|---|---|---|---|---|
| 1 | Zen JV (D. Del.) | AlixPartners | FA | Y | Y | A and B |
| 2 | Pine Gate (S.D. Tex.) | Latham & Watkins | debtor counsel | Y | Y | A and B |
| 3 | Pacifica of the Valley (D. Del.) | Verita | claims agent | Y | Y | B |
| 4 | Alliance Farm and Ranch (S.D. Tex.) | Crain / E-Merger Law | special counsel | Y | Y | B |
| 5 | At Home (D. Del.) | Ernst & Young | tax and audit | Y | Y (client-side only) | B |
| 6 | Zen JV | PJT Partners | IB | Y | N | A |
| 7 | Pine Gate | Lazard | IB | Y | N | A |
| 8 | Pine Gate | Alvarez & Marsal | CRO | Y | N | A |
| 9 | Zen JV | M3 Advisory Partners | committee FA | **N** | N | A |
| 10 | Zen JV | Richards, Layton & Finger | debtor counsel | **N** | N | A |

## Sample 1: AlixPartners, Zen JV (primary set, FA)

The AI language sits in the confidentiality section of the EL terms, and it runs opposite to MERU's clause: it reserves the right to train the firm's AI on client data.

- **R13 (firm reserves rights to client data):** yes. "AlixPartners may use Confidential Information (i) for benchmarking and related activities, and (ii) to train, enhance or test AlixPartners' Artificial Intelligence (AI) technologies to augment or enhance its services."
- **R4 (confidentiality):** the only safeguards are a firewall and anonymized output. "Any such use will only be conducted behind a secure firewall, and any output from such activities will only be used on an aggregated and anonymized basis."
- **R1 (disclosure):** general, limited to the firm's own AI technologies.
- **R14 (court and UST treatment):** no objection to the AI terms. "The Revised Order has been circulated to the U.S. Trustee, and the U.S. Trustee does not object to the entry of the Revised Order." Neither the entered order (Dkt 263) nor the blackline (Dkt 250-2) touches confidentiality or AI.
- R2, R3, R5 to R12: silent.

## Sample 2: Latham & Watkins, Pine Gate (comparison set, debtor counsel)

The AI language sits in the EL's data privacy and vendor paragraph and treats AI as a feature of third-party software.

- **R1:** general. "SaaS services (which may include software that utilizes artificial intelligence (AI))".
- **R2 (human review):** yes. "all results from AI tools will be reviewed by qualified lawyers who are trained on the ethical and responsible use of AI".
- **R4:** no training of public models. "Your data will not be used to train any large language models ("LLMs") that are made publicly available or hosted on open platforms accessible to the general public". Training of private models is not addressed.
- **R5 (AI providers as permitted recipients):** yes. "All such vendors shall be subject to confidentiality and data security obligations and, where applicable, appropriate data processing terms."
- **R8 (consent):** separate consent only for matter-specific vendors.
- **R14:** not available, because the entered order (Dkt 694) is not in RECAP.

## Sample 3: Deborah L. Crain / E-Merger Law, Alliance Farm and Ranch (comparison set, special counsel)

This is the closest match to MERU's structure: named uses, verification, and consent with an opt-out.

- **R1:** specific tasks. "Client agrees and consents to the Firm using LLM systems, a form of Artificial Intelligence, for various legal and administrative functions, including but not limited to, drafting and editing, research assistance, and administrative support."
- **R2:** yes. "uses verification methods (like pulling case law cited to make sure that the case says what the AI said)".
- **R4:** "the Firm does not use any "open source" AI".
- **R8 and R9 (consent and opt-out):** consent by signing, with an opt-out by written notice ("Unless otherwise advised by the Client in writing"). No stated effect on fees.
- **R14:** not available.

## Calls for your review

1. **"Silent" versus "not available."** I added `not_available` for R14 when the entered order is not in RECAP, so a gap is never read as "no court treatment" (CLAUDE.md rule 8).
2. **At Home / EY.** The AI language is a client-side obligation in an audit EL: management must identify its own use of generative AI. I coded "AI provision present: Y" with every R field silent and a note. Alternatively it could be coded N as not addressing the firm's use. Your call.
3. **Verita's no-training promise** covers "shared or third-party AI models" only, so R13 is silent, not "no".
4. **Early prevalence signal (Track A, low confidence):** in the two census cases classified so far, 2 of 9 retentions (AlixPartners and Latham) contain AI language. Fewer than three cases; not a finding yet.

## Track A census status

The coverage census has found 3 qualifying cases so far (Pine Gate, JOANN, and Zen JV) through rank 28 of 63, after fixing a matching bug that missed every Delaware-style "Application/Motion to Employ/Retain" entry. It is resuming as the API budget frees up. If fewer than 10 of the 63 ranked cases qualify, I will report back with options rather than lower the bar.

## Next, on approval

Classify the remaining census filings as cases qualify, then build the coverage report and deliverables.

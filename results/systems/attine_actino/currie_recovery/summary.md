# Currie 1999 repeat-extraction diagnosis

The fixed Currie relation was missed in all three samples. The unchanged system prompt names Pseudonocardia, while the 1999 relation names Streptomyces and the corrigendum supplies only the family Pseudonocardiaceae. Samples 1 and 2 were empty; sample 3 selected that corrigendum family statement and repaired its printed line breaks, which made the quote ungrounded. The strict all-empty criterion is inapplicable because sample 3 surfaced a candidate.

| Sample | Candidate records | Grounded records | Fixed item recovered |
| --- | ---: | ---: | --- |
| 1 | 0 | 0 | no |
| 2 | 0 | 0 | no |
| 3 | 1 | 0 | no |

Each sample used the saved Currie-only payload, `single_quote_v1` grounding, unchanged attine prompt and schema, and `gemini-3.8-flash`. The original sample and positive-control score remain unchanged.
All three response envelopes replayed exactly from their raw HTTP caches with offline mode enabled.

## Source inspection

- Historical `Streptomyces` naming: present.
- Embedded-font glyph artifacts: present.
- Hyphenation across retained line breaks: present (23 instances).
- Complete producer–antibiotic–Escovopsis–inhibition relation in the abstract: present.
- Abstract block reached the adapter unchanged from the cached source: yes.

Candidate-level fields, validation outcomes, complete response envelopes, source diagnostics, and hashes are recorded in this directory.

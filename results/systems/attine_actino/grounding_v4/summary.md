# attine_actino: v4 grounding replay

The saved-proposal replay completed with **zero recoveries and zero lost records**.

| Measure | Count |
|---|---:|
| Saved response jobs replayed | 11 |
| Jobs with empty records arrays | 5 |
| Model candidates | 11 |
| Exact quotation matches | 11 |
| v4 control-glyph matches | 0 |
| Baseline full-validator acceptance | 10 |
| v4 full-validator acceptance | 10 |
| Prior semantic inclusions surviving | 5 |

All eleven proposed quotes match exactly. One proposal still fails the target-name check because its quote omits the claimed producer `Pseudonocardia`. The five prior semantic inclusions remain available. Currie returned an empty records array, and v4 has no proposed quote to validate there. Fixed reference recall remains 1/2: Oh recovered, Currie missing. The taxonomy filter result is unchanged.

## Scope and verification

This applies the existing `ground_quote_v4` matcher to the original single-quote system schema. Section, target-name, direction and confidence checks remain active. Quotes, source blocks, candidate identities, prompts and model responses are preserved. The full multi-span v4 schema and identity validator were not exercised; evaluating those requires multi-span model proposals.

No model or network calls occurred. A second local replay reproduced all 15 compared output files byte-for-byte. All 231 protected input and previous-result files retained their checksums, including the frozen primary files. The focused validation suite passed 162 tests, including 21 adapter tests. Taxonomy, chemistry and bioactivity were not rerun because the accepted record identities and prior semantic inclusions are unchanged.

[Machine-readable comparison](/Users/seth/Documents/ChatGPT/hackathon/results/systems/attine_actino/grounding_v4/comparison.json) · [Candidate-by-candidate audit](/Users/seth/Documents/ChatGPT/hackathon/data/interim/systems/attine_actino/grounding_v4/run/candidate_audit.jsonl) · [Recorded comparison protocol](/Users/seth/Documents/ChatGPT/hackathon/results/systems/attine_actino/grounding_v4/protocol.json)

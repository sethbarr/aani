# monarch: v4 grounding replay

The saved-proposal replay completed with **zero recoveries and zero lost records**.

| Measure | Count |
|---|---:|
| Saved response jobs replayed | 10 |
| Jobs with empty records arrays | 6 |
| Model candidates | 5 |
| Exact quotation matches | 5 |
| v4 control-glyph matches | 0 |
| Baseline full-validator acceptance | 5 |
| v4 full-validator acceptance | 5 |
| Prior semantic inclusions surviving | 2 |

All five candidate quotes already match exactly. The original two semantic inclusions remain available; the three previously excluded records retain their semantic problems. The missing infected-versus-uninfected comparison and the ancillary character of the water-treatment chemistry join are unchanged.

## Scope and verification

This applies the existing `ground_quote_v4` matcher to the original single-quote system schema. Section, target-name, direction and confidence checks remain active. Quotes, source blocks, candidate identities, prompts and model responses are preserved. The full multi-span v4 schema and identity validator were not exercised; evaluating those requires multi-span model proposals.

No model or network calls occurred. A second local replay reproduced all 14 compared output files byte-for-byte. All 284 protected input and previous-result files retained their checksums, including the frozen primary files. The focused validation suite passed 162 tests, including 21 adapter tests. Taxonomy, chemistry and bioactivity were not rerun because the accepted record identities and prior semantic inclusions are unchanged.

[Machine-readable comparison](/Users/seth/Documents/ChatGPT/hackathon/results/systems/monarch/grounding_v4/comparison.json) · [Candidate-by-candidate audit](/Users/seth/Documents/ChatGPT/hackathon/data/interim/systems/monarch/grounding_v4/run/candidate_audit.jsonl) · [Recorded comparison protocol](/Users/seth/Documents/ChatGPT/hackathon/results/systems/monarch/grounding_v4/protocol.json)

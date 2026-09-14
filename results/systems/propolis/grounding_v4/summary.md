# propolis: v4 grounding replay

The saved-proposal replay completed with **zero recoveries and zero lost records**.

| Measure | Count |
|---|---:|
| Saved response jobs replayed | 12 |
| Jobs with empty records arrays | 11 |
| Model candidates | 2 |
| Exact quotation matches | 0 |
| v4 control-glyph matches | 0 |
| Baseline full-validator acceptance | 0 |
| v4 full-validator acceptance | 0 |
| Prior semantic inclusions surviving | 0 |

Both proposals contain U+2011 in `phenolic-rich` where the cached source uses U+2010. Their declared section labels have the same printable-hyphen difference. The v4 policy permits non-whitespace C0 controls aligned to source `±` or `¼`; it excludes these printable substitutions. Both records still fail grounding, and neither enters semantic review.

## Scope and verification

This applies the existing `ground_quote_v4` matcher to the original single-quote system schema. Section, target-name, direction and confidence checks remain active. Quotes, source blocks, candidate identities, prompts and model responses are preserved. The full multi-span v4 schema and identity validator were not exercised; evaluating those requires multi-span model proposals.

No model or network calls occurred. A second local replay reproduced all 16 compared output files byte-for-byte. All 230 protected input and previous-result files retained their checksums, including the frozen primary files. The focused validation suite passed 162 tests, including 21 adapter tests. Taxonomy, chemistry and bioactivity were not rerun because the accepted record identities and prior semantic inclusions are unchanged.

[Machine-readable comparison](/Users/seth/Documents/ChatGPT/hackathon/results/systems/propolis/grounding_v4/comparison.json) · [Candidate-by-candidate audit](/Users/seth/Documents/ChatGPT/hackathon/data/interim/systems/propolis/grounding_v4/run/candidate_audit.jsonl) · [Recorded comparison protocol](/Users/seth/Documents/ChatGPT/hackathon/results/systems/propolis/grounding_v4/protocol.json)

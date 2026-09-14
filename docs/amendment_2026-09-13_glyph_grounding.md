# 2026-09-13 — glyph-only grounding development experiment

This amendment adds an isolated `multispan_v3` comparison mode. The analysis plan and analysis configuration remain frozen at `98b5e09199a5eef0c46be452793e953f5a2af31e`. Thresholds, unanimity, assay eligibility, the 25-genus feasibility gate, reference directions, and unknown activity labels are unchanged. These extraction outputs do not enter the biological join or change its feasibility-failure label.

## Evidence and scope

The saved Gemini response bytes contain U+0001 in positions where the cached source has ±, and U+0003 where the source has ¼. All nine source blocks survive export and decoded request JSON exactly. Saved request descriptors and a labeled HTTPX serialization reconstruction establish the request-side evidence; an outbound wire capture is unavailable. Full hashes, byte offsets, and all affected candidate spans are in `results/grounding_development_v3/byte_forensics.json`.

The validator permits only those two one-way character equivalences after the existing whitespace-normalized exact comparison fails. The policy is limited to `SAVERSCHEK2010`, block `b00005`, and its recorded SHA256. A fallback needs one unique alignment and exact equality of every other character. Source text and raw response quotes stay unchanged. Pre-existing source control characters continue to match exactly. Raw candidate digests remain stable.

Every candidate has a comparison ledger in `glyph_grounding_audit.jsonl`; survivors also carry per-span source coordinates, emitted and matched source quotes, the route, and each substituted code point. The existing v2 identity, plant-name, required-span, section, and confidence checks run on internally matched source quotes. The model prompt, schema, chunks, identity context, and provider serialization are unchanged. The default, v1, and v2 modes remain available unchanged.

## Measurement

The v3 rerun replays the original three v2 API responses offline. This keeps all 26 proposals fixed and isolates the validator change. A separately labeled v2 repeat makes one fresh request for each of the same three jobs in `data/raw/grounding_v3_repeat`; its outputs are scored independently and never pooled or selected for the main comparison. No fresh v3 model sample is drawn.

Scoring uses the baseline structured-direction convention on species-direction pairs. PRIMARY has six species; CONTEXT has five species with ten direction pairs, reported as both directions, collapsed to one, or absent. Counts and all eleven reference species are retained. This DEVELOPMENT SET is one panel from one paper, implementers know its reference, and it is not a sample from any population. Table-derived labels retain the original warning that the transcription was never visually checked against the PDF.

The curator matrix and extractor share source text, so shared blind spots would inflate apparent recall. The curator saw complete cached text including tables; extraction operated chunk-wise under strict quote constraints. Matching a structured direction does not adjudicate whether each table row and caption supports that direction semantically. No additional scoring convention is introduced.

## Reproduction

```shell
.venv/bin/python -m scripts.extract --provider gemini --grounding multispan_v3 --corpus data/interim/corpus_targeted_saverschek --export data/interim/extraction_jobs_saverschek_multispan_v3
.venv/bin/python -m scripts.extract --provider gemini --model gemini-3.8-flash --grounding multispan_v3 --corpus data/interim/corpus_targeted_saverschek --output data/interim/extraction_saverschek_multispan_v3 --offline
.venv/bin/python -m scripts.compare_grounding_v3 --repeat data/interim/extraction_saverschek_multispan_v2_repeat_for_v3
.venv/bin/python -m scripts.verify_grounding_v3
```

The verification report records original-file preservation, the frozen-file checks, and byte-identical offline scientific outputs for v3 and the completed repeat. The separate repeat cache must be retained to replay that sample.

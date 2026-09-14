# 2026-09-13 — v6 cache-side control grounding

This amendment precedes the v6 implementation. The task starts at 2026-09-13 19:20:05 UTC and ends at 20:50:05 UTC, a 90-minute wall-clock limit. Sample 4 must be drawn and scored within that interval. If the deadline is reached first, stop new sampling and report only the available development-set results with an explicit blocked reason.

## Rule and scope

V6 is additive through `--grounding multispan_v6`. The existing v4 and v5 modes, validators and policies remain selectable and unchanged. Quote comparison follows this order: existing whitespace-normalized exact match; existing v4 model-control inference; existing v5 printable-confusable inference; then the new cache-side inference. V5 section handling remains unchanged. The new class applies only to evidence quotes.

The new route permits exactly one differing position in a unique equal-length normalized alignment. At that position the cached text must contain a non-whitespace C0 control, and the model must contain a single printable, non-whitespace character. To protect numeric and direction content, the replacement must be Unicode punctuation or a symbol; letters, marks and all numeric categories are excluded. A cached control aligned to a digit or a letter within a direction word must fail. Every other normalized character must agree exactly, and a second differing position must fail. Insertions, deletions and mixed-class repairs within this new route are excluded.

Require the same literal printable anchor guard on both sides as v4, applied in the mirrored orientation to the cached control. Bind the source ID and exact cached block hashes in each job before hashing that job. Require a unique permitted alignment. Preserve prior ordered failures if earlier routes failed a safety guard, including ambiguous alignment or conflicting mappings; cache-side inference may proceed after an ordinary ungrounded quote failure.

Mappings are candidate-local. Existing emitted-to-cached mappings retain the v4/v5 consistency rule. Cache-side substitutions also require each cached control to map consistently to one emitted printable character across the record's spans. Conflicting mappings fail. Exact literal matches do not infer mappings. No map carries into another candidate, job or sample.

Every substitution logs both characters and Unicode code points, the model offset, the raw cached-source offset, the containing source span and block hash, and the route used. Preserve raw model proposals, original quotes and record digests. Only a temporary comparison copy contains matched cached text. Run the existing v2 identity, plant-name, span and confidence checks afterward. No source cache is rewritten and no intended PDF glyph is inferred.

This change leaves provider request descriptors, prompts, schema, required spans, chunks and source-identity context unchanged. The frozen files `docs/analysis_plan.md` and `config/analysis.json` remain byte-identical to commit `98b5e09199a5eef0c46be452793e953f5a2af31e`. Thresholds, unanimity, eligibility, unknown activity and the 25-genus feasibility gate are unchanged. No biological join or enrichment finding is part of this task.

## Regression and held-out protocol

Replay all saved samples 1, 2 and 3 offline under v6, preserving all existing artifacts. Require zero losses among previously surviving v4 and v5 records and zero changes to their structured directions. Sample 3 informed this rule and is explicitly DEVELOPMENT-SET evidence for v6. Synthetic adversarial cases must reject a cached control aligned to a changed digit, a changed direction word, or two differing positions; also test ambiguity, anchors, source binding and cross-span conflicts.

Before sample 4, save the complete rule, dependency, configuration and request hashes and recovery copies of the shared runner files. Draw exactly one new sample from the original three v2 request descriptors and source-identity context into a separate HTTP cache. Permit one network attempt per job, with no retries. Record unsuccessful attempts and incomplete jobs explicitly. Reserve time for scoring before the deadline; do not initiate a draw that cannot reasonably finish in time.

Validate the saved sample-4 proposals under the frozen v6 rule and save scores before anyone inspects candidate failures. Use the unchanged baseline structured-direction convention, keeping PRIMARY six species-direction pairs separate from CONTEXT five species and ten pairs. Report detection, survival, correctness and candidate stage yield as counts. Retain every denominator and explicit unscorable reasons. After scores are saved, classify every first ordered rejection and record any observed unsupported character mismatch. Make no rule, guard, prompt, schema or context changes after observing sample 4. Verify offline replay and report all samples without selection or pooling.

## Interpretation

This is one development panel from one paper; implementers know the reference. It is not a sample from any population. Samples 1–3 are development data for v6. Sample 4 is a held-out model draw under the frozen rule; it provides no unseen-paper estimate. The curator matrix used the same cached text blocks as the extractor, so shared blind spots can inflate apparent recall. The curator saw the complete cache including tables; the original extractor worked chunk-wise under a strict quote constraint. The numerical table transcription was never visually verified against the PDF, so table-derived labels remain weaker ground truth. Structured-direction correctness does not add a semantic adjudication gate.

Results go to `results/grounding_development_v6/summary.md` and, if sample 4 is drawn, `heldout_sample4_summary.md`. Preserve all previous results and record any blocker explicitly. This task writes files and does not commit.

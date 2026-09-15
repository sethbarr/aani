# V4 on a held-out model draw: sample 3

V4 does not fully generalise to this untouched draw: seven records fail where cached U+0002 is rendered as ASCII hyphen U+002D, leaving CONTEXT survival and correctness at 5 of 10 pairs.

This is a DEVELOPMENT SET: one panel from one paper, with a reference known to the implementers. The panel is not a sample from any population. Samples 1 and 2 informed the v4 rule. Sample 3 was held out from rule development; unseen-paper performance remains untested.

## PRIMARY — six species-direction pairs

| Sample 1: v4 | Sample 2: v4 | Sample 3: v4, held out |
| --- | --- | --- |
| Detection: 6 of 6 | Detection: 6 of 6 | Detection: 6 of 6 |
| Survival: 6 of 6 | Survival: 6 of 6 | Survival: 6 of 6 |
| Correctness: 6 of 6 | Correctness: 6 of 6 | Correctness: 6 of 6 |

## CONTEXT — five species, ten species-direction pairs

Coverage counts below are **both directions / collapsed to one / absent**.

| Sample 1: v4 | Sample 2: v4 | Sample 3: v4, held out |
| --- | --- | --- |
| Detection: 10 of 10; coverage 5 / 0 / 0 | Detection: 9 of 10; coverage 4 / 1 / 0 | Detection: 10 of 10; coverage 5 / 0 / 0 |
| Survival: 10 of 10; coverage 5 / 0 / 0 | Survival: 9 of 10; coverage 4 / 1 / 0 | Survival: 5 of 10; coverage 2 / 1 / 2 |
| Correctness: 10 of 10; coverage 5 / 0 / 0 | Correctness: 9 of 10; coverage 4 / 1 / 0 | Correctness: 5 of 10; coverage 2 / 1 / 2 |

All 11 species are scorable in each sample. Sample 3 loses both directions for Inga goldmanii and Tetragastris panamensis, plus accepted Trichilia tuberculata, during grounding. PRIMARY and CONTEXT remain separate throughout.

## Candidate stage yield

| Sample 1: v4 | Sample 2: v4 | Sample 3: v4, held out |
| --- | --- | --- |
| 23 of 26 | 18 of 18 | 13 of 24 |

Stage yield includes outside-panel proposals. Correctness uses the unchanged baseline structured-direction matching convention: a surviving species and outcome must match the fixed reference pair. This run adds no semantic-review gate and pools no proposals across samples.

## Sample-3 rejections

Every rejected record retains its first ordered validator failure. Later gates remain unadjudicated.

| Ordered reason | Records | Classification |
| --- | --- | --- |
| `ungrounded_quote` | 7 | `other`: unsupported cached-control-to-ASCII rendering |
| `invalid_exact_name_link` | 1 | identity |
| `unabbreviated_genus_required` | 2 | identity |
| `name_surface_not_in_quote` | 1 | name surface |
| Total | 11 | 7 other; 3 identity; 1 name surface |

All seven quote failures print `habitat-related` where the cache contains `habitat\u0002related`: model U+002D, UTF-8 byte `2d`; cached U+0002, byte `02`. Each has a unique equal-length source alignment with exactly one differing character. The mismatch is at raw Unicode-code-point offset 4321 in block `b00003`, SHA-256 `e1908cad9b1c86f10c3ccaaaecfdcdba8c937d721b6b383933344882ac0efc94`.

These seven records are Inga accepted and rejected; Tetragastris accepted and two rejected proposals; and Trichilia accepted and rejected. The three identity failures concern Stigmaphyllon, outside the reference panel. The name-surface failure concerns one Hymenaea rejected proposal; another surviving proposal retains that pair.

The predeclared diagnostic reports 0 unresolved model-control-to-printable substitutions and 0 printable-Unicode substitutions. Its attribution scope excludes this cached-control-to-ASCII case, so the original `other: 7` classification is preserved. The supplemental evidence records the exact mismatch without inferring the intended PDF glyph or changing the rule. Full record IDs, proposal indices, quotes and offsets are in [the ordered audit](heldout_failures.json) and [the supplemental byte evidence](heldout_cached_control_evidence.json).

## Sampling and replay integrity

Three model calls completed, one per original v2 job, with 0 retries. Every request descriptor and source-identity context matches the earlier samples. A separate sample-3 HTTP cache holds response bytes distinct from both earlier samples for each job. Scores were saved before failure inspection. The v4 policy, guards, prompts, schema, chunks and reference labels were unchanged for this test.

The initial replay attempt stopped before execution because concurrent v5 work changed `scripts/extract.py` and `src/extraction/pipeline.py` after scoring. Those live edits were preserved. Separate copies of both runners were recovered and verified against their exact pre-draw SHA-256 hashes. The isolated offline replay used those copies with the unchanged v4 dependencies: all 13 scientific artifacts match byte for byte, and baseline-convention counts match. Replay made 0 model requests. The other 313 protected files remain unchanged; all 315 replay inputs match their pre-draw hashes. Both scientific protocol files still match commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.

The [initial blocked check](heldout_verification.json) and [successful frozen-code replay](heldout_frozen_verification.json) are both preserved. The [pre-draw protocol](heldout_protocol.json), [sampling log](heldout_sampling.json), and [saved scores](heldout_scores.json) establish the run order and provenance.

All 189 focused transport, scoring, diagnostic, recovery-guard and v4 grounding tests passed. Ruff passed for the new held-out code and tests.

## Reference limitations

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. Directions were checked against Table 1 of the original PDF and follow the authors' printed headings, so these are author-assigned groupings rather than inferences from numerical signs. What remains unverified is the semantic support for individual rows and captions.

# V4 source-anchored control glyphs — DEVELOPMENT SET

V4 infers a corrupted control character's cached glyph from a unique source span. The model-side codes can vary across records and samples. Cached targets remain limited to ± and ¼, and every other character must match exactly.

## Two saved samples, unchanged proposals

All three jobs from each sample were processed offline, with zero model requests. Requests, raw proposals, prompts, schema, identity context, and chunks are unchanged. Correctness uses the baseline structured-direction convention.

### PRIMARY — six species-direction pairs

| Sample 1: v3 | Sample 1: v4 | Sample 2: v3 | Sample 2: v4 |
| --- | --- | --- | --- |
| Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs |
| Survival: 6 of 6 species; 6 of 6 pairs | Survival: 6 of 6 species; 6 of 6 pairs | Survival: 1 of 6 species; 1 of 6 pairs | Survival: 6 of 6 species; 6 of 6 pairs |
| Correctness: 6 of 6 species; 6 of 6 pairs | Correctness: 6 of 6 species; 6 of 6 pairs | Correctness: 1 of 6 species; 1 of 6 pairs | Correctness: 6 of 6 species; 6 of 6 pairs |

### CONTEXT — five species, ten species-direction pairs

| Sample 1: v3 | Sample 1: v4 | Sample 2: v3 | Sample 2: v4 |
| --- | --- | --- | --- |
| Detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Detection: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | Detection: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 |
| Survival: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Survival: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Survival: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Survival: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 |
| Correctness: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Correctness: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Correctness: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Correctness: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 |

### Candidate stage yield

| Sample 1: v3 | Sample 1: v4 | Sample 2: v3 | Sample 2: v4 |
| --- | --- | --- | --- |
| 23 of 26 | 23 of 26 | 6 of 18 | 18 of 18 |

## Recovered records and remaining failures

- sample1: 0 newly surviving records, 23 previous survivors retained, 0 previous survivors lost.
- sample2: 12 newly surviving records, 6 previous survivors retained, 0 previous survivors lost.
- sample1 remaining rejection reasons: `name_surface_not_in_quote`: 1; `unabbreviated_genus_required`: 2.
- sample2 remaining rejection reasons: zero rejected records.
- sample2 missing structured proposals: Miconia argentea — rejected. Grounding preserves this detection gap.

## Inferred glyph routes

Mappings below are read from source matches and are local to each candidate. They are not a global replacement table.

sample1: 13 surviving records use the glyph route; 10 use exact matching.

- `U+0001` → `U+00B1`: 11 records, 28 span occurrences.
- `U+0003` → `U+00BC`: 2 records, 2 span occurrences.

sample2: 12 surviving records use the glyph route; 6 use exact matching.

- `U+0010` → `U+00BC`: 5 records, 5 span occurrences.
- `U+0011` → `U+00B1`: 7 records, 18 span occurrences.

## Guardrails and generalization checks

The fallback accepts only non-whitespace C0 controls aligned to cached ± or ¼, with literal printable context on both sides and one unique equal-length source match. Conflicting mappings within a record fail. Insertions, deletions, other cached glyphs, and changed digits, signs, words, or direction statements remain rejected. Existing literal source controls remain exact.

Every job binds its own source ID and block hashes, so the rule has no fixed Saverschek identifier. Raw quotes and record digests stay unchanged. Each match logs source offsets, original text, cached text, and inferred substitutions.

Synthetic check status: complete; 91 of 91 expectations passed. [generalization_checks.json](generalization_checks.json) records exhaustive non-whitespace C0 probes for the two permitted cached glyphs, using invented text and an unrelated source ID, plus adversarial rejections. These are algorithm checks and contain zero model samples.

Offline replay status: passed; 235 protected files checked. [verification.json](verification.json) records identical response/proposal identities, scientific replay bytes, and unchanged frozen files at `98b5e09`.

## Scope of the result

The generalized rule covers the glyph failures observed in both saved samples. Its remaining source-glyph scope is ± and ¼; other Unicode and OCR errors are outside this implementation.

Both existing samples informed development of the generalized glyph rule. Neither sample is an independent test of that rule. Both samples are reported separately, with every raw proposal retained.

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. Implementers know the reference. This is one panel from one paper and is not a sample from any population.

The numerical table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. Reference labels remain unchanged.

This DEVELOPMENT SET is one panel from one paper and is not a sample from any population. Semantic support of table-derived directions remains unadjudicated. The default extractor and all earlier validators are preserved; select `--grounding multispan_v4` to use this mode. The biological feasibility-failure label is unchanged.

The rule and reproduction commands are documented in [the dated amendment](../../docs/amendment_2026-09-13_generalized_glyph_grounding.md).

Blocked reason: none.

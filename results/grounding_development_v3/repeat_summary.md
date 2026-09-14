# Repeat sample under unchanged v3 rules — DEVELOPMENT SET

The saved sample 2 proposals were processed with the unchanged v3 validator and glyph policy, offline with zero model requests. Within each sample, both rule sets use the same request hashes and raw proposals. Both samples are reported separately; none of their records are pooled or selected across draws.

This DEVELOPMENT SET is one panel from one paper, implementers know the reference, and it is not a sample from any population. Correctness uses the unchanged baseline structured-direction convention.

## PRIMARY — six species-direction pairs

| Sample 1: v2 rules | Sample 1: v3 rules | Sample 2: v2 rules | Sample 2: v3 rules |
| --- | --- | --- | --- |
| Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs | Detection: 6 of 6 species; 6 of 6 pairs |
| Survival: 4 of 6 species; 4 of 6 pairs | Survival: 6 of 6 species; 6 of 6 pairs | Survival: 1 of 6 species; 1 of 6 pairs | Survival: 1 of 6 species; 1 of 6 pairs |
| Correctness: 4 of 6 species; 4 of 6 pairs | Correctness: 6 of 6 species; 6 of 6 pairs | Correctness: 1 of 6 species; 1 of 6 pairs | Correctness: 1 of 6 species; 1 of 6 pairs |

## CONTEXT — five species, ten species-direction pairs

Both means both directions surfaced; collapsed means one direction surfaced. Each cell retains absent and unscorable species explicitly.

| Sample 1: v2 rules | Sample 1: v3 rules | Sample 2: v2 rules | Sample 2: v3 rules |
| --- | --- | --- | --- |
| Detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Detection: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | Detection: both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 |
| Survival: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Survival: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Survival: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Survival: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |
| Correctness: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Correctness: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | Correctness: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | Correctness: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |

## Candidate stage yield

| Sample 1: v2 rules | Sample 1: v3 rules | Sample 2: v2 rules | Sample 2: v3 rules |
| --- | --- | --- | --- |
| 10 of 26 | 23 of 26 | 6 of 18 | 6 of 18 |

## Sample 2 failures under v3

Each record is classified by its first returned reason in validator order. Later gates are not adjudicated after an earlier rejection.

- Glyph substitution outside the two pinned equivalences: 12 records.
- Identity: 0 records.
- Name surface: 0 records.
- Other: 0 records.

Observed, unpermitted substitutions in the first-failing spans:

- Emitted `U+0010` replaces cached `U+00BC` (¼): 5 records, 5 character occurrences.
- Emitted `U+0011` replaces cached `U+00B1` (±): 7 records, 18 character occurrences.

The diagnostic establishes a unique source match with every other whitespace-normalized character unchanged. These observed substitutions were never applied to the validator, proposals, or scores. The permitted policy remains U+0001→± and U+0003→¼ in the original hash-pinned table block.

### Every failed record, in proposal order

Indices are zero-based. Full raw candidate hashes, response hashes, original quotes, source offsets, and UTF-8 evidence are in [repeat_failures.json](repeat_failures.json).

| Chunk:record | Species | Direction | First ordered failure | Observed substitution |
| --- | --- | --- | --- | --- |
| 1:0 | Spondias mombin | accepted | `supporting_evidence[1]:ungrounded_quote` | U+0010→U+00BC |
| 1:2 | Hiraea grandifolia | rejected | `supporting_evidence[0]:ungrounded_quote` | U+0010→U+00BC |
| 1:3 | Randia armata | rejected | `supporting_evidence[0]:ungrounded_quote` | U+0010→U+00BC |
| 1:4 | Sorocea affinis | rejected | `supporting_evidence[0]:ungrounded_quote` | U+0010→U+00BC |
| 1:5 | Trema micrantha | rejected | `supporting_evidence[0]:ungrounded_quote` | U+0010→U+00BC |
| 1:6 | Hymenaea courbaril | rejected | `supporting_evidence[0]:ungrounded_quote` | U+0011→U+00B1 |
| 1:9 | Inga goldmanii | accepted | `ungrounded_quote` | U+0011→U+00B1 |
| 1:10 | Inga goldmanii | rejected | `ungrounded_quote` | U+0011→U+00B1 |
| 1:11 | Tetragastris panamensis | accepted | `ungrounded_quote` | U+0011→U+00B1 |
| 1:12 | Tetragastris panamensis | rejected | `ungrounded_quote` | U+0011→U+00B1 |
| 1:13 | Trichilia tuberculata | accepted | `ungrounded_quote` | U+0011→U+00B1 |
| 1:14 | Trichilia tuberculata | rejected | `ungrounded_quote` | U+0011→U+00B1 |

## Cross-sample verdict

The pinned v3 fix fails to generalize across these two samples: sample 2 gains zero survivors and retains 12 failures caused by different, unpermitted glyph substitutions.

All observed sample 2 rejections are glyph failures at the first failing gate; this run makes no claim that later identity or name checks would pass after a future repair.

## Preservation and limits

Offline replay: passed. Protected files checked: 206. [repeat_verification.json](repeat_verification.json) records identical scientific output bytes, unchanged source caches and validators, the identical glyph policy, and frozen-file checks against `98b5e09`.

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. Implementers know the reference. This is one panel from one paper and is not a sample from any population.

The numerical table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. Reference labels remain unchanged.

Structured-direction agreement leaves the semantic interpretation of table rows and captions unadjudicated. The biological feasibility-failure label is unchanged.

Blocked reason: none.

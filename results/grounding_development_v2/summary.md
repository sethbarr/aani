# Source-level ant identity — DEVELOPMENT SET

V2 PRIMARY survival and correctness are **4 of 6**, above the baseline **2 of 6**.
The single approved three-job run produced 26 candidates, ten grounding passes
and 16 failures; each job made one API attempt.

V2 adds source-wide ant identity and same-block supporting plant-name links;
the dominant remaining failure is exact table-glyph copying, affecting 13 of
16 rejected records: ten supporting spans and three primary quotes.

This development set is one panel from one paper, is not a sample from any
population, and its reference is known to the implementers. Every column uses
baseline structured-direction matching for correctness. All 11 species are scorable.

## PRIMARY

The denominator is six species and six species-direction pairs.

| baseline | v1 | v2 |
| --- | --- | --- |
| Detection: 6 of 6 | Detection: 2 of 6 | Detection: 6 of 6 |
| Survival: 2 of 6 | Survival: 0 of 6 | Survival: 4 of 6 |
| Correctness: 2 of 6 | Correctness: 0 of 6 | Correctness: 4 of 6 |

Desmopsis rejection is retained; Randia, Sorocea and Trema rejection are gained.
Spondias acceptance is lost versus baseline. Spondias and Hiraea both fail a
supporting table caption's exact-quote check.

## CONTEXT

Each row classifies five species as both directions surfaced, collapsed to one,
or absent; the pair denominator is ten.

| baseline | v1 | v2 |
| --- | --- | --- |
| Detection: both 0; one 4; absent 1 | Detection: both 1; one 1; absent 3 | Detection: both 5; one 0; absent 0 |
| Survival: both 0; one 1; absent 4 | Survival: both 0; one 0; absent 5 | Survival: both 1; one 1; absent 3 |
| Correctness: both 0; one 1; absent 4 | Correctness: both 0; one 0; absent 5 | Correctness: both 1; one 1; absent 3 |

Detected pairs are baseline 4 of 10, v1 3 of 10, v2 10 of 10.
Surviving/correct pairs are baseline 1 of 10, v1 0 of 10, v2 3 of 10.
V2 retains both Miconia directions and Hymenaea rejection.

## Diagnosis and checks

Identity resolves to `Atta colombica` from `b00000`; all ten survivors record
`source_identity_full_name`, with zero ant-identity failures. Hymenaea's pronoun
record uses `supporting_evidence[0]` in `b00003` for its plant name.

The 13 quote failures copy `\u0001` in place of cached `±` in eleven rows,
or `\u0003` in place of cached `\u00bc` in two captions. The other failures
are two abbreviated full-name plant anchors and one missing plant-name surface,
all outside the panel. Original quotes and glyphs remain unchanged.

PRIMARY detection returned to six of six with the schema, required spans, table
instructions and chunks unchanged. One sample per variant cannot separate the
identity-context effect on proposals from sampling variability. The separate
saved-v1-candidate diagnostic recovers six of seven records and PRIMARY two of six.

Offline replay passed for baseline, v1 and v2, with nine, nine and ten exact
artifact comparisons. V1's previously documented full-name hardening changes
one rejection reason; its first-run response bytes and counts match.
All 61 protected files and frozen protocol files are unchanged. Tests:
223 passed, one pre-existing missing experiment-planner template failure;
scoped Ruff passed.

Reference provenance remains six author_prose and five author_table_grouping species
(PRIMARY two/four; CONTEXT four/one). The table transcription was never visually
verified against the PDF. Correctness measures label agreement; semantic-review
flags remain. Curator and extractor share cached text, so shared blind spots
could inflate recall; the curator saw complete text including tables, while
the original extractor worked chunk-wise under a strict quote constraint.

The debugging review isolated glyph-copy failures; data checks preserved scoring
and denominators. No new record entered the biological join. The feasibility
failure, frozen rules and unknown-activity handling remain unchanged.

See [comparison data](compare.json), [saved-candidate diagnostic](saved_candidate_diagnostic.json),
[offline replay](verification.json), [run status](run_status.json), and
[dated amendment](../../docs/amendment_2026-09-13_source_ant_identity.md).

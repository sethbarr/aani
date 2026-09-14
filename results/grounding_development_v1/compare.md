# Grounding development comparison — DEVELOPMENT SET

This is one panel from one paper and is not a sample from any population. PRIMARY has six species-direction pairs across six species. CONTEXT has ten pairs across five species. The groups retain their separate denominators.

| Run / stage | PRIMARY species | PRIMARY pairs | CONTEXT both | CONTEXT collapsed | CONTEXT absent | CONTEXT unscorable | CONTEXT pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline detection | 6 of 6 | 6 of 6 | 0 of 5 | 4 of 5 | 1 of 5 | 0 of 5 | 4 of 10 |
| Baseline survival | 2 of 6 | 2 of 6 | 0 of 5 | 1 of 5 | 4 of 5 | 0 of 5 | 1 of 10 |
| Baseline correctness | 2 of 6 | 2 of 6 | 0 of 5 | 1 of 5 | 4 of 5 | 0 of 5 | 1 of 10 |
| Development detection | 2 of 6 | 2 of 6 | 1 of 5 | 1 of 5 | 3 of 5 | 0 of 5 | 3 of 10 |
| Development survival | 0 of 6 | 0 of 6 | 0 of 5 | 0 of 5 | 5 of 5 | 0 of 5 | 0 of 10 |
| Development correctness | 0 of 6 | 0 of 6 | 0 of 5 | 0 of 5 | 5 of 5 | 0 of 5 | 0 of 10 |

The completed development run has zero surviving panel candidates. Its correctness counts are zero because no candidate survived grounding. Surviving-record semantic adjudication was unnecessary and was not performed; diagnostic source review of rejected records is recorded separately.

Detection counts any raw candidate bearing the species name. Survival counts candidates that passed grounding. Development correctness counts independently reviewed records with matching species, direction and natural-panel context; each review cites exact cached source anchors. The saved baseline correctness counts remain unchanged and used structured-direction matching. This difference in review depth limits direct correctness comparisons. Automatic direction matches appear separately in JSON as provisional. An additional direction in a quote receives credit only when emitted as its own structured outcome.

| Species | Group | Reference | Detected | Survived | Reviewed correct directions | Correctness status |
| --- | --- | --- | --- | --- | --- | --- |
| Desmopsis panamensis | PRIMARY | rejected | True | False | absent | scored |
| Hiraea grandifolia | PRIMARY | rejected | False | False | absent | scored |
| Randia armata | PRIMARY | rejected | False | False | absent | scored |
| Sorocea affinis | PRIMARY | rejected | False | False | absent | scored |
| Trema micrantha | PRIMARY | rejected | False | False | absent | scored |
| Spondias mombin | PRIMARY | accepted | True | False | absent | scored |
| Hymenaea courbaril | CONTEXT | accepted, rejected | True | False | absent | scored |
| Inga goldmanii | CONTEXT | accepted, rejected | False | False | absent | scored |
| Tetragastris panamensis | CONTEXT | accepted, rejected | False | False | absent | scored |
| Trichilia tuberculata | CONTEXT | accepted, rejected | False | False | absent | scored |
| Miconia argentea | CONTEXT | accepted, rejected | True | False | absent | scored |

Reference provenance is unchanged: PRIMARY has 2 author_prose and 4 table_derived species; CONTEXT has 4 author_prose and 1 table_derived species. The numerical table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. All reference labels and provenance tags come directly from the saved baseline.

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. The reference was known during development, which adds direct development-set contamination. This run provides no independent generalization estimate.

The development inventory has 7 candidates, 0 grounding passes and 7 grounding failures. Candidate retention counts are stage yields. The broader nine-of-41 semantic-retention count is also a stage yield.

Original baseline artifacts and recorded inputs unchanged: True. JSON records the baseline commit, expected and observed hashes, development manifest, per-candidate semantic decisions and exact source anchors.

Comparison status: complete. Blocked reason: none.

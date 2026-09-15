# Saverschek recall baseline — DEVELOPMENT SET

This is one panel from one paper and is not a sample from any population. The unit is the species-direction pair: PRIMARY has six species with six pairs; CONTEXT has five species with ten pairs. The groups remain separate.

| Stage | PRIMARY species / pairs recovered | CONTEXT both directions | CONTEXT collapsed to one | CONTEXT absent | CONTEXT pairs recovered |
| --- | --- | --- | --- | --- | --- |
| detection | 6 of 6 | 0 of 5 | 4 of 5 | 1 of 5 | 4 of 10 |
| survival | 2 of 6 | 0 of 5 | 1 of 5 | 4 of 5 | 1 of 10 |
| correctness | 2 of 6 | 0 of 5 | 1 of 5 | 4 of 5 | 1 of 10 |

Detection means a candidate was proposed for the species; survival means a candidate passed the original grounding checks; correctness means a surviving structured outcome matches a reference direction. Direction coverage uses emitted outcome fields. Hymenaea's failed delayed-rejection record mentions acceptance in its quote, but its structured outcome is rejection, so acceptance receives no credit.

| Species | Group | Reference directions | Detection | Survival | Correct directions | Reference provenance |
| --- | --- | --- | --- | --- | --- | --- |
| Desmopsis panamensis | PRIMARY | rejected | True | True | rejected | author_prose |
| Hiraea grandifolia | PRIMARY | rejected | True | False | absent | author_table_grouping; printed Table 1 heading |
| Randia armata | PRIMARY | rejected | True | False | absent | author_table_grouping; printed Table 1 heading |
| Sorocea affinis | PRIMARY | rejected | True | False | absent | author_table_grouping; printed Table 1 heading |
| Trema micrantha | PRIMARY | rejected | True | False | absent | author_table_grouping; printed Table 1 heading |
| Spondias mombin | PRIMARY | accepted | True | True | accepted | author_prose |
| Hymenaea courbaril | CONTEXT | accepted, rejected | True | True | rejected | author_prose |
| Inga goldmanii | CONTEXT | accepted, rejected | True | False | absent | author_prose |
| Tetragastris panamensis | CONTEXT | accepted, rejected | True | False | absent | author_prose |
| Trichilia tuberculata | CONTEXT | accepted, rejected | True | False | absent | author_prose |
| Miconia argentea | CONTEXT | accepted, rejected | False | False | absent | author_table_grouping; printed Table 1 heading plus prose acceptance |

Reference provenance distinguishes explicit `author_prose` from the stronger `author_table_grouping`, which records species placed under a printed author heading in Table 1. PRIMARY has 2 `author_prose` and 4 `author_table_grouping` species; CONTEXT has 4 `author_prose` and 1 `author_table_grouping`. Overall this is 6 prose and 5 author-grouped species, or 11 prose and 5 author-grouped direction pairs. Miconia has prose acceptance and author-grouped rejection, so its species tag records `author_table_grouping`.

Reference directions were manually checked against Table 1 of the original PDF and follow its printed author headings: `Acceptance`, `Immediate rejection`, and `Habitat-related rejection`. These are author-assigned groupings; numerical signs do not determine directions. Semantic support for individual rows and captions remains unverified. Group/complement prose also supports these five labels: nine species except Spondias and Miconia were avoided on simultaneous day 2; all ten except Spondias were rejected in individual p-habitat tests. Miconia is grouped under `Immediate rejection` in Table 1 and accepted in both habitats in the simultaneous-choice tests, so it remains in CONTEXT. Reference directions and the 6 PRIMARY / 5 CONTEXT denominators stay fixed. Exact anchors and source hashes are in JSON.

Contamination risk: the curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the extractor worked chunk-wise under a strict quote constraint. This difference partly mitigates the risk, but both depend on the same source representation. Subsequent improvements measured here are development results.

Unscorable species: 0 of 6 PRIMARY; 0 of 5 CONTEXT. Every panel member remains in its denominator, including Trema under the original spelling. Outstanding taxonomy does not prevent scoring its extraction. Any unscorable row has a blocked_reason in JSON.

The existing inventory reconciles 14 candidates: 11 panel candidates and three outside this panel. The complete run has six grounding passes and eight failures; three passes concern this panel. Desmopsis and Spondias supply the two correct PRIMARY pairs. Hymenaea supplies one correct CONTEXT rejection pair. Miconia is absent from the candidates. These counts measure the original extraction, with curator records used only for reference labels. The broader nine-of-41 semantic-retention count is a stage yield.

Rebuild offline with `.venv/bin/python -m scripts.recall_baseline`. The JSON includes input hashes and record-level scoring. Extraction prompts, outputs and grounding rules are unchanged.

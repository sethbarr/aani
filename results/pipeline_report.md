# aani: end-to-end coverage run

Protocol: `98b5e09199a5eef0c46be452793e953f5a2af31e`.

| Stage | Count | Unit / status |
| --- | --- | --- |
| papers_retrieved | 33 | unique sources with cached full text; complete |
| screened_in | 13 | unique sources selected by any inclusion route; complete |
| extraction_jobs | 23 | model jobs; complete |
| candidate_records | 61 | original model candidates; complete |
| grounding_passed | 41 | original model candidates; complete |
| semantically_retained | 9 | original model records retained by source review; complete |
| names_resolved | 16 | distinct accepted species identities; complete |
| genera_after_aggregation | 10 | directionally consistent genera; complete |
| genera_with_chemistry | 8 | eligible genera with at least one imported occurrence; complete |
| genera_with_classified_compounds | 7 | eligible genera with at least one active or inactive compound; complete |
| genera_available_for_primary_test | 7 | joined genera available before the feasibility gate; complete |

The model branch is separate from curator recovery: 96 retained directional contexts before taxonomy, including source-following corrections and the complete Saverschek audit. These are not 96 model successes or independent observations.

Miconia verification: **conflict**; both accepted species identities and opposing directions were checked from records.

Primary status: **feasibility_failure**; estimable: **False**.

See `funnel.json` for cohort denominators, conflict counts, stage manifests, missingness and blocked reasons.

Chemistry used the verified LOTUS v4 export (Zenodo 6582121, CC BY 4.0), with version, download URL, retrieval time, checksum, licence and transform provenance in `data/processed/chemistry/run_manifest.json`.

Imported 27033 provenance rows / 3774 distinct occurrences / 2183 structures across the full audited genus scope.

ChEMBL retrieved 2183 structures: 7 active, 17 inactive and 2159 unknown; 0 retrieval failures. Unknowns are excluded from the classified denominator.

The primary join contains 6 accepted and 1 rejected genera. Inference blockers: fewer_than_minimum_joined_genera, need_two_genera_per_direction, lme4_unavailable. All unavailable endpoints remain null; no substitute model or shortlist was produced.

Missing chemistry is reported for Desmopsis and Hiraea. Randia has 12 mapped structures but zero classified compounds and is excluded. These are different missingness states.

Original data and frozen protocol files remain intact. `results/offline_replay.json` records the completed offline replay checks; README and the pipeline guide describe the runnable chain.

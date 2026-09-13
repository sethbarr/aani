# aani — day-two baseline and blockers

| Stage | PRIMARY | CONTEXT both / collapsed / absent | CONTEXT pairs |
| --- | --- | --- | --- |
| detection | 6 of 6 | 0 / 4 / 1 of 5 | 4 of 10 |
| survival | 2 of 6 | 0 / 1 / 4 of 5 | 1 of 10 |
| correctness | 2 of 6 | 0 / 1 / 4 of 5 | 1 of 10 |

This DEVELOPMENT SET is one panel from one paper and is not a sample from any population. All eleven species are scorable. Desmopsis rejection and Spondias acceptance survive correctly; Hymenaea supplies only its rejection direction. Miconia is absent from the original candidates.

Under the documented conservative named-prose convention, PRIMARY has 2 author_prose and 4 table_derived species; CONTEXT has 4 author_prose and 1 table_derived. Table categories assign the latter labels; numerical signs do not. The table transcription remains visually unverified. Group/complement prose corroborates these labels. The [baseline report](recall_baseline.md) explains the convention and shared-text contamination risk, with record-level provenance in [JSON](recall_baseline.json).

lme4: available; R version 4.5.0 (2025-04-11) lme4=2.0.6. Analysis was rerun. Current inference blockers: fewer_than_minimum_joined_genera, need_two_genera_per_direction.

Trema resolves to accepted Trema micranthum with an EXACT GBIF match at confidence 100. LOTUS supplies 26 compounds, including six with exact accepted-species occurrences. All 26 have unknown eligible activity, with zero retrieval failures. Trema contributes zero classified compounds.

| Funnel | Before | Current |
| --- | --- | --- |
| names_resolved | 16 | 17 |
| genera_after_aggregation | 10 | 11 |
| genera_with_chemistry | 8 | 9 |
| genera_with_classified_compounds | 7 | 7 |
| genera_available_for_primary_test | 7 | 7 |
| mapped_structures | 2183 | 2198 |

The primary join remains six accepted and one rejected genus. The feasibility-failure label, null inferential results and 25-genus trigger remain. The two frozen files match the original commit; original extraction inputs and outputs match the baseline hashes. Offline replay passed 23 artifact comparisons for behaviour, activity and analysis. Chemistry used the completed full export scan.

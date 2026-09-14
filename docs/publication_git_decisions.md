# Publication Git decisions

This table covers every results file that was untracked when this review began, plus previously ignored compact evidence selected for publication. TRACK sizes are bytes in the index at final review; IGNORE sizes are bytes on disk. TRACK files are staged; IGNORE files remain on disk. No files are deleted.

Raw response caches remain ignored. Existing replay and bundle copies remain ignored; no reviewed per-record ledger exceeds 1 MB. Future files in the reader and system output directories remain ignored unless explicitly allowed.

The seeded-monarch source disagreement is resolved using the user-confirmed funnel and matching completion manifests. The [publication report](../results/publication_verification.json) records the source checks, protected text and publication links. The additional compact completion and access manifests below are staged with the corrected prose.

| Path | Bytes | Decision | Reason |
| --- | ---: | --- | --- |
| `results/day2_blockers/funnel.json` | 20,316 | TRACK | Compact coverage or feasibility counts. |
| `results/day2_blockers/metrics.json` | 671 | TRACK | Compact coverage or feasibility counts. |
| `results/grounding_development_v1/compare.json` | 84,151 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v1/compare.md` | 4,199 | TRACK | Compact interpretation linked from the reader reports. |
| `results/grounding_development_v1/verification.json` | 17,948 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v2/compare.json` | 256,411 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v2/compare.md` | 2,820 | TRACK | Compact interpretation linked from the reader reports. |
| `results/grounding_development_v2/preserved_inputs.json` | 11,429 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v2/run_status.json` | 994 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v2/saved_candidate_diagnostic.json` | 86,249 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v2/verification.json` | 34,205 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v3/byte_forensics.json` | 26,181 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v3/compare.json` | 542,221 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v3/compare.md` | 4,896 | TRACK | Compact interpretation linked from the reader reports. |
| `results/grounding_development_v3/preserved_inputs.json` | 20,371 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v3/repeat_comparison.json` | 464,706 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v3/repeat_failures.json` | 73,357 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v3/repeat_preserved_inputs.json` | 38,874 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v3/repeat_status.json` | 2,789 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v3/repeat_summary.md` | 6,266 | TRACK | Reader or system summary supporting the submission. |
| `results/grounding_development_v3/repeat_verification.json` | 53,813 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v3/verification.json` | 32,507 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v4/compare.json` | 527,552 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/generalization_checks.json` | 119,436 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_cached_control_evidence.json` | 20,505 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_failures.json` | 25,800 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_frozen_verification.json` | 135,233 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v4/heldout_preserved_inputs.json` | 59,431 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v4/heldout_protocol.json` | 99,658 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v4/heldout_sampling.json` | 2,634 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_scores.json` | 359,325 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_validation.json` | 636 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/heldout_verification.json` | 105 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v4/preserved_inputs.json` | 44,974 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v4/test_status.json` | 448 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v4/verification.json` | 71,829 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v5/generalization_checks.json` | 219,862 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v5/system_deltas.json` | 1,983 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v5/test_status.json` | 725 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v5/verification.json` | 42,864 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v6/development_scores.json` | 372,825 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/development_verification.json` | 104,014 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v6/heldout_sample4_failures.json` | 8,120 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/heldout_sample4_interpretation.json` | 1,756 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/heldout_sample4_protocol.json` | 166,376 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v6/heldout_sample4_sampling.json` | 2,508 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/heldout_sample4_scores.json` | 468,161 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/heldout_sample4_summary.md` | 6,177 | TRACK | Reader or system summary supporting the submission. |
| `results/grounding_development_v6/heldout_sample4_validation.json` | 275 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/heldout_sample4_verification.json` | 187,451 | TRACK | Compact provenance and replay verification. |
| `results/grounding_development_v6/heldout_sample4_workflow_status.json` | 2,389 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/grounding_development_v6/preserved_inputs.json` | 61,599 | TRACK | Input hashes or prespecified protocol for audit. |
| `results/grounding_development_v6/summary.md` | 4,023 | TRACK | Reader or system summary supporting the submission. |
| `results/grounding_development_v6/test_status.json` | 2,003 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/saverschek_audit/source_verification.json` | 13,022 | TRACK | Compact provenance and replay verification. |
| `results/saverschek_audit/verification_report.json` | 5,001 | TRACK | Compact provenance and replay verification. |
| `results/systems/attine_actino/control_preflight.json` | 5,058 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/currie_recovery/diagnosis.json` | 14,254 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/currie_recovery/sample_1_response.json` | 1,065 | IGNORE | Raw model response cache; diagnosis and verification remain public. |
| `results/systems/attine_actino/currie_recovery/sample_2_response.json` | 1,065 | IGNORE | Raw model response cache; diagnosis and verification remain public. |
| `results/systems/attine_actino/currie_recovery/sample_3_response.json` | 2,380 | IGNORE | Raw model response cache; diagnosis and verification remain public. |
| `results/systems/attine_actino/currie_recovery/summary.md` | 1,444 | TRACK | Reader or system summary supporting the submission. |
| `results/systems/attine_actino/funnel.json` | 3,347 | TRACK | Compact coverage or feasibility counts. |
| `results/systems/attine_actino/grounding_v4/summary.md` | 2,106 | TRACK | Reader or system summary supporting the submission. |
| `results/systems/attine_actino/grounding_v5/comparison.json` | 21,376 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/positive_control.json` | 5,538 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/reference_set.json` | 5,934 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/semantic_review.json` | 15,946 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/attine_actino/taxonomy_microbial/verification.json` | 1,990 | TRACK | Compact provenance and replay verification. |
| `results/systems/attine_actino/verification.json` | 111,925 | TRACK | Compact provenance and replay verification. |
| `results/systems/monarch/downstream_manifest.json` | 11,225 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch/funnel.json` | 5,368 | TRACK | Compact coverage or feasibility counts. |
| `results/systems/monarch/grounding_v4/summary.md` | 1,983 | TRACK | Reader or system summary supporting the submission. |
| `results/systems/monarch/grounding_v5/comparison.json` | 19,357 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch/semantic_review.json` | 12,740 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch/verification.json` | 145,636 | TRACK | Compact provenance and replay verification. |
| `results/systems/monarch_seeded/bibliography_audit.json` | 8,049 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch_seeded/funnel.json` | 5,952 | TRACK | Compact coverage or feasibility counts. |
| `results/systems/monarch_seeded/preparation.json` | 3,707 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch_seeded/source_design_review.json` | 8,395 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/monarch_seeded/verification.json` | 377,543 | TRACK | Compact provenance and replay verification. |
| `results/systems/propolis/downstream_manifest.json` | 8,020 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/propolis/funnel.json` | 4,003 | TRACK | Compact coverage or feasibility counts. |
| `results/systems/propolis/grounding_v4/summary.md` | 2,037 | TRACK | Reader or system summary supporting the submission. |
| `results/systems/propolis/grounding_v5/comparison.json` | 22,079 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/propolis/semantic_review.json` | 3,571 | TRACK | Compact comparison, score or diagnostic supporting the reported result. |
| `results/systems/propolis/verification.json` | 106,891 | TRACK | Compact provenance and replay verification. |
| `results/systems/monarch_seeded/assay_scope_manifest.json` | 1,234 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |
| `results/systems/monarch_seeded/downstream_manifest.json` | 13,001 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |
| `results/systems/monarch_seeded/extraction_manifest.json` | 21,568 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |
| `results/systems/monarch_seeded/local_pdf_access.json` | 7,474 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |
| `results/systems/monarch_seeded/seed_access.json` | 18,403 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |
| `results/systems/monarch_seeded/semantic_review.json` | 69,192 | TRACK | Completed seeded run and source-access provenance cited by the corrected documents. |

## Results status

The four corrected documents and their compact cited manifests are staged. The pre-existing pipeline-report edit remains unstaged. `.DS_Store` is ignored and absent from the index.

```text
A  results/business_case/judges_submission_v2.md
A  results/day2_blockers/funnel.json
A  results/day2_blockers/metrics.json
A  results/experiment_planner/index.html
A  results/grounding_development_v1/compare.json
A  results/grounding_development_v1/compare.md
A  results/grounding_development_v1/summary.md
A  results/grounding_development_v1/verification.json
A  results/grounding_development_v2/compare.json
A  results/grounding_development_v2/compare.md
A  results/grounding_development_v2/preserved_inputs.json
A  results/grounding_development_v2/run_status.json
A  results/grounding_development_v2/saved_candidate_diagnostic.json
A  results/grounding_development_v2/summary.md
A  results/grounding_development_v2/verification.json
A  results/grounding_development_v3/byte_forensics.json
A  results/grounding_development_v3/compare.json
A  results/grounding_development_v3/compare.md
A  results/grounding_development_v3/preserved_inputs.json
A  results/grounding_development_v3/repeat_comparison.json
A  results/grounding_development_v3/repeat_failures.json
A  results/grounding_development_v3/repeat_preserved_inputs.json
A  results/grounding_development_v3/repeat_status.json
A  results/grounding_development_v3/repeat_summary.md
A  results/grounding_development_v3/repeat_verification.json
A  results/grounding_development_v3/summary.md
A  results/grounding_development_v3/verification.json
A  results/grounding_development_v4/compare.json
A  results/grounding_development_v4/generalization_checks.json
A  results/grounding_development_v4/heldout_cached_control_evidence.json
A  results/grounding_development_v4/heldout_failures.json
A  results/grounding_development_v4/heldout_frozen_verification.json
A  results/grounding_development_v4/heldout_preserved_inputs.json
A  results/grounding_development_v4/heldout_protocol.json
A  results/grounding_development_v4/heldout_sampling.json
A  results/grounding_development_v4/heldout_scores.json
A  results/grounding_development_v4/heldout_summary.md
A  results/grounding_development_v4/heldout_validation.json
A  results/grounding_development_v4/heldout_verification.json
A  results/grounding_development_v4/preserved_inputs.json
A  results/grounding_development_v4/summary.md
A  results/grounding_development_v4/test_status.json
A  results/grounding_development_v4/verification.json
A  results/grounding_development_v5/generalization_checks.json
A  results/grounding_development_v5/summary.md
A  results/grounding_development_v5/system_deltas.json
A  results/grounding_development_v5/test_status.json
A  results/grounding_development_v5/verification.json
A  results/grounding_development_v6/development_scores.json
A  results/grounding_development_v6/development_verification.json
A  results/grounding_development_v6/heldout_sample4_failures.json
A  results/grounding_development_v6/heldout_sample4_interpretation.json
A  results/grounding_development_v6/heldout_sample4_protocol.json
A  results/grounding_development_v6/heldout_sample4_sampling.json
A  results/grounding_development_v6/heldout_sample4_scores.json
A  results/grounding_development_v6/heldout_sample4_summary.md
A  results/grounding_development_v6/heldout_sample4_validation.json
A  results/grounding_development_v6/heldout_sample4_verification.json
A  results/grounding_development_v6/heldout_sample4_workflow_status.json
A  results/grounding_development_v6/preserved_inputs.json
A  results/grounding_development_v6/summary.md
A  results/grounding_development_v6/test_status.json
 M results/pipeline_report.md
A  results/publication_verification.json
A  results/saverschek_audit/source_verification.json
A  results/saverschek_audit/verification_report.json
A  results/systems/attine_actino/control_preflight.json
A  results/systems/attine_actino/currie_recovery/diagnosis.json
A  results/systems/attine_actino/currie_recovery/summary.md
A  results/systems/attine_actino/funnel.json
A  results/systems/attine_actino/grounding_v4/summary.md
A  results/systems/attine_actino/grounding_v5/comparison.json
A  results/systems/attine_actino/positive_control.json
A  results/systems/attine_actino/reference_set.json
A  results/systems/attine_actino/semantic_review.json
A  results/systems/attine_actino/taxonomy_microbial/summary.md
A  results/systems/attine_actino/taxonomy_microbial/verification.json
A  results/systems/attine_actino/verification.json
A  results/systems/monarch/downstream_manifest.json
A  results/systems/monarch/funnel.json
A  results/systems/monarch/grounding_v4/summary.md
A  results/systems/monarch/grounding_v5/comparison.json
A  results/systems/monarch/semantic_review.json
A  results/systems/monarch/verification.json
A  results/systems/monarch_seeded/assay_scope_manifest.json
A  results/systems/monarch_seeded/bibliography_audit.json
A  results/systems/monarch_seeded/downstream_manifest.json
A  results/systems/monarch_seeded/extraction_manifest.json
A  results/systems/monarch_seeded/funnel.json
A  results/systems/monarch_seeded/local_pdf_access.json
A  results/systems/monarch_seeded/preparation.json
A  results/systems/monarch_seeded/seed_access.json
A  results/systems/monarch_seeded/semantic_review.json
A  results/systems/monarch_seeded/source_design_review.json
A  results/systems/monarch_seeded/summary.md
A  results/systems/monarch_seeded/verification.json
A  results/systems/propolis/downstream_manifest.json
A  results/systems/propolis/funnel.json
A  results/systems/propolis/grounding_v4/summary.md
A  results/systems/propolis/grounding_v5/comparison.json
A  results/systems/propolis/semantic_review.json
A  results/systems/propolis/verification.json
A  results/systems/summary.md
```

# Publication source-text audit

Every file in the initial index, including every tracked or staged docs/ and results/ file; working and differing index bytes audited.

Source-bearing prose and table strings in docs/results are removed entirely. Attributed quotations elsewhere have at most 15 whitespace-delimited words. Bibliographic titles, author lists, identifiers, derived findings and invented synthetic test strings are separate from retrieved paper prose.

Duplicate-inclusive words and UTF-8 bytes in source-bearing fields. Raw request totals count cached block bodies only. Model quotes may contain copying errors. This is a carriage inventory, not a count of unique paper words.

The [JSON audit](audit.json) records exact before/after hashes, byte counts and private locators. The [licence inventory](licences.json) records all represented sources, including metadata-only mentions, with evidence URLs and uncertainty.

Saverschek 2010 (Animal Behaviour, Elsevier) has an all-rights-reserved publisher notice and no recorded redistribution permission. Its full text remains private.

| File | Source | Licence / redistribution | Source words before → after | File bytes before → after | Action |
| --- | --- | --- | --- | --- | --- |
| `.gitignore` | None (derived results or metadata) | N/A | 0 → 0 | 9151 → 9564 | publication notice or pitch updated source prose unchanged |
| `README.md` | None (derived results or metadata) | N/A | 0 → 0 | 21722 → 22541 | publication notice or pitch updated source prose unchanged |
| `config/pilot_name_mappings.json` | PMC11543716 | PMC11543716: CC-BY-4.0; redistribution yes | 68 → 68 | 2546 → 2546 | retained attributed quotes within 15 words |
| `docs/amendment_2026-09-12_reporting_gate.md` | None (derived results or metadata) | N/A | 0 → 0 | 3488 → 3488 | no retrieved source prose found |
| `docs/amendment_2026-09-13_exploratory_systems.md` | None (derived results or metadata) | N/A | 0 → 0 | 3437 → 3437 | no retrieved source prose found |
| `docs/amendment_2026-09-13_generalized_glyph_grounding.md` | None (derived results or metadata) | N/A | 0 → 0 | 4916 → 4916 | no retrieved source prose found |
| `docs/amendment_2026-09-13_glyph_grounding.md` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 4060 → 4060 | no retrieved source prose found |
| `docs/amendment_2026-09-13_microbial_taxonomy.md` | None (derived results or metadata) | N/A | 0 → 0 | 3078 → 3078 | no retrieved source prose found |
| `docs/amendment_2026-09-13_monarch_seeded.md` | None (derived results or metadata) | N/A | 0 → 0 | 5734 → 5734 | no retrieved source prose found |
| `docs/amendment_2026-09-13_multispan_development.md` | None (derived results or metadata) | N/A | 0 → 0 | 5405 → 5405 | no retrieved source prose found |
| `docs/amendment_2026-09-13_source_ant_identity.md` | None (derived results or metadata) | N/A | 0 → 0 | 4975 → 4975 | no retrieved source prose found |
| `docs/amendment_2026-09-13_trema_taxonomy.md` | None (derived results or metadata) | N/A | 0 → 0 | 2277 → 2277 | no retrieved source prose found |
| `docs/amendment_2026-09-13_v5_printable_confusables.md` | None (derived results or metadata) | N/A | 0 → 0 | 5639 → 5639 | no retrieved source prose found |
| `docs/amendment_2026-09-13_v6_cache_side_controls.md` | None (derived results or metadata) | N/A | 0 → 0 | 5879 → 5879 | no retrieved source prose found |
| `docs/analysis_plan.md` | None (derived results or metadata) | N/A | 0 → 0 | 11949 → 11949 | no retrieved source prose found |
| `docs/checkin_12h.md` | None (derived results or metadata) | N/A | 0 → 0 | 5110 → 5110 | no retrieved source prose found |
| `docs/chemistry_export.md` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 6799 → 6799 | no retrieved source prose found |
| `docs/design_audit.md` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 5843 → 5843 | no retrieved source prose found |
| `docs/experiment_workflows.md` | None (derived results or metadata) | N/A | 0 → 0 | 11427 → 11427 | no retrieved source prose found |
| `docs/final_pitch_skeleton.md` | None (derived results or metadata) | N/A | 0 → 0 | 987 → 987 | no retrieved source prose found |
| `docs/gemini_setup.md` | None (derived results or metadata) | N/A | 0 → 0 | 6230 → 6230 | no retrieved source prose found |
| `docs/implementation_log.md` | 3 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 17611 → 17611 | no retrieved source prose found |
| `docs/local_notes.md` | 3 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 2218 → 2218 | no retrieved source prose found |
| `docs/pending_evidence.md` | 3 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 5211 → 5211 | no retrieved source prose found |
| `docs/pilot_status.md` | 6 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 7709 → 7709 | no retrieved source prose found |
| `docs/pipeline.md` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 10379 → 10379 | no retrieved source prose found |
| `docs/publication_git_decisions.md` | None (derived results or metadata) | N/A | 0 → 0 | 19817 → 19817 | no retrieved source prose found |
| `docs/source_gaps.md` | 12 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 12310 → 12310 | no retrieved source prose found |
| `docs/source_gaps_monarch_seeded.md` | None (derived results or metadata) | N/A | 0 → 0 | 5790 → 5790 | no retrieved source prose found |
| `docs/targeted_saverschek.md` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 16 → 0 | 7444 → 7736 | source text replaced with private references |
| `docs/video_script_12h.md` | None (derived results or metadata) | N/A | 0 → 0 | 1794 → 1794 | no retrieved source prose found |
| `results/business_case/judges_submission_v2.md` | None (derived results or metadata) | N/A | 0 → 0 | 9500 → 10622 | publication notice or pitch updated source prose unchanged |
| `results/candidate_genera.csv` | None (derived results or metadata) | N/A | 0 → 0 | 22 → 22 | no retrieved source prose found |
| `results/day2_blockers/funnel.json` | 31 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 20316 → 20316 | no retrieved source prose found |
| `results/day2_blockers/lme4_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 1661 → 1661 | no retrieved source prose found |
| `results/day2_blockers/metrics.json` | None (derived results or metadata) | N/A | 0 → 0 | 671 → 671 | no retrieved source prose found |
| `results/day2_blockers/trema_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 3616 → 3616 | no retrieved source prose found |
| `results/day2_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 8962 → 8962 | no retrieved source prose found |
| `results/day2_status.md` | None (derived results or metadata) | N/A | 0 → 0 | 2203 → 2203 | no retrieved source prose found |
| `results/delayed/genera.csv` | 510 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 97605 → 97605 | no retrieved source prose found |
| `results/delayed/summary.json` | None (derived results or metadata) | N/A | 0 → 0 | 1737 → 1737 | no retrieved source prose found |
| `results/end_to_end_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 3234 → 3234 | no retrieved source prose found |
| `results/experiment_planner/index.html` | 2 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 320634 → 320634 | no retrieved source prose found |
| `results/experimental/genera.csv` | 507 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 97992 → 97992 | no retrieved source prose found |
| `results/experimental/summary.json` | None (derived results or metadata) | N/A | 0 → 0 | 2087 → 2087 | no retrieved source prose found |
| `results/funnel.csv` | None (derived results or metadata) | N/A | 0 → 0 | 854 → 854 | no retrieved source prose found |
| `results/funnel.json` | 31 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 20726 → 20726 | no retrieved source prose found |
| `results/grounding_development_v1/compare.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 2322 → 0 | 84151 → 173557 | source text replaced with private references |
| `results/grounding_development_v1/compare.md` | None (derived results or metadata) | N/A | 0 → 0 | 4199 → 4199 | no retrieved source prose found |
| `results/grounding_development_v1/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 3943 → 3943 | no retrieved source prose found |
| `results/grounding_development_v1/verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 17948 → 17948 | no retrieved source prose found |
| `results/grounding_development_v2/compare.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 7894 → 0 | 256411 → 583866 | source text replaced with private references |
| `results/grounding_development_v2/compare.md` | None (derived results or metadata) | N/A | 0 → 0 | 2820 → 2820 | no retrieved source prose found |
| `results/grounding_development_v2/preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 11429 → 11429 | no retrieved source prose found |
| `results/grounding_development_v2/run_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 994 → 994 | no retrieved source prose found |
| `results/grounding_development_v2/saved_candidate_diagnostic.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 2804 → 0 | 86249 → 239739 | source text replaced with private references |
| `results/grounding_development_v2/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 4154 → 4154 | no retrieved source prose found |
| `results/grounding_development_v2/verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 34205 → 34205 | no retrieved source prose found |
| `results/grounding_development_v3/byte_forensics.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 48 → 0 | 26181 → 41303 | source text replaced with private references |
| `results/grounding_development_v3/compare.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 16258 → 0 | 542221 → 1362139 | source text replaced with private references |
| `results/grounding_development_v3/compare.md` | None (derived results or metadata) | N/A | 0 → 0 | 4896 → 4896 | no retrieved source prose found |
| `results/grounding_development_v3/preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 20371 → 20371 | no retrieved source prose found |
| `results/grounding_development_v3/repeat_comparison.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 13140 → 0 | 464706 → 1147326 | source text replaced with private references |
| `results/grounding_development_v3/repeat_failures.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 1248 → 0 | 73357 → 190400 | source text replaced with private references |
| `results/grounding_development_v3/repeat_preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 38874 → 38874 | no retrieved source prose found |
| `results/grounding_development_v3/repeat_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 2789 → 2789 | no retrieved source prose found |
| `results/grounding_development_v3/repeat_summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 6266 → 6266 | no retrieved source prose found |
| `results/grounding_development_v3/repeat_verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 53813 → 53813 | no retrieved source prose found |
| `results/grounding_development_v3/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 6072 → 6072 | no retrieved source prose found |
| `results/grounding_development_v3/verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 32507 → 32507 | no retrieved source prose found |
| `results/grounding_development_v4/compare.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 14350 → 0 | 527552 → 1325472 | source text replaced with private references |
| `results/grounding_development_v4/generalization_checks.json` | None (derived results or metadata) | N/A | 0 → 0 | 119436 → 119436 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_cached_control_evidence.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 948 → 0 | 20505 → 47302 | source text replaced with private references |
| `results/grounding_development_v4/heldout_failures.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 646 → 0 | 25800 → 44035 | source text replaced with private references |
| `results/grounding_development_v4/heldout_frozen_verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 135233 → 135233 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 59431 → 59431 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_protocol.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 8149 → 0 | 99658 → 51388 | source text replaced with private references |
| `results/grounding_development_v4/heldout_sampling.json` | None (derived results or metadata) | N/A | 0 → 0 | 2634 → 2634 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_scores.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 9816 → 0 | 359325 → 881637 | source text replaced with private references |
| `results/grounding_development_v4/heldout_summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 5800 → 5800 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_validation.json` | None (derived results or metadata) | N/A | 0 → 0 | 636 → 636 | no retrieved source prose found |
| `results/grounding_development_v4/heldout_verification.json` | None (derived results or metadata) | N/A | 0 → 0 | 105 → 105 | no retrieved source prose found |
| `results/grounding_development_v4/preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 44974 → 44974 | no retrieved source prose found |
| `results/grounding_development_v4/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 6096 → 6096 | no retrieved source prose found |
| `results/grounding_development_v4/test_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 448 → 448 | no retrieved source prose found |
| `results/grounding_development_v4/verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 71829 → 71829 | no retrieved source prose found |
| `results/grounding_development_v5/generalization_checks.json` | None (derived results or metadata) | N/A | 0 → 0 | 219862 → 219862 | no retrieved source prose found |
| `results/grounding_development_v5/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 5858 → 5858 | no retrieved source prose found |
| `results/grounding_development_v5/system_deltas.json` | None (derived results or metadata) | N/A | 0 → 0 | 1983 → 1983 | no retrieved source prose found |
| `results/grounding_development_v5/test_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 725 → 725 | no retrieved source prose found |
| `results/grounding_development_v5/verification.json` | None (derived results or metadata) | N/A | 0 → 0 | 42864 → 42864 | no retrieved source prose found |
| `results/grounding_development_v6/development_scores.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 9816 → 0 | 372825 → 896494 | source text replaced with private references |
| `results/grounding_development_v6/development_verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 104014 → 104014 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_failures.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 8120 → 8120 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_interpretation.json` | None (derived results or metadata) | N/A | 0 → 0 | 1756 → 1756 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_protocol.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 8149 → 0 | 166376 → 118138 | source text replaced with private references |
| `results/grounding_development_v6/heldout_sample4_sampling.json` | None (derived results or metadata) | N/A | 0 → 0 | 2508 → 2508 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_scores.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 12661 → 0 | 468161 → 1124439 | source text replaced with private references |
| `results/grounding_development_v6/heldout_sample4_summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 6177 → 6177 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_validation.json` | None (derived results or metadata) | N/A | 0 → 0 | 275 → 275 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_verification.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 187451 → 187451 | no retrieved source prose found |
| `results/grounding_development_v6/heldout_sample4_workflow_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 2389 → 2389 | no retrieved source prose found |
| `results/grounding_development_v6/preserved_inputs.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 61599 → 61599 | no retrieved source prose found |
| `results/grounding_development_v6/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 4023 → 4023 | no retrieved source prose found |
| `results/grounding_development_v6/test_status.json` | None (derived results or metadata) | N/A | 0 → 0 | 2003 → 2003 | no retrieved source prose found |
| `results/metrics.json` | None (derived results or metadata) | N/A | 0 → 0 | 775 → 775 | no retrieved source prose found |
| `results/nondiscordant/genera.csv` | 507 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 97942 → 97942 | no retrieved source prose found |
| `results/nondiscordant/summary.json` | None (derived results or metadata) | N/A | 0 → 0 | 1738 → 1738 | no retrieved source prose found |
| `results/offline_replay.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 9001 → 9001 | no retrieved source prose found |
| `results/pipeline_report.md` | None (derived results or metadata) | N/A | 0 → 0 | 2872 → 2872 | no retrieved source prose found |
| `results/primary/genera.csv` | 507 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 97992 → 97992 | no retrieved source prose found |
| `results/primary/summary.json` | None (derived results or metadata) | N/A | 0 → 0 | 2243 → 2243 | no retrieved source prose found |
| `results/publication_verification.json` | 5 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 9892 → 9892 | no retrieved source prose found |
| `results/recall_baseline.json` | SAVERSCHEK2010 | SAVERSCHEK2010: all-rights-reserved; redistribution no | 2296 → 0 | 75710 → 138133 | source text replaced with private references |
| `results/recall_baseline.md` | None (derived results or metadata) | N/A | 0 → 0 | 4783 → 4783 | no retrieved source prose found |
| `results/run_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 4436 → 4436 | no retrieved source prose found |
| `results/saverschek_audit/source_verification.json` | 2 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 13022 → 13022 | no retrieved source prose found |
| `results/saverschek_audit/verification_report.json` | None (derived results or metadata) | N/A | 0 → 0 | 5001 → 5001 | no retrieved source prose found |
| `results/summary.json` | None (derived results or metadata) | N/A | 0 → 0 | 8399 → 8399 | no retrieved source prose found |
| `results/systems/attine_actino/control_preflight.json` | 2 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 5058 → 5058 | no retrieved source prose found |
| `results/systems/attine_actino/currie_recovery/diagnosis.json` | CURRIE1999 | CURRIE1999: unverified; redistribution unclear | 300 → 0 | 14254 → 402609 | source text replaced with private references |
| `results/systems/attine_actino/currie_recovery/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 1444 → 1444 | no retrieved source prose found |
| `results/systems/attine_actino/funnel.json` | None (derived results or metadata) | N/A | 0 → 0 | 3347 → 3347 | no retrieved source prose found |
| `results/systems/attine_actino/grounding_v4/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 2106 → 2106 | no retrieved source prose found |
| `results/systems/attine_actino/grounding_v5/comparison.json` | None (derived results or metadata) | N/A | 0 → 0 | 21376 → 21376 | no retrieved source prose found |
| `results/systems/attine_actino/positive_control.json` | 3 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 5538 → 5538 | no retrieved source prose found |
| `results/systems/attine_actino/reference_set.json` | CURRIE1999, PMC2748230 | CURRIE1999: unverified; redistribution unclear; PMC2748230: unverified; redistribution unclear | 46 → 0 | 5934 → 10518 | source text replaced with private references |
| `results/systems/attine_actino/semantic_review.json` | PMC10384482, PMC13098279, PMC2748230, PMC8689564 | PMC10384482: CC-BY-4.0; redistribution yes; PMC13098279: CC-BY-4.0; redistribution yes; PMC2748230: unverified; redistribution unclear; PMC8689564: CC-BY-4.0; redistribution yes | 357 → 0 | 15946 → 28646 | source text replaced with private references |
| `results/systems/attine_actino/taxonomy_microbial/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 1071 → 1071 | no retrieved source prose found |
| `results/systems/attine_actino/taxonomy_microbial/verification.json` | None (derived results or metadata) | N/A | 0 → 0 | 1990 → 1990 | no retrieved source prose found |
| `results/systems/attine_actino/verification.json` | 22 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 111925 → 111925 | no retrieved source prose found |
| `results/systems/monarch/downstream_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 11225 → 11225 | no retrieved source prose found |
| `results/systems/monarch/funnel.json` | None (derived results or metadata) | N/A | 0 → 0 | 5368 → 5368 | no retrieved source prose found |
| `results/systems/monarch/grounding_v4/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 1983 → 1983 | no retrieved source prose found |
| `results/systems/monarch/grounding_v5/comparison.json` | None (derived results or metadata) | N/A | 0 → 0 | 19357 → 19357 | no retrieved source prose found |
| `results/systems/monarch/semantic_review.json` | PMC10370756, PMC10430791, PMC12585044, PMC9197062 | PMC10370756: CC-BY-4.0; redistribution yes; PMC10430791: CC-BY-NC-ND-4.0; redistribution unclear; PMC12585044: CC-BY-4.0; redistribution yes; PMC9197062: CC-BY-4.0; redistribution yes | 231 → 0 | 12740 → 29990 | source text replaced with private references |
| `results/systems/monarch/verification.json` | 20 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 145636 → 145636 | no retrieved source prose found |
| `results/systems/monarch_seeded/assay_scope_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 1234 → 1234 | no retrieved source prose found |
| `results/systems/monarch_seeded/bibliography_audit.json` | None (derived results or metadata) | N/A | 0 → 0 | 8049 → 8049 | no retrieved source prose found |
| `results/systems/monarch_seeded/downstream_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 13001 → 13001 | no retrieved source prose found |
| `results/systems/monarch_seeded/extraction_manifest.json` | 6 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 21568 → 21568 | no retrieved source prose found |
| `results/systems/monarch_seeded/funnel.json` | None (derived results or metadata) | N/A | 0 → 0 | 5952 → 5952 | no retrieved source prose found |
| `results/systems/monarch_seeded/local_pdf_access.json` | 5 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 7474 → 7474 | no retrieved source prose found |
| `results/systems/monarch_seeded/preparation.json` | 8 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 3707 → 3707 | no retrieved source prose found |
| `results/systems/monarch_seeded/seed_access.json` | None (derived results or metadata) | N/A | 0 → 0 | 18403 → 18403 | no retrieved source prose found |
| `results/systems/monarch_seeded/semantic_review.json` | LEFEVRE2010, LEFEVRE2012, PMC10370756, PMC10430791, PMC12585044, PMC9197062 | LEFEVRE2010: unverified; redistribution unclear; LEFEVRE2012: unverified; redistribution unclear; PMC10370756: CC-BY-4.0; redistribution yes; PMC10430791: CC-BY-NC-ND-4.0; redistribution unclear; PMC12585044: CC-BY-4.0; redistribution yes; PMC9197062: CC-BY-4.0; redistribution yes | 2047 → 0 | 69192 → 146995 | source text replaced with private references |
| `results/systems/monarch_seeded/source_design_review.json` | LEFEVRE2010, LEFEVRE2012 | LEFEVRE2010: unverified; redistribution unclear; LEFEVRE2012: unverified; redistribution unclear | 238 → 0 | 8395 → 20013 | source text replaced with private references |
| `results/systems/monarch_seeded/summary.md` | 8 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 16325 → 16325 | no retrieved source prose found |
| `results/systems/monarch_seeded/verification.json` | 25 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 377543 → 377543 | no retrieved source prose found |
| `results/systems/propolis/downstream_manifest.json` | None (derived results or metadata) | N/A | 0 → 0 | 8020 → 8020 | no retrieved source prose found |
| `results/systems/propolis/funnel.json` | None (derived results or metadata) | N/A | 0 → 0 | 4003 → 4003 | no retrieved source prose found |
| `results/systems/propolis/grounding_v4/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 2037 → 2037 | no retrieved source prose found |
| `results/systems/propolis/grounding_v5/comparison.json` | None (derived results or metadata) | N/A | 0 → 0 | 22079 → 22079 | no retrieved source prose found |
| `results/systems/propolis/semantic_review.json` | 1 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 3571 → 3571 | no retrieved source prose found |
| `results/systems/propolis/verification.json` | 20 cited sources; no verbatim prose (IDs in JSON) | Source-specific licence status in JSON audit and licence inventory | 0 → 0 | 106891 → 106891 | no retrieved source prose found |
| `results/systems/summary.md` | None (derived results or metadata) | N/A | 0 → 0 | 15483 → 15483 | no retrieved source prose found |

All affected source-bearing originals retain their exact pre-edit bytes under `data/interim/publication_safety/originals/`; initial index copies are preserved separately under `index_originals/`. Both are ignored. No files were moved out of tracking; public paths now contain references.

Current index and working files only. Historical Git blobs are not rewritten; earlier committed quotations require separate history review before release.

Full text is retained locally and is not redistributed. Local replay uses the private mirror described in [the publication guide](../../docs/publication_safety.md).

## Added publication files

These files had no pre-cleanup counterpart. Hashes and sizes are in the JSON audit; the audit's own two files are excluded from self-hashing. The final source-text check includes these files.

| File | Source | Licence / redistribution | Source words before → after | File bytes before → after | Action |
| --- | --- | --- | --- | --- | --- |
| `docs/publication_safety.md` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 5050 | Added publication-safety file |
| `results/publication_safety/audit.json` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → self-size excluded | Added publication-safety file |
| `results/publication_safety/audit.md` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → self-size excluded | Added publication-safety file |
| `results/publication_safety/licences.json` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 907762 | Added publication-safety file |
| `results/publication_safety/replay_verification.json` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 217680 | Added publication-safety file |
| `results/publication_safety/test_verification.json` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 179564 | Added publication-safety file |
| `results/publication_safety/verification.json` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 23020 | Added publication-safety file |
| `scripts/publication_safety.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 5329 | Added publication-safety file |
| `src/publication/__init__.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 77 | Added publication-safety file |
| `src/publication/audit.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 5842 | Added publication-safety file |
| `src/publication/redact.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 8356 | Added publication-safety file |
| `src/publication/replay.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 22695 | Added publication-safety file |
| `src/publication/report.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 12232 | Added publication-safety file |
| `src/publication/source_index.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 5826 | Added publication-safety file |
| `src/publication/verify.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 9926 | Added publication-safety file |
| `tests/test_publication_replay.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 7441 | Added publication-safety file |
| `tests/test_publication_safety.py` | Publication metadata, references or synthetic fixtures | Source-specific status in licence inventory; no paper prose | 0 → 0 | 0 → 6876 | Added publication-safety file |

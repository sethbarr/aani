# Detection variance — DEVELOPMENT SET

**Arm A is complete; Arm B has three complete draws and one unscorable draw (B2).** All seven complete draws detected, retained, and correctly matched all six PRIMARY species. The complete Arm A result is reported below; available Arm B observations are retained separately.

Predeclaration: `3a29ebd8622b3c47af95eb6b9846328a27c86bd8`, committed `2026-09-14T08:15:33-04:00`. The original window expired while approval was pending, with zero calls. After explicit approval, restart addendum `2d6c9e9dcf2471fc12e558368c302da5b4fb4e08` was committed at `2026-09-14T10:35:16-04:00`, before any draw. The declared restart window was `14:34:12–16:34:12 UTC` on September 14. This timing departure is documented in `docs/amendment_2026-09-14_detection_variance_restart.md`.

All 24 predeclared calls were attempted once, from `2026-09-14T14:35:48.049481+00:00` through `2026-09-14T14:41:30.292990+00:00`. All received HTTP 200; 23 returned parseable extraction JSON. Transport retries: **0**. No replacement draws or repaired responses were used.

Arm A uses the existing v2+ two-span contract, including supporting evidence. Arm B requests one span; every other job field and the source-level identity suffix are identical. Both use Gemini `gemini-3.8-flash`, the same three source chunks, and unchanged generation settings. All candidates use frozen v6 at confidence threshold 0.8. The B adapter copies its sole quote into `name_evidence` and supplies empty supporting evidence, without adding source text.

## Eight-draw table

Detection, survival, and correctness are PRIMARY species counts out of six under the saved baseline convention. Proposed and passed candidate counts include all species and contexts. The three reference-pair counts equal the three species counts in every complete draw.

| Draw | Status | Detection /6 | Survival /6 | Correctness /6 | Proposed candidates | Passed v6 | Omitted PRIMARY species |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| A1 | complete | 6 | 6 | 6 | 24 | 22 | none |
| A2 | complete | 6 | 6 | 6 | 24 | 22 | none |
| A3 | complete | 6 | 6 | 6 | 25 | 21 | none |
| A4 | complete | 6 | 6 | 6 | 26 | 20 | none |
| B1 | complete | 6 | 6 | 6 | 20 | 13 | none |
| B2 | incomplete: invalid JSON in chunk 1 | unavailable | unavailable | unavailable | 2 readable; full count unknown | 0 from readable jobs | unknown |
| B3 | complete | 6 | 6 | 6 | 17 | 12 | none |
| B4 | complete | 6 | 6 | 6 | 18 | 13 | none |

B2 chunk 1 failed parsing with `JSONDecodeError: Invalid control character at: line 113 column 45 (char 4771)`. Its original HTTP response remains in the isolated transport cache. B2 chunks 0 and 2 yielded zero and two readable candidates, respectively; neither candidate passed. B2 has no full-draw score, and its two readable candidates are excluded from complete-draw arm summaries.

## Arm summaries

| Measure | A: four complete draws | B: three available complete draws |
| --- | --- | --- |
| Detection counts | 6, 6, 6, 6 | 6, unavailable, 6, 6 |
| Detection mean; range | 6; 6–6 | 6; 6–6 (B1, B3, B4 only) |
| Survival counts | 6, 6, 6, 6 | 6, unavailable, 6, 6 |
| Survival mean; range | 6; 6–6 | 6; 6–6 (B1, B3, B4 only) |
| Correctness counts | 6, 6, 6, 6 | 6, unavailable, 6, 6 |
| Correctness mean; range | 6; 6–6 | 6; 6–6 (B1, B3, B4 only) |
| Proposed candidates | 99 | 55 across B1, B3, B4; four-draw total unknown |
| Proposals per complete draw: mean; range | 24.75; 24–26 | 18.33; 17–20 |
| Candidate survival | 85/99 | 38/55 |
| Candidate failures | 14 | 17 |
| Candidate passes per complete draw: mean; range | 21.25; 20–22 | 12.67; 12–13 |

The available B draws had fewer proposals and lower candidate survival than A, while PRIMARY detection and survival stayed at the ceiling. Fifteen of the 17 failures in complete B draws were `plant_not_in_name_evidence`; two were `ant_identity_mismatch`. This is a candidate-level survival cost of the single-span contract under unchanged v6. These data show no PRIMARY detection gain from single-span output. The missing B2 table response prevents a complete four-draw arm comparison.

## PRIMARY omissions

| Species | A omissions /4 | B omissions /3 complete draws |
| --- | ---: | ---: |
| Desmopsis panamensis | 0 | 0 |
| Hiraea grandifolia | 0 | 0 |
| Randia armata | 0 | 0 |
| Sorocea affinis | 0 | 0 |
| Trema micrantha | 0 | 0 |
| Spondias mombin | 0 | 0 |

B2 omission status is unknown for every species. Missing data are excluded from means and omission denominators.

## Hypothesis verdict

The data cannot distinguish H1 and H2 at the planned n=4 per arm: all seven complete draws reached 6/6 PRIMARY detection, and B2 was unscorable.

The committed H2 criterion requires min(B) > max(A). The H1 criterion requires an A detection range of at least two species, overlapping arm ranges, and an absolute detection-mean gap at most 0.5. Equal ceiling counts and incomplete arms fall under the predeclared inconclusive category. No statistical test, p-value, confidence interval, or population effect estimate was computed.

## Verification and scope

Independent reconciliation passed: 24 single transport attempts, 24 distinct response-byte hashes, exact request descriptors, preserved raw records, mechanically constrained B adaptation, and baseline score agreement. The provider omitted response IDs; fresh caches, attempt logs, and response-byte hashes document separate executions. All 640 execution-frozen files passed preservation checks. The v6 extraction/scoring code matched the historical hashes, and `docs/analysis_plan.md` plus `config/analysis.json` still match `98b5e09`.

The separate concurrent `results/assay_gap_audit` directory was excluded through the committed restart addendum. Its original/current hashes remain in `execution_provenance.json`. This experiment did not modify those files. Original pre-restart provenance is preserved.

Arm B raw records, adapted records, and validation outputs remain under `data/interim/detection_variance`, isolated from every primary and exploratory biological output. No biological pipeline was invoked. Per-draw JSON files, `comparison.json`, `verification.json`, and `reconciliation.json` retain the measurement evidence.

This is a development set: one paper, one panel, and implementers know the reference. Exact full names and structured outcomes determine baseline scores; correctness is a reference-label match without an added semantic-review gate. Author-grouped labels follow the printed Table 1 headings, checked against the original PDF; the numerical transcription remains unverified and the semantic support for individual rows and captions remains unadjudicated. Arms ran A first, so provider changes during execution remain a limitation. The incomplete B draw may reflect output-dependent missingness; its absence cannot be assumed random.

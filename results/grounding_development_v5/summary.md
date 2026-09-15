# V5 printable confusables — DEVELOPMENT SET

V5 applies exact grounding first, the complete v4 control-glyph inference second, and printable-confusable inference third. The printable policy contains only the listed hyphen/dash, single-quote, double-quote, and SPACE/NBSP classes. Candidate-local conflicts, ambiguous alignments, length changes, and any other character change reject.

## Leafcutter regression

All three saved leafcutter samples were replayed from their existing caches with offline mode enabled. Raw model outputs and request hashes match between v4 and v5 for every job. A second v5 replay reproduced the scientific artifacts byte for byte.

| Sample | Candidates | V4 survivors | V5 survivors | Prior survivors retained | New survivors | Lost survivors | Direction changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 26 | 23 | 23 | 23 | 0 | 0 | 0 |
| 2 | 18 | 18 | 18 | 18 | 0 | 0 | 0 |
| 3 | 24 | 13 | 13 | 13 | 0 | 0 | 0 |

V5 route counts are 10 exact and 13 v4 control-glyph records in sample 1; 6 exact and 12 v4 control-glyph records in sample 2; and 8 exact and 5 v4 control-glyph records in sample 3. No leafcutter record uses the printable route, and all v4 rejection outcomes remain unchanged.

Sample 3 existed as a saved raw v2 draw with three complete cached responses. Its frozen v4 rule had prepared jobs and protocol artifacts without a completed v4 extraction directory. This run first applied the existing `multispan_v4` mode offline to create the comparison baseline, confirmed identical request hashes and raw proposals, and then applied v5.

## Propolis grounding and semantic review

Both saved propolis candidates pass v5 grounding. V4 accepted 0 of 2 candidates; v5 accepts 2 of 2. Each candidate has one logged quote substitution from emitted U+2011 to cached U+2010, at emitted offset 265 and cached block offset 1431. Each declared section has two logged U+2011-to-U+2010 substitutions at offsets 48 and 61. The logs include the emitted and cached characters, both Unicode code points, and source-bound offsets.

Grounding and semantic retention are separate stages. Both candidates advance to the saved semantic classifications. Those classifications identify 2 secondary statements, 0 direct observations, and 0 focal-eligible records. The v5 focal retention outcome is therefore 0 of 2. One candidate names *Populus nigra* and the other uses the common name `poplar`; both describe the same secondary discussion statement.

## Monarch and attine deltas

| System | Candidates | V4 accepted | V5 accepted | New | Lost | Direction changes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Monarch | 5 | 5 | 5 | 0 | 0 | 0 |
| Attine actinomycete | 11 | 10 | 10 | 0 | 0 | 0 |

All five monarch survivors use exact grounding. All ten attine survivors use exact grounding. The existing attine rejection remains `target_not_in_quote`; v5 adds no record and removes none in either system.

## Synthetic checks

The v5 synthetic artifact contains 157 cases: 107 expected acceptances and 50 expected rejections. All 157 expectations passed. This total includes all 91 inherited v4 cases, every ordered distinct substitution within each printable class, mapping conflicts, ambiguity, missing anchors, and closed-scope cases.

The four required semantic-change adversaries all reject:

- A changed digit next to a hyphen substitution.
- A changed word with a single smart-quote substitution.
- A changed word with a double smart-quote substitution.
- A changed direction word with an NBSP substitution.

Required adversarial result: 4 of 4 passed, with 0 accepted and 4 rejected.

## Verification

Every replay used saved responses with offline mode enabled. Recorded model calls: 0. Recorded network calls: 0. Leafcutter verification preserved 48 prior files, reproduced every v5 scientific output byte for byte, and confirmed that `docs/analysis_plan.md` and `config/analysis.json` match commit `98b5e09199a5eef0c46be452793e953f5a2af31e`. Each system replay also reproduced its v5 outputs byte for byte and retained all protected v4 and original extraction artifacts.

The v5-focused suite passed 19 of 19 tests, and the changed files pass Ruff. The final full repository suite passed 703 tests and has one existing unrelated failure because `src/experiments/viewer.template.html` is absent. The v4 test status records the same missing-template failure.

Reproduction commands:

```shell
.venv/bin/python -m scripts.verify_grounding_v5
.venv/bin/python -m scripts.replay_system_grounding_v5 --system propolis --system monarch --system attine_actino
.venv/bin/python -m scripts.check_printable_confusable_generalization
.venv/bin/python -m pytest -q tests/test_v5_grounding_modes.py tests/test_system_grounding_v5.py tests/test_printable_confusable_grounding.py
```

Machine-readable evidence is in `verification.json`, `generalization_checks.json`, each system's `results/systems/<slug>/grounding_v5/comparison.json`, and the propolis `data/interim/systems/propolis/grounding_v5/run/semantic_review.json`.

## Scope

The propolis failure informed this policy, so propolis is development evidence. The leafcutter, monarch, and attine samples are also saved development artifacts. Synthetic probes test implementation boundaries and do not estimate unseen-run performance.

The curator and extractor may share cached-source errors. Curators can inspect complete cached documents while extraction works chunk-wise. Directions were checked against Table 1 of the original PDF and follow the authors' printed headings, so these are author-assigned groupings rather than inferences from numerical signs. The numerical cell transcription still lacks visual verification. Structured-direction agreement does not adjudicate semantic support in table rows or captions.

The default extractor is unchanged. V1 through v4 remain available, and v5 requires `--grounding multispan_v5`.

Blocked reason: none.

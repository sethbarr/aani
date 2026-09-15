# Saverschek 2010 audit packet

Start with `study_report.md` or the eight-page PDF at
`output/pdf/saverschek_behavioral_audit.pdf` in the workspace/bundle.

The audit covers every natural plant × habitat × day context and the separate
treatment/memory series. Complete context accounting does **not** mean complete
visual verification: 23 simultaneous-assay directions, all graphic coordinates,
and Table 1 numerical glyphs remain unverified. Exact source wording and
provisional numeric normalization are separate fields.

| Artifact | Contents |
| --- | --- |
| `natural_contexts.csv/.jsonl` | All 110 pooled contexts, including 23 unclear directions |
| `behavior_matrix.png/.svg` | Categorical author-direction matrix; not a digitized published graph |
| `source_genus_audit.csv/.jsonl` | All 11 plant names, direction conflicts and exact-taxonomy status |
| `table1_provisional_transcription.csv/.jsonl` | 66 raw numerical tokens; normalized values explicitly provisional |
| `manipulation_phases.csv/.jsonl` | 12 historical/experimental/control/not-performed phase entries and decisions |
| `extraction_candidate_audit.csv/.jsonl` | Original 14 candidates and gates; no curator records in that denominator |
| `evidence_anchors.json` | 71 exact source anchors, hashes and cached-block offsets |
| `figure_table_inventory.json` | All seven figures and Table 1; text versus visual status |
| `figure7_recovered_tail.json` | Caption recovered after References; absent from original model input |
| `source_verification.json` | Source retrieval and failed visual-verification audit |
| `unresolved_items.json` | Direction, treatment, sample-size and taxonomy review queue |
| `secondary_claims.json` | Cited/background claims kept outside current-study natural evidence |
| `curated_directional_observations.jsonl` | 87 curator-created directional contexts, including unresolved taxonomy |
| `taxonomy_matched_directional.jsonl` | 80 contexts passing exact taxonomy matching |
| `combined_contextual_observations.jsonl` | 89 records: prior nine plus 80 curated contexts, replacing old Saverschek rows |
| `combined_genus_eligible_observations.jsonl` | 42 contextual records for ten consistent genera; not 42 independent samples |
| `combined_conflict_hold.jsonl` | 47 contextual records from five conflicted genera |
| `combined_genera.csv/.jsonl` | Six accepted, four rejected, five conflicts before chemistry |
| `sensitivity_counts.csv/.jsonl` | Reaggregation within each design/timing subset |
| `summary.json`, `validation.json` | Counts and deterministic integrity checks |
| `manifest.json` | Input/output SHA-256 hashes and replay command |
| `verification_report.json` | Offline replay, regression checks, taxonomy replay and PDF inspection results |

The rejection genera ready after exact taxonomy are Desmopsis, Hiraea, Randia
and Sorocea. Trema has a high-confidence VARIANT match, not an EXACT match, so
is held. Hymenaea, Inga, Tetragastris, Trichilia and Miconia have mixed directions.
All summaries are conditional on supported observations; unclear cells are not
negative evidence. Natural rejection does not establish antifungal action.

`record_type=curated_aggregate_context` and `provider=manual_curation` identify
Codex-assisted source review. These records use multiple exact anchors and are
not passed off as new Gemini output. `audit_rejection_timing` retains the source
review's richer labels; `rejection_timing` uses the pipeline's three values.
Raw Table 1 plus/minus components remain untyped because the extracted caption
does not explicitly define their uncertainty measure. Do not use those values
as a verified quantitative endpoint.

The combined snapshot uses the current operational acceptability definition.
The strict simultaneous-alternatives subset has one accepted genus and cannot
support the minimum two-per-direction comparison. No chemistry or bioactivity
join was performed; the ten eligible behavioural genera cannot yet meet the
25-joined-genus feasibility target.

Rebuild from the repository root using Python 3.12 and the project dependencies:

```bash
.venv/bin/python -m scripts.build_saverschek_audit
.venv/bin/pytest -q tests/test_saverschek_audit.py
python scripts/render_saverschek_report.py
```

The report renderer additionally needs ReportLab. The workspace uses the bundled
Codex Python runtime for that command. Rendering the PDF for visual inspection
uses `pdftoppm`. Rebuilding data uses only the archived inputs in `manifest.json`;
it makes no model, taxonomy, chemistry or web requests. The protocol commit is
`98b5e09199a5eef0c46be452793e953f5a2af31e`.

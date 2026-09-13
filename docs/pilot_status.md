# Screened pilot status — 2026-09-12

Follow-up: all six pilot records now resolve to four GBIF genera. Three pending
claims have separately audited manual replacements, also taxonomically resolved.
The targeted Saverschek run now supplies Desmopsis rejection and Spondias
acceptance; Hymenaea and Miconia are held out for conflicting source directions.
The provisional combined snapshot is `data/interim/evidence_current/`: six
consistent acceptance genera and one rejection genus, without a chemistry join.
See [the design audit](design_audit.md) for the distinction between harvesting,
single-substrate acceptability and comparative preference. The fixed pilot
counts below remain unchanged.

The full screened Gemini extraction is complete: all 20 jobs across 10 papers
succeeded, with no response failures. Source review retained six acceptance
records from one paper, excluded 26 candidates from the primary evidence table,
and left three for further review. No eligible rejection record survived.

The six retained records report actual cutting of untreated leaves; they still
need taxonomic resolution. This sample cannot support the planned
accepted-versus-rejected comparison. See [Gemini setup](gemini_setup.md) for
configuration and commands.

| Stage | Result |
|---|---|
| Original cached corpus | 30 full texts |
| Relevance screening | 10 included; 20 excluded with source-specific reasons |
| Screened extraction inputs | 20 jobs covering all 10 included papers |
| Full Gemini extraction | 10/10 papers and 20/20 chunks completed; no response failures |
| Candidate records | 47 |
| Automatic schema and grounding checks | 35 passed; 12 rejected |
| Automatic record rejection rate | 12/47 = 25.5%; this is not a semantic accuracy estimate |
| Source review of automatic passes | 6 included; 26 excluded; 3 pending review |
| Retained evidence | 6 acceptance records, all from PMC11543716; no rejection records; taxonomy pending |
| Offline verification | Replayed all 20 jobs; observations, rejections, failures, status and metrics match exactly |
| Added targeted source | Crumière 2021, PMC9292433, cached separately; 2 jobs |

Screening is recorded in [pilot_screening.json](../config/pilot_screening.json).
Included papers may still yield no eligible observations: treatment, behaviour,
direction, textual grounding and taxonomic identity all require record review.
The original pilot manifest has not been replaced by a new selection of papers.

## Full-run review and artifacts

The run is at `data/interim/extraction_gemini/`. The prompt, schema and low-thinking,
32,768-token settings were unchanged from the successful smoke test. Its two
requests were reused from cache. Raw automatic results remain in
`observations.jsonl`, `rejections.jsonl`, `responses/` and `metrics.json`.

`semantic_review.json` records a provenance-checked decision for all 35 automatic
passes. `evidence_review.csv` presents those decisions alongside every quote.
Use `semantic_review_observations.jsonl` for the six retained records;
`semantic_review_excluded.jsonl` and `semantic_review_pending.jsonl` preserve
the other 26 and three records. Review decisions are Codex-assisted source
audits, not an independent human accuracy benchmark.

The retained records cover Arabidopsis, lima bean, faba bean and tococa in
laboratory ant-cutting experiments. They demonstrate observed harvesting,
not field preference or subsequent fungal-garden acceptance. Six records do
not mean six distinct plants or genera. As-written common names need
source-supported scientific-name mapping before GBIF matching.

All 15 records from PMC12847897 were labelled natural by Gemini, but the source
says every substrate was autoclaved. Other exclusions include husbandry-only
claims, artificial orange/rice assays and duplicated secondary passages.
The three pending records comprise two secondary claims needing original-source
verification and one fresh-leaf cutting record that pools control and exposed
colonies. The latter's leaves must not be mislabeled as fungus-dosed.

Empty automatic output does not establish absence of relevant evidence.
PMC9286363 places named foraged plants in missing supplements and overlaps the
Crumière dataset. PMC8778871 lost two candidates because Gemini expanded a
plant name beyond its literal quote; treatment context also requires review.
PMC7541895 lists plant genera detected in garden DNA, without direct
genus-specific collection observations. No failed candidate was silently repaired.

## Earlier smoke review

The latest run is at `data/interim/extraction_gemini_smoke/`, using low thinking
and a 32,768-token cap. Raw model outputs and automatic validation results are
preserved. The separate `semantic_review.json` records review decisions, and
`semantic_review_observations.jsonl` is empty after both grounded candidates
are excluded:

- The E. grandis acceptance record quotes seedlings being offered in an arena
  (`b00018`), without a reported acceptance outcome. Its quote also does not
  isolate the untreated control from the experimentally treated plants.
- The Acalypha wilkesiana acceptance record quotes leaves being placed in the
  arena for daily husbandry (`b00008`), without observed collection or feeding.

The two other candidates describe reduced cutting following experimental
Beauveria treatment. Gemini labelled them `experimentally_treated`, but their
quotes omitted the plant name and failed grounding. This run demonstrates the
plant-in-quote check; it does not verify downstream treatment exclusion.

The initial medium-thinking, 16,384-token run is preserved separately at
`data/interim/extraction_gemini_smoke_medium_16384/`. One chunk exhausted its
output budget and remained incomplete; the other completed but its candidate
required ant-name review. Incomplete responses were not counted as successful
empty extractions.

## Next steps and replay

Resolve the retained names, verify the pending source/context claims, and fill
the direct natural-rejection evidence gap before chemistry or enrichment.
Document extraction changes before further scale-up. To replay this completed run:

```bash
.venv/bin/python -m scripts.extract --provider gemini --screening config/pilot_screening.json --model --offline --output data/interim/extraction_gemini_offline
```

Successful identical requests replay from cache. All HTTP responses are cached
in `data/raw/http/`; authentication headers are not stored. Review
`observations.jsonl`, `rejections.jsonl`, `failures.jsonl`, and `metrics.json`,
then record semantic decisions separately before taxonomy or chemistry work.
A source-grounded quote is necessary but does not verify its interpretation.

The earlier OpenAI smoke remains at `data/interim/extraction_smoke/`. Its API
returned `credit_balance_exhausted` with type `insufficient_quota`; the screened
offline replay at `data/interim/extraction_screened/` records the quota stop.
That provider's credit failure does not prevent Gemini requests.

The separately acquired Crumière paper is an acceptance-data lead. Its input
jobs are at `data/interim/extraction_jobs_targeted_crumiere/`; a targeted run
needs separate output and reporting. See [source gaps](source_gaps.md) for the
other missing primary sources and their access/eligibility limitations.

Local verification: 33 tests pass, Ruff passes, and the frozen analysis files
still match protocol commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.
GBIF v2 was checked against a live, cached `Poa annua` response and its primary
API schema. The adapter now uses `taxonRank` and correctly reads accepted names
from `usage` when `acceptedUsage` is absent, with synonym safeguards retained.

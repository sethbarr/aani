# Pipeline guide

The pipeline is deliberately staged. Each network response is cached under
`data/raw/` by request hash, so a completed stage can be replayed with
`--offline`. The analysis protocol in `docs/analysis_plan.md` must remain
unchanged after its freeze commit.

## Setup

Use Python 3.12 and install the project with its development dependencies:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

For model extraction, put the API key and model name in a local `.env` file.
The example uses the model supplied for this run:

```ini
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4
```

Never commit `.env` or copy the key into a request log. Authentication headers
are intentionally excluded from cache keys and cache files.

## Stage 1: corpus

Retrieve a pilot of 30 open-access papers and their full-text XML:

```bash
.venv/bin/python -m scripts.corpus --limit 30
```

The manifest and retrieval metrics are written to
`data/interim/corpus/`. Unavailable full texts remain in the manifest with a
reason. Add `--offline` to replay only already cached Europe PMC responses.

## Stage 2: extraction

For Gemini, follow [Gemini setup](gemini_setup.md). Use `--provider gemini`
and `GEMINI_MODEL`; its default output is `data/interim/extraction_gemini/`.
The original OpenAI provider remains available with `--provider openai` and
`OPENAI_MODEL`. `EXTRACTION_PROVIDER` in `.env` supplies the provider when the
flag is omitted; the explicit flag takes precedence.

Export exact model inputs first. This is useful for review or for running an
approved model outside the repository:

```bash
.venv/bin/python -m scripts.extract --export data/interim/extraction_jobs
```

Run the Responses API against the jobs:

```bash
.venv/bin/python -m scripts.extract --provider openai --model
```

Add `--offline` when replaying cached Responses API outputs. The command writes complete observations,
partial-paper observations, rejected candidates, failures and a rejection-rate
metric under `data/interim/extraction/`. A response is accepted only when its
structured record has an exact quote, source block and plant name grounding.

The current screened pilot uses the exact command in
[pilot status](pilot_status.md). `--screening config/pilot_screening.json`
applies the audited relevance decisions; `--limit-papers 1` limits a smoke run
to the first included paper. Use a separate output directory for smoke runs.
Each completed response is saved with its request hash and token usage, and
progress is checkpointed per chunk. Exhausted credits or configuration errors
halt further model calls and mark the remaining jobs blocked.

The completed Gemini pilot's `observations.jsonl` contains automatic passes,
not fully reviewed evidence. Its source decisions are in `semantic_review.json`
and `evidence_review.csv`. Six records remain in
`semantic_review_observations.jsonl` and have completed taxonomy. The historical
26 exclusions and three pending records are saved separately; the three pending
claims were subsequently recovered through the documented source-review branch.
Use the reviewed table for downstream work, preserving as-written names and
their source-supported mappings.

## Stages 3–5: joins

Resolve accepted plant names and keep unmatched names for review:

```bash
.venv/bin/python -m scripts.taxonomy
```

For the six source-reviewed pilot records, the verified command is:

```bash
.venv/bin/python -m scripts.taxonomy --observations data/interim/extraction_gemini/semantic_review_observations.jsonl --name-map config/pilot_name_mappings.json --output data/interim/taxonomy_pilot
```

The optional name map is source-specific and contains exact quoted anchors and
the source-document hash. It supplies separate taxonomy query names/ranks while
preserving model wording, original rank and record IDs. Stale sources, duplicate
keys and ungrounded expansions fail before network access. All six resolve to
four genera; full taxonomy outputs replay identically with `--offline`.

Merge the three taxonomy outputs with the completed source-audit replacement:

```bash
.venv/bin/python -m scripts.behaviour --output data/processed/behaviour --taxonomy-supplement data/interim/trema_resolution/manifest.json
```

The three early Saverschek rows are explicitly superseded by 80 audited,
taxonomy-matched contexts, with seven Trema contexts added by the
[September 13 taxonomy supplement](amendment_2026-09-13_trema_taxonomy.md).
This preserves Miconia's contrary directions, which the early extraction omitted.
`observations.jsonl` retains all 96 contexts for sensitivity reaggregation;
`all_genera.jsonl` contains 16 genera; `genera.jsonl` contains eleven eligible genera;
`conflicts.jsonl` contains five
conflicts. Exact source/context deduplication, source/ant/observation counts,
Miconia verification and every replacement hash are saved alongside them.
The older `data/interim/evidence_current/` remains an archived provisional snapshot.

Import a versioned LOTUS or COCONUT occurrence export using the documented CSV
contract in `src/chemistry/occurrences.py`:

```bash
.venv/bin/python -m scripts.chemistry --lotus-export \
  --genera data/processed/behaviour/all_genera.jsonl \
  --output data/processed/chemistry
```

The pinned [LOTUS v4 export](https://doi.org/10.5281/zenodo.6582121) is
CC BY 4.0. Complete download and published checksum verification precede the
local genus filter. Version, URL, retrieval time, file hash, licence, original
row locators and transformation rules are saved in `run_manifest.json`.
All 16 genera are represented in coverage reporting, including conflicts.
The contract CSV is `data/interim/chemistry/occurrence_contract.csv`; it can also
be imported directly with `scripts.chemistry PATH --offline`.
See [chemistry export provenance](chemistry_export.md) for complete details.

Then retrieve ChEMBL whole-organism MIC/IC50 measurements:

```bash
.venv/bin/python -m scripts.bioactivity \
  --occurrences data/processed/chemistry/occurrences.jsonl \
  --primary-genera data/processed/behaviour/genera.jsonl \
  --chemistry-metrics data/processed/chemistry/metrics.json \
  --output data/processed/bioactivity
```

Unknown activity and failed retrievals stay explicit. They are excluded from
the classified-compound denominator rather than being treated as inactive.
The informational `--primary-genera` records the primary structure subset while
retrieving all imported structures for sensitivity completeness. It does not
admit conflicting genera to primary inference. The optional `--behaviour-genera`
instead restricts retrieval and is not used for the final full-sensitivity run.
ChEMBL version, complete assay-organism inventory, batched full-InChIKey matches,
all activity pages, per-compound status and query hashes are cached and recorded.

## Stage 6–7: analysis

After the protocol is committed and the three prepared tables exist, run:

```bash
.venv/bin/python -m scripts.analyse \
  --observations data/processed/behaviour/observations.jsonl \
  --occurrences data/processed/chemistry/occurrences.jsonl \
  --labels data/processed/bioactivity/labels.jsonl \
  --occurrence-metrics data/processed/chemistry/metrics.json \
  --label-metrics data/processed/bioactivity/metrics.json \
  --processed data/processed/analysis --output results
.venv/bin/python -m scripts.funnel
```

Results include the genus table, review table, permutation null, the required
mixed-effects availability/diagnostics and candidate-genera output. Under the
user's [dated reporting amendment](amendment_2026-09-12_reporting_gate.md), fewer
than 25 joined genera or fewer than two per direction returns
`feasibility_failure`, `estimable: false` and null effect/P-value fields. No
permutation, mixed-model estimate or shortlist substitutes for that endpoint.
Missing upstream data emits explicit blocked metrics and schema-bearing empty
artifacts; it does not become an observed zero-coverage result.

The complete prepared-input chain is also available as
`.venv/bin/python -m scripts.run_pipeline --taxonomy-supplement data/interim/trema_resolution/manifest.json`.
Add `--offline` to replay every stage
from local inputs/cached responses. Individual chemistry, behaviour, bioactivity,
analysis and funnel commands also support `--offline`. `--start-at analysis`
resumes after retrieval. The September 13 offline verification covers behaviour,
activity and analysis in `results/offline_replay.json`, reusing the completed
chemistry export scan. The previous full-run replay report is retained at
`results/day2_blockers/offline_replay.json`.

The Saverschek DEVELOPMENT SET baseline is generated from the saved curator audit
and original extraction with `.venv/bin/python -m scripts.recall_baseline`.
Its [report](../results/recall_baseline.md) records separate PRIMARY and CONTEXT
counts, reference provenance and contamination risk. Reproduce the day-two
verification with `.venv/bin/python -m scripts.verify_day2`, then assemble the
combined report with `.venv/bin/python -m scripts.day2_report`.

## Stage 8: prospective experiment planning

Use the source-reviewed assay collection to prepare a diverse-fungus validation
panel and potential laboratory handoffs:

```bash
.venv/bin/python -m scripts.plan_experiments
```

Open `results/experiment_planner/index.html`. Selections and design settings are
in `config/experiment_panel.json`; the command accepts `--records`, `--fungi`, and
`--output` overrides. The generated bundle includes source snapshots, an untested
study matrix, an illustrative layout, and local drafts for Potato, Emerald, and
cultivar access through the Gerardo lab. No partner submission is made.

The OT-2 export is a water-only layout demonstration. Biological methods, doses,
strain identity and availability require resolution before a biological protocol
can be generated. See [experimental workflow scope and commands](experiment_workflows.md).
This stage does not modify the frozen retrospective analysis or produce
biological results.

## Supplied local leads

The Obsidian notes described in [local notes](local_notes.md) can guide a
targeted paper search and manual review. The Wirth complement is a useful
avoidance seed, while the Crumière table is acceptance-only and remains outside
the primary rejection/acceptance contrast until it has quote-grounded evidence.

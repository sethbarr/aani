# aani: chemical information in animal behaviour

**Artificial and animal intelligence. An evolved biological prior, made computable at literature scale.**

When a leafcutter colony refuses a plant, that refusal is a chemical assay run by
evolution, scored against a live fungus and replicated across colonies and
seasons. Fifty years of those observations sit in the literature, unstructured and
unjoinable to chemistry. aani makes them computable: papers in, grounded
behavioural observations out, resolved to accepted plant names, joined to chemical
structures and measured antifungal activity, with a source anchor at every link.

**What this run measured.** The pipeline executes end to end on public data with the
analysis plan frozen before any outcome was seen. The primary test is
non-estimable, and the coverage funnel says precisely why. Two findings stand:

1. **Assay coverage is the binding constraint.** Of 2,183 mapped structures, 24 carry
   an eligible antifungal measurement — 1.1%. Behavioural evidence is recoverable.
   Phytochemistry is recoverable. Whole-organism antifungal activity data for plant
   natural products essentially is not.
2. **Quote-grounding is necessary and far from sufficient.** 61 candidate records,
   41 passed automatic grounding, 9 survived source review. Of the 89 directional
   contexts that reached analysis, 6 came from model extraction and 83 from curator
   audit. The gap is recall, not hallucination: exact-substring grounding cannot
   survive tables, abbreviations and encoding artifacts.

The prior is old; the proposal to mine it dates to zoopharmacognosy work in the
1990s. What is new is that extracting and joining scattered behavioural
observations to chemical structure is now tractable. Leafcutters are case one
because the behaviour is well documented and the target class is unambiguous. The
method is intended to generalise to any coevolved system where a behaviour implies
a chemical claim.

The public repository includes the code, frozen protocol and compact run
summaries. Full texts, raw API caches, complete processed datasets and local
research/build artifacts are excluded. Offline replay requires the prepared
inputs and populated cache described in [the pipeline guide](docs/pipeline.md);
a fresh clone alone cannot reproduce the full run. With those inputs available,
run `.venv/bin/python -m scripts.run_pipeline --offline` without an API key.

The idea has a history: zoopharmacognosy was an established research proposal by
the early 1990s, including Rodriguez and Wrangham's 1993 chapter on medicinal
plant use by animals ([author bibliography](https://kibalechimpanzees.wordpress.com/publications/)).
The contribution proposed here is a reproducible method for extracting scattered
behavioural observations, resolving the organisms they describe, and joining
them to chemistry. Whether enough usable observations exist, and whether their
signal survives that join, are empirical questions.

Leafcutter ants are case one. They provision a cultivated fungus with plant
material. Experiments show that they can learn to reject material harmful to
that fungus ([Herz, Hölldobler & Roces, 2008](https://doi.org/10.1093/beheco/arn016)).
That gives us a specific hypothesis: **plant genera rejected by leafcutters are
enriched for compounds with measured antifungal activity compared with genera
they accept.** Rejection is an imperfect prior: plant nutrients, moisture and
chemistry also influence selection ([Howard, 1990](https://pubmed.ncbi.nlm.nih.gov/28312716/)).

The ecological target is the fungal cultivar. The translational test asks
whether this signal extends to *Candida albicans*, *Cryptococcus neoformans*, and
*Aspergillus fumigatus*. Activity against one fungus does not establish activity
against another. A positive enrichment would justify follow-up experiments;
the deliverable is a prioritisation result, not a drug discovery claim.

## The 72-hour experiment

Build a public-data pipeline linking:

**paper → ant–plant observation → accepted plant name → compound structure → fungal assay**

Every link retains its source. The analysis plan is frozen in a Git commit before
outcomes are examined. Unknown activity stays unknown. Conflicting behavioural
observations and unmatched names remain visible in review tables.

When the prespecified coverage gates pass, the pipeline estimates enrichment
against a permutation null and reports the required clustered models and
sensitivities. Otherwise it returns a coverage funnel and non-estimable status.
The current run does not meet those gates and produces no enrichment claim or
ranked shortlist.

A precise null or negative effect would argue against this prior in the defined
dataset. Sparse coverage or wide uncertainty would leave the hypothesis
unresolved. Neither outcome licenses changing the threshold to manufacture a hit.

The broader method is intended for coevolved systems where a documented behaviour
supports a testable chemical hypothesis. Each new system needs its own mechanism,
comparison group and validation; generalisation is a future test.

## Status and execution

Stages 1-6 have executed. **The primary test is non-estimable at the prespecified
thresholds:** seven joined genera, comprising six accepted and one rejected,
fall below both the 25-genus trigger and the minimum two genera per direction.
Effect estimates and P-values are null. R is installed; lme4 is unavailable,
and no substitute model is fitted.

| Coverage stage | Current result |
| --- | --- |
| Retrieved sources | 33 in this run's corpus lineage: 30 fixed-pilot plus three targeted additions |
| Selected sources | 13: ten formally screened in and three source-following/targeted inclusions |
| Model extraction | 23 jobs; 61 candidates; 41 grounding passes; nine original semantic inclusions |
| Current source-audited evidence | 96 directional contexts before taxonomy; 89 matched contexts; 16 resolved species |
| Genus aggregation | Ten eligible genera: six accepted, four rejected; five conflicts excluded |
| Verified LOTUS chemistry | Eight eligible genera; Desmopsis and Hiraea have missing chemistry |
| Classified-compound coverage | Seven eligible genera; Randia has zero classified compounds and is excluded |
| Primary test | Feasibility failure; no inferential statistic computed |

Curator recovery replaces incomplete model summaries and has separate
provenance; its contexts are not additional model successes or independent
replicates. The Miconia conflict was verified from tococa/M. microphysca acceptance
and Saverschek M. argentea acceptance and rejection. Trema remains on taxonomy
review. See [the machine-readable funnel](results/funnel.json),
[run report](results/pipeline_report.md), and
[Miconia verification](data/processed/behaviour/miconia_verification.json).

Chemistry uses the complete, checksum-verified LOTUS v4 export, with a documented
local genus filter and CC BY 4.0 attribution. Activity retrieval uses ChEMBL 37
and retains unknowns outside the classified denominator. All 2,183 mapped
structures were queried: seven active, 17 inactive and 2,159 unknown, with zero
retrieval failures. The primary subset contains 1,851 structures; the remainder
supports sensitivity reaggregation. See [export provenance](docs/chemistry_export.md).

Run stages 3-6 from the prepared, source-audited taxonomy inputs:

```bash
.venv/bin/python -m scripts.run_pipeline
```

Replay with no network requests:

```bash
.venv/bin/python -m scripts.run_pipeline --offline
```

The [frozen analysis plan](docs/analysis_plan.md) and `config/analysis.json` are
unchanged at commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.
The user's stricter reporting gate is documented in a separate
[dated amendment](docs/amendment_2026-09-12_reporting_gate.md).
See [the pipeline guide](docs/pipeline.md) for individual commands and
[the design audit](docs/design_audit.md) for the distinction between observed
cutting, natural acceptability and comparative preference.

Python 3.12; pandas for tables; validated structured JSON for extraction; R/lme4
for the secondary model. API responses are cached under `data/raw/` by request
hash. Each stage also supports replay from cached or explicitly imported data.

## Prospective experimental validation

The hackathon now includes a [diverse-fungus experiment planner](docs/experiment_workflows.md):
an ant cultivar as an ecological reference, four model-fungus comparisons,
source-linked materials, and local handoff drafts for Potato, Emerald Cloud Lab,
and the Gerardo lab. Those partners and sample sources are possibilities, not
confirmed integrations or arrangements.

Run `.venv/bin/python -m scripts.plan_experiments`, then open
[the offline planner](results/experiment_planner/index.html). It exports a
structured study plan, an illustrative plate map, and a water-only OT-2 protocol.
Biological methods remain unassigned and no experiments have been run. This
prospective work is separate from the frozen retrospective analysis.

## Repository

```text
docs/analysis_plan.md       analysis decisions, frozen before outcomes
docs/local_notes.md         how the supplied Obsidian leads enter review
config/analysis.json        machine-readable analysis constants
src/corpus/                 Europe PMC retrieval and XML parsing
src/extraction/             schema, model requests and grounding checks
src/taxonomy/               GBIF name matching and review queue
src/chemistry/              provenance-preserving occurrence imports
src/bioactivity/            ChEMBL retrieval and activity classification
src/analysis/               joins, permutation test, shortlist and R model
data/raw/                  request-hashed source/API/export cache
data/interim/              original extraction, taxonomy and source audits
data/processed/behaviour/  merged observations, genus table and conflicts
data/processed/chemistry/  imported occurrences and export provenance
data/processed/bioactivity/ ChEMBL labels, measurements and retrieval audit
data/processed/analysis/   prepared primary and sensitivity join tables
results/funnel.json        machine-readable coverage and blocked reasons
results/primary/           non-estimable summary, coverage tables and review
results/experimental/      experimental-evidence sensitivity
results/delayed/           delayed-rejection sensitivity
results/nondiscordant/     discordance sensitivity
results/saverschek_audit/  completed text audit and evidence bundle
results/experiment_planner/ prospective planning artifacts
results/business_case/     project business-case artifacts
output/pdf/               readable reports
scripts/                    one CLI entry point per stage
tests/                      scientific edge cases and offline integration
```

There is no enrichment figure for this run because the feasibility gate fails.

# Chemical information in animal behaviour

**An evolved biological prior, made computable at literature scale.**

Animal behaviour can reveal chemical effects in ecological context. This project
joins that information to chemical structures and assay results, asking whether
it improves where we look for antifungal compounds.

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

The deliverables are an observed enrichment against a permutation null, effect
estimates with uncertainty, and an exploratory shortlist of plant genera for
wet-lab follow-up. The analysis accounts for study effort and family clustering,
and repeats the test using experimental behavioural evidence alone.

A precise null or negative effect would argue against this prior in the defined
dataset. Sparse coverage or wide uncertainty would leave the hypothesis
unresolved. Neither outcome licenses changing the threshold to manufacture a hit.

The broader method is intended for coevolved systems where a documented behaviour
supports a testable chemical hypothesis. Each new system needs its own mechanism,
comparison group and validation; generalisation is a future test.

## Status and execution

This repository is being bootstrapped for the solo Life Sciences hackathon.
See [the analysis plan](docs/analysis_plan.md) for the frozen decisions and
[the pipeline guide](docs/pipeline.md) for commands, data contracts and current
limitations. No enrichment result has been produced.

Python 3.12; pandas for tables; validated structured JSON for extraction; R/lme4
for the secondary model. API responses are cached under `data/raw/` by request
hash. Each stage also supports replay from cached or explicitly imported data.

## Repository

```text
docs/analysis_plan.md       analysis decisions, frozen before outcomes
config/analysis.json        machine-readable analysis constants
src/corpus/                 Europe PMC retrieval and XML parsing
src/extraction/             schema, model requests and grounding checks
src/taxonomy/               GBIF name matching and review queue
src/chemistry/              provenance-preserving occurrence imports
src/bioactivity/            ChEMBL retrieval and activity classification
src/analysis/               joins, permutation test, shortlist and R model
data/{raw,interim,processed}/
results/figures/
scripts/                    one CLI entry point per stage
tests/                      scientific edge cases and offline integration
```

# Multi-span grounding development experiment — September 13, 2026

The baseline at commit `aeb5130341a8c41e0373ad51aabd79b7bbbf3a12` precedes this
experiment. The user requested continuation after the baseline was committed.
This optional experiment tests extraction with separate exact spans for plant
identity, behavioural evidence and supporting table/context statements.

The first run uses the same cached Saverschek paper, nine blocks, three chunk
boundaries, Gemini 3.8 Flash, low thinking and 32,768-token output cap as the
original extraction. Only the optional extraction prompt/schema and grounding
contract change. No curator directions or species reference list enter the model
request. The implementers have seen the reference and original errors, so this
is development on a known set. It tests the combined prompt/schema change;
separating their individual effects would require further experiments.

Each supplied span must occur verbatim within its named block after the same
whitespace normalization used by the original validator. Source text and numerical
glyphs remain unchanged. A separate name span supports an exact, abbreviated
binomial or genus reference in the behavioural quote. Genus references require
semantic review of species identity. Supporting table headings and context spans
retain their original block provenance. Automatic grounding checks source links;
source review must establish the claimed direction, table category membership,
exposure history and experimental context.

The first three-job run is saved under
`data/interim/extraction_saverschek_multispan_v1/`. Original extraction outputs,
reference labels and baseline artifacts remain immutable. Score PRIMARY's six
species and CONTEXT's five species separately, using counts at detection,
survival and adjudicated correctness. CONTEXT also reports both directions,
collapsed to one and absent. A quoted mention of a second direction receives
credit only when a distinct structured record carries it. All surviving panel
candidates require documented semantic adjudication. Missing adjudication makes
correctness unavailable for the affected species, with an explicit reason.

This DEVELOPMENT SET is one panel from one paper and is not a sample from any
population. The reference and extractor share the same source representation;
shared blind spots can inflate apparent recall. The curator saw complete cached
text including tables, while the extractor works chunk-wise with exact quote
requirements. The unverified table category-to-row mapping remains a weaker
reference for five species under the conservative provenance convention.

No biological analysis uses these new extraction records in this experiment.
The frozen files `docs/analysis_plan.md` and `config/analysis.json` remain at
`98b5e09199a5eef0c46be452793e953f5a2af31e`. Activity eligibility, unknown labels,
unanimity and the 25-genus trigger retain their current definitions.

## First-run result and follow-up check

The first model run completed all three jobs, proposed seven records and passed
zero through grounding. It used the model request only once per job. Six records
failed the ant-name gate and one failed the primary-quote plant-name link. All
seven emitted `A. colombica`; the full `Atta colombica` occurs only outside the
middle job that produced them. The model emitted no table-based records. The
[count comparison](../results/grounding_development_v1/compare.md) records PRIMARY
and CONTEXT separately. Zero survivors make correctness zero without a semantic
review of surviving candidates.

Source review also found a lexical validator defect: `S. lindenianum` could pass
as its own purported full-name anchor. That candidate failed the ant-name gate
in the first run. A subsequent code correction rejects abbreviated genus tokens
in species-level full-name anchors. A separate hardened replay uses the same
cached model responses and changes that candidate's rejection reason. It creates
no new model sample and leaves the seven-candidate, zero-survivor counts unchanged.
The first-run files remain intact; verification records both validator hashes.

The unresolved extraction work includes source-anchored ant identity across
chunk boundaries, table coverage and sufficient primary-quote context for
pronouns. These changes require another explicitly versioned experiment. This
run provides no evidence of improved grounding recall.

## Reproduction

Prepared source text and populated local API caches are required; a fresh clone
does not contain these inputs. The optional mode leaves the default extraction
contract and its job hashes unchanged.

```bash
.venv/bin/python -m scripts.extract --provider gemini --model gemini-3.8-flash --grounding multispan_v1 --corpus data/interim/corpus_targeted_saverschek --output data/interim/extraction_saverschek_multispan_v1_hardened_replay --offline
.venv/bin/python -m scripts.compare_grounding --extraction data/interim/extraction_saverschek_multispan_v1 --output results/grounding_development_v1
.venv/bin/python -m scripts.verify_grounding_development
```

The comparison scores the preserved first-run artifacts. The hardened replay
records the subsequent full-name check separately. A future surviving record
requires `--adjudication` with a candidate digest, scientific decision, natural
panel membership, context and exact direction/context source anchors.

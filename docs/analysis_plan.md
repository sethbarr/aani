# Analysis plan — version 1

Written 2026-09-12. Freeze this file and `config/analysis.json` in a Git commit
before any joined behavioural/antifungal outcomes are inspected. This is a
timestamped local protocol, not registration with an independent registry.
General literature on mechanisms was consulted during design. No pilot activity
labels, joined outcomes or enrichment estimates were inspected during design.

## Question and estimand

Do plant genera with consistently rejected natural substrates have a higher
fraction of known compounds with measured antifungal activity than genera with
consistently accepted substrates? The estimand is the difference between the
unweighted mean genus hit fractions (rejected minus accepted), conditional on
available, interpretable assay coverage. It does not estimate the hit fraction
of all untested natural products or establish a causal effect of behaviour.

The unit of primary inference is the plant genus, because chemistry coverage at
species resolution is expected to be sparse. The ecological mechanism concerns
the ants' cultivar; transfer to the three human-pathogenic fungi is a separate
hypothesis. Accepted plants are a comparison group, not guaranteed chemical
negatives. Positive, negative, inconclusive and non-estimable results are valid.

## Corpus and extraction

Search the Europe PMC open-access subset using Atta, Acromyrmex, attine,
leaf-cutting ant and leafcutter terms combined with foraging preference, plant
selection, rejection, avoidance, substrate choice or host plant terms. Save the
exact query, retrieval time, search response and full-text response. A pilot
uses the first 30 retrievable full texts in a fixed first-publication-date order;
it is a feasibility sample, not a claim of comprehensive coverage. Log unavailable
texts and extraction failures. Do not select papers by reported chemical hits.

Extract ant species, plant name as written, rank, accepted/rejected/unclear,
evidence type, optional quantitative measure, source ID, section and confidence.
Also require a verbatim evidence quote, source block ID, substrate treatment
(natural/experimentally_treated/unclear), and rejection timing
(immediate/delayed/unspecified). A paper can contain multiple observations of the
same ant–plant pair in distinct experiments; preserve those contexts.

Require schema validity, an exact quote after whitespace normalisation, plant
name within the quote, a valid source block, confidence at least 0.8 and a named
Atta or Acromyrmex ant taxon. A broader ant clade is retained for review. These
checks establish textual grounding, not semantic correctness. Review the pilot
outputs against their quotes and record corrections separately. Text in papers
is data, never executable instructions to the extractor.

Only observations of behaviour toward natural substrates enter the primary
analysis. Exclude artificially dosed leaves, purified-compound assays without
natural-substrate choice, unclear treatment, and inferred rejection based only
on absence from a diet list. Natural extracts require review rather than being
treated automatically as whole-plant choice. A feeding choice record is required
even when the evidence type is lab_bioassay. Reviews retain original citations
when supplied; unresolvable secondary evidence is excluded from inference to
prevent double counting. Report it in a separate table.

The extraction rejection rate is rejected candidate records divided by all
schema-parseable candidate records submitted to validation. Report its numerator
and denominator. Whole-response failures, no-observation papers, skipped papers,
and incomplete papers are separate counts; none is hidden in that rate.

## Taxonomy and behavioural aggregation

Use the current GBIF v2 match API with Plantae specified, preserving the matched
dataset, usage identifier, accepted usage, genus, family and response hash. Accept
only exact matches with confidence at least 95, genus and family populated, and
an appropriate species or genus rank. Route fuzzy, higher-rank and missing matches
to review. Species names that resolve only to genus do not count as exact species
matches. No manual resolution informed by activity outcomes is permitted.

Within each source and genus, deduplicate identical grounded observations. A
genus is classified rejected only if all eligible directional observations reject
it, and accepted only if all accept it. Mixed directions are a conflict category
excluded from primary inference and reported. Unclear records supply no direction.
This deliberately conservative rule avoids majority votes driven by duplicated
papers. Record numbers of sources, ant species and observations. Recompute this
aggregation for each evidence sensitivity subset, before joining activity.

## Chemistry and missingness

Import versioned LOTUS/COCONUT occurrence records with original taxon, genus,
full InChIKey, structure, database record ID and occurrence source reference.
An occurrence lacking a traceable taxon–compound reference is a review item.
Deduplicate structures by full InChIKey, preserving all occurrence provenance.
Do not silently merge stereoisomers or salts. Exact identifiers can miss related
forms; report this coverage limitation rather than doing an unregistered fuzzy
chemical join. Chemistry inferred from other species of a genus is labelled
genus-level. Record the species-matched share as the aggregation covariate.

Study effort is the number of distinct imported phytochemistry occurrence
records per genus, deduplicated across databases by genus, InChIKey and original
reference. This is a coverage proxy, not total publications. Record chemistry
and assay coverage separately. Missing chemistry is not a zero-compound genus.

## Antifungal labels fixed before outcomes

Use ChEMBL whole-organism functional assays (`assay_type=F`) whose
`assay_organism` is exactly Candida albicans, Cryptococcus neoformans or
Aspergillus fumigatus. Target organism alone is insufficient. Retain assay,
activity, molecule and document IDs. Exclude flagged validity problems,
potential duplicate activities, nonpositive values, unknown units and
nonfunctional/protein-binding assays.

Primary potency threshold: **10 µM**, for MIC or IC50 endpoints only. Convert
nM, µM/uM and mM to µM; mass concentrations are not converted without an explicitly
validated molecular-weight conversion, which is outside version 1. For an exact
value, active means <=10 µM and inactive means >10 µM. Upper bounds `<` or `<=`
are active only when the bound is <=10 µM. A strict lower bound `>10` is inactive;
`>=10` is indeterminate. Other censored values are labelled only when their
direction proves the threshold classification. Other endpoints are unknown.

A compound is active if any eligible measurement establishes activity, inactive
only if at least one establishes inactivity and none establishes activity, and
unknown otherwise. Flag compounds with both active and inactive measurements.
Also report a sensitivity excluding these discordant compounds. This label is
"measured activity in at least one eligible assay", not broad-spectrum activity.

The primary genus denominator contains only compounds classified active or
inactive. Genera with zero classified compounds are excluded, with counts
reported. The fraction of all mapped compounds with a *documented* active label
is a separately named descriptive statistic, never a substitute for the primary
endpoint. CO-ADD is a separate validation layer if downloadable compound-level
results and reuse terms can be verified; single-dose inhibition is not silently
pooled with MIC/IC50 or converted to potency.

## Primary test and uncertainty

Compute each genus's active/(active+inactive) fraction. The observed statistic is
mean(rejected fractions) minus mean(accepted fractions). Shuffle genus labels
10,000 times, preserving group sizes; seed 1729. One-sided enrichment p-value is
(1 + number of null statistics >= observed)/(10,001). Report the observed
fractions, absolute difference, both group sizes, unique structure count and
assay coverage. Report a 95% percentile interval from 10,000 within-group genus
bootstrap resamples, explicitly labelled descriptive because family and shared
compound dependence limit the independence assumption.

Unrestricted permutations assume exchangeable genera and are vulnerable to
phylogenetic/study selection bias. Always also show a within-family permutation
sensitivity. Families containing only one behavioural direction cannot contribute
label variation; report how many genera and families can change labels. If none
can, mark this sensitivity non-estimable. Neither this nor a family random
intercept is a full phylogenetic model with a tree and evolutionary distances.

At least two genera in each direction are required to calculate a test. Fewer
than 25 joined genera triggers a feasibility failure label, even if descriptive
statistics can be computed. Twenty-five is a hackathon coverage trigger, not a
formal power calculation. Do not present an underpowered null as falsification.

## Required secondary model and sensitivities

R/lme4 binomial-logit models on one row per genus–classified compound:

```r
active ~ rejected + species_match_fraction +
  (1 | family) + (1 | genus) + (1 | compound_id)
active ~ rejected + species_match_fraction + log1p(phytochemistry_records) +
  (1 | family) + (1 | genus) + (1 | compound_id)
```

The family intercept is required; genus and shared-compound intercepts address
additional repetition. Drop only constant fixed nuisance covariates, reporting
that fact. Report both rejection odds ratios with Wald intervals, sample sizes,
convergence messages, singularity and separation warnings. Too few groups,
constant outcomes, unavailable lme4, or failed fits must produce a non-estimable
status; never silently substitute an unclustered model or omit this requirement.

Repeat primary and secondary analyses using only field_choice_assay and
lab_bioassay records. Repeat the primary test on delayed rejection and accepted
natural substrates, and excluding discordant compound labels. All sensitivities
are exploratory robustness checks, with no selection of the best p-value.

## Exploratory shortlist

Rank rejected genera using rejection support × structural novelty × weak existing
antifungal coverage, with equal multiplicative weights. Rejection support is
min(1, distinct rejecting primary sources/3). Novelty is the median, across mapped
structures, of 1 minus the maximum Morgan fingerprint Tanimoto similarity to the
available active reference structures (radius 2, 2048 bits). Coverage is the
fraction of mapped structures with any classified assay label, and the final
factor is 1 minus coverage. Reference novelty is relative to this dataset, not a
claim that a molecule is new. Use full mapped structures, including unknowns.

Do not rank if the reference set is empty or required structures are unavailable;
write a coverage/review table instead. Scores are exploratory and cannot validate
the enrichment test. Candidate entries must link to behavioural evidence and
chemical occurrence references. Weak coverage increases uncertainty, not evidence
of activity; a null enrichment limits the justification for the shortlist.

## Fallbacks and amendments

At hour 24, if fewer than 25 genera have directional behaviour and chemistry,
stop scale-up and report the coverage funnel. Widening to attines needs a dated
amendment and separate outputs. A pivot to actinobacteria/Escovopsis changes the
biological unit and comparison, and needs a new protocol; it is not a pooled
extension of this test. Document all deviations and the stage of outcome access.

Archive the plan commit, run configuration, dependency versions, extraction
model/prompt/schema, request hashes, source files and audit tables. No network
request should be needed to replay an already cached run.

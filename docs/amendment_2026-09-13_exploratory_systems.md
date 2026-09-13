# Amendment — exploratory coevolved systems

Written and committed 2026-09-13 before retrieving any corpus for these runs.

These extensions test whether the aani extraction and coverage funnel generalise
to three additional coevolved systems. They are exploratory, unprescribed, and
excluded from every inferential claim in the frozen primary leafcutter analysis.
All inputs and outputs remain under system-specific paths in
`data/interim/systems/` and `results/systems/`; they will never enter the
leafcutter behavioural join. The analysis plan and configuration frozen at
commit `98b5e09` remain unchanged.

Each corpus is limited to 20 open-access Europe PMC sources. Each system is
limited to 12 extraction jobs and uses the current default extractor so that
its funnel is comparable with the leafcutter run. Corpus retrieval timestamps
will be recorded after this amendment commit. The pending Saverschek v2 rerun
has priority for the shared Gemini quota. Any payload-export approval gate stops
that system until approval is supplied. A system that reaches four hours of
wall-clock time stops after its last completed stage and reports a partial
funnel with a blocked reason.

## Outcomes declared before retrieval

### Propolis

Apis mellifera resin collection and propolis deposition, including increased
collection under pathogen challenge, is the behaviour. Collected resin sources
count as accept; available sources lacking observed collection remain unknown.
The chemical target is plant-resin natural products. Taxonomy uses GBIF and
chemistry uses LOTUS. Bioactivity uses the three frozen primary assay organisms:
Candida albicans, Cryptococcus neoformans, and Aspergillus fumigatus.

Expected outcome: propolis is the system most likely to retain records through
the assay join because its chemistry has extensive experimental coverage.

### Monarch

Danaus plexippus oviposition preference among milkweed species by infected and
uninfected females is the behaviour. Preferred plants count as accept; plants
avoided in a choice test count as reject; other absences remain unknown. The
chemical target is milkweed natural products, including cardenolides. Taxonomy
uses GBIF and chemistry uses LOTUS. Bioactivity still uses Candida albicans,
Cryptococcus neoformans, and Aspergillus fumigatus. Ophryocystis elektroscirrha
is outside that ChEMBL assay panel, and the report will state this biological
mismatch explicitly.

Expected outcome: monarch has the strongest behavioural design in this set and
loses coverage at the assay join. That outcome would show that the measured
assay wall generalises to a well-designed behavioural system.

### Attine actinomycete positive control

Attine ant cultivation of cuticular Pseudonocardia that suppresses Escovopsis
is the behaviour. The chemical target is explicitly reported microbial
antifungal compounds. This extraction-only positive control runs corpus,
extraction, and taxonomy stages. It does not run LOTUS chemistry or ChEMBL
bioactivity because the compounds are microbial and LOTUS is a plant occurrence
backend.

Expected outcome: the default extractor recovers known organism-compound-
activity statements, including dentigerumycin, from explicit reports. Recall
will be scored against a reference set built before extraction from Currie et
al. (1999), Nature, and Oh et al. (2009), Nature Chemical Biology. This is the
first positive-control evaluation of aani.


# 2026-09-13 — seeded exploratory monarch rerun

This amendment is written and committed before retrieval for the seeded rerun.
The rerun is exploratory, source-seeded, and excluded from inference. It follows
the first monarch run, whose retained observations did not recover the focal
infected-versus-uninfected female oviposition design.

## Isolation and source selection

The first monarch run and its v4 grounding replay remain unchanged. New data
are confined to `data/interim/systems/monarch_seeded/`; new results are confined
to `results/systems/monarch_seeded/`. The primary plan and analysis configuration
remain frozen at `98b5e09`, and no new records enter the primary leafcutter join.
The amendment commit hash, commit timestamp and file checksum will be recorded
before external retrieval begins.

Five user-proposed citations seed bibliographic verification:

1. Lefèvre, Oliver, Hunter and de Roode (2010), "Evidence for trans-generational
   medication in nature."
2. Lefèvre et al. (2012), "Behavioural resistance against a protozoan parasite in
   the monarch butterfly."
3. de Roode, Pedersen, Hunter and Altizer (2008), "Host plant species affects
   virulence in monarch butterfly parasites."
4. Sternberg et al. (2012), "Food plant derived disease tolerance and resistance
   in the monarch butterfly."
5. Gowler, Leon, Hunter and de Roode (2015), "Secondary defense chemicals in
   milkweed reduce parasite infection in monarch butterflies."

Titles, authors, years and DOIs are hypotheses to verify against retrieved
bibliographic records. Each verified DOI receives a Europe PMC full-text access
attempt where an indexed full-text identifier exists. Record retrieved, not
open access, or not found, with separate metadata and transport-failure detail
when those labels alone would conceal uncertainty. A Europe PMC access flag
describes that service's holdings. It does not establish that every other copy
is paywalled. Paywalled text will not be scraped. Unavailable seeds enter a
DOI-linked source-gap table, and the user will be asked for missing sources.

Retrieved seed texts form `corpus_targeted_monarch/` with separate provenance.
The combined corpus adds them to an isolated copy of the existing 20 ready
discovery texts, deduplicated by source identifier and verified DOI. Every
source receives a recorded screening decision. Complete seed papers have
priority within a maximum of 12 extraction jobs for this rerun; remaining
capacity may contain complete previously screened discovery papers. Partial
papers do not enter the retained extraction cohort.

## Extraction and fixed review rules

Use the same system adapter, model, prompt construction, schema, chunking and
single-quote validator as the first monarch run. Do not switch to multispan or
v4 glyph recovery. Record adapter and configuration hashes. New external model
payloads remain subject to the existing explicit payload-export approval gate.

Fix the seeded review's directional rules before extraction:

- Accept requires a milkweed species preferred in an oviposition choice test.
- Reject requires a milkweed species avoided in an oviposition choice test.
- Absence from a list is never rejection. Unresolved direction remains unknown.

To preserve the original extraction contract, infection status is a required
post-extraction annotation on every reviewed record, including retained
records: `infected`, `uninfected`, or `unreported`. Link assigned infection
status to source, block and quote, and preserve the original model record.
An ambiguous status remains unreported. Unreported records may be retained
with a flag and cannot satisfy the focal design. Different infection groups
must remain separate, with any curator-added context distinguished from
model-proposed records.

Focal recovery requires direct evidence of oviposition choice among milkweed
species and an explicit infected-versus-uninfected comparison of choosing
females. Infection during larval feeding, plant watering treatments, secondary
summaries and isolated infection labels cannot establish that comparison.
Report source-design recovery and model-record recovery separately if the
source contains a comparison that the extractor omits.

## Downstream coverage and expected outcome

Run existing GBIF taxonomy, pinned LOTUS export processing and ChEMBL activity
classification with the three frozen primary fungi and unchanged thresholds.
Re-query the exact assay organism `Ophryocystis elektroscirrha` separately across
all assay types, keeping the count and the query's time/version provenance.
Unknown activity remains unknown and is excluded from classified denominators.
Genus-level directional conflicts remain explicit and follow existing exclusion
rules; they must not be removed to improve coverage. Preserve infection and
treatment context through aggregation.

Expected outcome: accessible primary seeds should improve exposure to the focal
behavioral design. Its actual extraction recovery and the resulting taxonomy,
chemistry and assay coverage will be measured. A surviving fungal-assay join
does not measure the monarch parasite mechanism. No analysis stage, enrichment
statistic or shortlist will run. A source or service gap will be reported with
an explicit blocked reason and unavailable counts.

Cache all retrieval and model responses by request hash. Verify an offline
replay of completed stages and checksum preservation of the first monarch run
and frozen primary files. The final `results/systems/monarch_seeded/summary.md`
will contain a seed-access table, a side-by-side funnel with the first monarch
run, focal-design recovery verdicts, the parasite-assay count, and the observed
endpoint or blocker for each join.

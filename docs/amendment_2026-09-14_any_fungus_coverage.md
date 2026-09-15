# Exploratory sensitivity analysis: any-fungus ChEMBL coverage

Declared 2026-09-14, before any new retrieval for this analysis. The execution manifest records this amendment's commit hash and timestamp. The 90-minute window begins 2026-09-15T00:03:15Z and ends 2026-09-15T01:33:15Z; retrieval will stop early enough to report partial results and verify offline replay.

## Scope and protection

This is an EXPLORATORY SENSITIVITY ANALYSIS of the fixed 2,198 mapped structures, identified by full InChIKey in the existing chemistry occurrences. It changes no primary labels, eligibility rules, enrichment analysis, funnel, or feasibility-failure label. Files frozen at 98b5e09 and primary outputs remain byte-identical. Implementers have seen the primary results and hand audit. Counts describe database coverage in this development dataset.

The existing 24 denotes compounds with a classifiable active/inactive result under the complete frozen rules. Existing retrieval contains measurements for 98 compounds against the frozen three organisms; many measurements cannot produce a frozen label. Broader measurement coverage will be compared with both denominators and will never be described as newly established biological activity.

## Retrieval and identity

Resolve all 2,198 exact full InChIKeys to ChEMBL molecule identifiers, allowing multiple exact matches and retaining unmatched structures in the denominator. Retrieve every activity for those molecule identifiers without organism-name, assay-type, endpoint, units, potency, validity, or duplicate prefilters. Follow every page and check returned counts against the service total. Join each activity to its assay and retain assay organism, assay taxon ID, assay ChEMBL ID, activity ID, and molecule ID. Record service version and provenance.

Resolve assay taxon IDs through a public taxonomy service with NCBI identifiers and ancestor lineages. Fungal membership requires a Fungi ancestor (including the node itself). Taxon names can locate authoritative taxonomic nodes or resolve an absent identifier, but names alone will not establish fungal membership. A name fallback must be an unambiguous exact scientific name or documented synonym with its resolution provenance. Missing, conflicting, or unresolved organism identity remains explicitly unresolved; target-organism fields will not substitute for assay-organism fields. Report residual uncertainty and unqueried records separately from verified zero results.

Cache every request descriptor and response by a deterministic cryptographic hash, including failed attempts and transport errors. Retain raw taxonomy responses and lineage IDs. Use bounded retries and record attempts. Replay retrieval and classification entirely offline, checking hashes and result equality. All new data and reports are isolated under any_fungus_coverage paths.

## Predeclared classification

Tiers overlap at compound level and can overlap at measurement level for organisms with several roles. Taxonomic anchors and their IDs, synonyms, citations, and decisions will be recorded in a versioned mapping before final scoring. Taxonomy determines membership; ecological roles require documented taxon or assay context.

- **T1:** descendants of the three frozen species nodes: Candida albicans, Cryptococcus neoformans, Aspergillus fumigatus. This exploratory species-lineage grouping may include strain-level nodes; the original exact-name eligibility remains unchanged.
- **T2:** other human fungal pathogen lineages, including Candida (including reclassified species and C. auris), Cryptococcus, Aspergillus, Fusarium, dermatophytes, Histoplasma, Coccidioides, Pneumocystis, and Mucorales. T1 measurements are excluded from T2.
- **T3:** plant/agricultural pathogen lineages including Botrytis, Fusarium, Magnaporthe/Pyricularia, Rhizoctonia, and Sclerotinia. Fusarium receives both potential-role tiers when host use is unspecified, with an explicit ambiguous-role flag; this does not assert that its assay tested human or crop infection. Phytophthora is included as a separately flagged oomycete sidecar in T3 and excluded from the any-true-fungus union. Other documented pathogen taxa may be added to the auditable role map with sources before scoring.
- **T4:** Leucoagaricus gongylophorus (including authoritative synonyms) and other taxa specifically documented as attine cultivars. Genus membership alone does not establish ant cultivation. Unresolved broad Leucoagaricus/Leucocoprinus records will be separately flagged as potential cultivar records. Report T4 prominently, including an explicit zero if no resolved records exist.
- **T5:** remaining verified fungi, with model organisms (including Saccharomyces cerevisiae and Neurospora crassa) separately flagged. Residual tier membership does not establish nonpathogenicity; retain an unknown-role flag where appropriate.

Retain all activity records, including qualitative, nonfunctional, flagged, or potentially duplicate measurements. Deduplicate only repeated retrieval of the same ChEMBL activity ID. Counts are database records, not independent experiments. Endpoint groups are MIC, IC50, percent inhibition, zone of inhibition, and other; original endpoint text is retained. MIC and IC50 require those standard types; percent/zone groups use explicit standard type and compatible units, with ambiguous records left in other.

Conversion is assessed independently of organism, endpoint, assay type, validity flags, or potency: finite positive standard values and the frozen units nM, uM, µM, μM, mM only, with the frozen conversion factors. Mass concentrations, percentages, zones, missing values, and unsupported units remain unconvertible. Do not infer a mass-to-molar conversion. Preserve relation and explain that convertibility alone does not establish a frozen active/inactive label.

## Reports and stopping rule

Report unique compound counts and activity counts for every tier, split into convertible/unconvertible and endpoint groups, for all structures, the nine genera with chemistry in the frozen primary join, and the four rejected genera. Derive genus membership from frozen files; compounds shared among genera are deduplicated within each population. Include genus lists, denominator counts, missing taxonomy, incomplete pagination, failed requests, and unqueried molecules/assays. Tiers and conversion subgroups overlap at compound level, so compound counts need not sum.

Write results/any_fungus_coverage/summary.md, coverage.csv (one row per compound per tier, with aligned JSON arrays for organisms, endpoints, values, units, and activity IDs), and measurements.csv (one row per compound/activity/tier for direct inspection), plus machine-readable provenance, taxonomy mapping, and replay verification. Report counts alongside percentages; no statistical test is planned. If T2-inclusive labels appear potentially computable, describe that observation using coverage and the frozen minimum-genera constraint without constructing new labels or recomputing inference.

Stop retrieval by the deadline and report partial tiers with missing draws of data named by molecule, assay, and taxon identifiers as available. Absence of a ChEMBL record does not establish absence of published measurements: extract-level assays and uncurated literature remain a separate gap. Complete the report and offline verification within the window where practical; record any timing deviation.

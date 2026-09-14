# Exploratory coevolved-system runs — 13 September 2026

The system adapter uses an adapted prompt and schema with compound/activity fields and omits the primary `substrate_treatment` and `rejection_timing` fields, so these runs do not test the unchanged default extraction contract. The follow-ups leave propolis with no direct behavioural observation after v5 grounding and attine with partial control recovery and resolved microbial taxonomy. Seeding known primary monarch sources recovered the focal infected-versus-uninfected comparison missed by discovery; its completed fungal bioactivity join is a coverage probe that does not test the monarch-parasite mechanism. Outcome-level generalisation is not established.

## Scope and comparability

The prospective amendment was committed as `495b25d` at 16:31:21 UTC and the system configurations as `bf3923f` at 16:32:55 UTC, before corpus retrieval. Each discovery corpus contains 20 successfully retrieved open-access Europe PMC full texts. Retrieval began at 16:33:46 UTC for propolis, 16:33:39 UTC for monarch, and 16:34:02 UTC for attine. Each system completed by 17:05 UTC, about 30 minutes after retrieval began. Failed full-text attempts remain recorded separately.

All three original extraction runs and their permitted downstream stages completed within the four-hour limit. They used the same `gemini-3.8-flash` model, transport, confidence threshold of 0.8, and single-contiguous-quote grounding approach. The later v5 checks replay saved proposals under a separate grounding rule.

Other material deviations from the requested controlled comparison remain:

- Attine has two additional, purpose-selected reference documents beyond its 20-source discovery corpus: the user-supplied Currie PDF, including its corrigendum, and Oh's cached NCBI BioC author manuscript. This gives 22 available sources and exceeds the requested 20-source cap in total availability. Both supplements were explicitly approved for export. They replaced one discovery paper in the execution selection, preserving whole sources and an 11-job total. The discovery corpus and original prepared payloads remain archived.
- Original monarch discovery screening included adjacent oviposition experiments and secondary accounts; its retained direct comparison concerned watering treatments within one species. The seeded rerun added user-supplied primary sources and recovered the focal infection comparison. Its source selection and semantic review remain separate from the original ancillary cohort.
- The leafcutter comparator includes a separate curator-recovery branch: its nine original retained model records precede 96 directional contexts, comprising six model and 90 curator contexts, with 87 from the Saverschek audit. The current merge has 17 resolved species and 11 eligible genera, as recorded in the [behaviour metrics](../../data/processed/behaviour/metrics.json). The exploratory runs contain no manual recovery of missing model records. These stages have different units and curation histories.

All 33 original extraction jobs completed: 12 propolis, 10 monarch, and 11 attine. Saverschek v2 completion was checked before execution. The follow-ups below retain their own samples and replay provenance. No enrichment statistic, analysis stage, or shortlist was run for these systems. The frozen primary plan, configuration, join, and outputs remain unchanged.

## Propolis

| Funnel stage | Leafcutter comparator | Propolis, including v5 replay |
|---|---:|---:|
| Full-text papers retrieved | 33 | 20 |
| Papers screened in | 13 | 8 |
| Extraction jobs completed | 23 | 12 |
| Model candidates | 61 | 2 |
| Grounded model records | 41 | 0 originally; 2 under v5 |
| Semantically retained model records | 9 | 0 |
| Accepted taxon identities resolved | 17 | 0 |
| Directionally eligible genera | 11 | 0 |
| Genera with chemistry | 9 | 0 |
| Genera with classified compounds | 7 | 0 |

Five complete papers fit the job cap; three other screened-in sources were excluded by that cap. Both original model candidates substituted printable U+2011 for the source U+2010 hyphen in their quotes and section labels, failing exact grounding. The [v5 printable-confusable replay](../grounding_development_v5/summary.md#propolis-grounding-and-semantic-review) resolves those substitutions and passes both candidates through grounding. Semantic review identifies two secondary reports of the same Populus preference statement, zero direct observations and zero focal-eligible records. The corpus's recovered plant-source evidence consists only of secondary reports; no direct behavioural observation was retained.

**Expected outcome:** propolis was expected to have the strongest chance of surviving the assay join. This expectation remains untested downstream because semantic review retains no direct behavioural observation after v5 grounding. Zero genera entered LOTUS and zero compounds entered ChEMBL; no LOTUS scan or ChEMBL query ran for this empty cohort. Its downstream zeros describe propagated empty inputs and provide no estimate of propolis chemistry or assay coverage. The original execution `blocked_reason` is null; the current scientific stopping point is semantic review: **no direct behavioural observation retained**.

Evidence: [v5 grounding and semantic outcomes](../grounding_development_v5/summary.md#propolis-grounding-and-semantic-review), [original semantic audit](propolis/semantic_review.json), [original funnel](propolis/funnel.json), [original execution](propolis/downstream_manifest.json), [original verification](propolis/verification.json).

## Monarch

Seeding known primary sources recovered the focal infected-versus-uninfected comparison that the 20-source discovery corpus missed. This is the same targeted-retrieval effect seen when Saverschek was added to the leafcutter corpus. The [seeded rerun](monarch_seeded/summary.md) completed extraction, semantic review, taxonomy, genus aggregation, chemistry and bioactivity. These exploratory results do not establish biological generalisation.

| Seeded stage | Completed result | Source |
| --- | ---: | --- |
| Retrieved seed full texts | 5 user-supplied PDFs | [Local access manifest](monarch_seeded/local_pdf_access.json) |
| Combined corpus | 25 papers, 8 screened in | [Preparation manifest](monarch_seeded/preparation.json) |
| Extraction jobs | 12: 5 new seed responses, 7 cached discovery responses | [Extraction manifest](monarch_seeded/extraction_manifest.json) |
| Model candidates | 13 | [Funnel](monarch_seeded/funnel.json) |
| Grounded records | 9 | [Funnel](monarch_seeded/funnel.json) |
| Semantically retained records | 4 | [Funnel](monarch_seeded/funnel.json) |
| Resolved names | 2 | [Funnel](monarch_seeded/funnel.json) |
| Retained infection status | 2 infected, 2 uninfected | [Funnel](monarch_seeded/funnel.json) |
| Focal-eligible genera | 1: Asclepias | [Funnel](monarch_seeded/funnel.json) |
| Infection-comparison-eligible genera | 1: Asclepias | [Funnel](monarch_seeded/funnel.json) |
| Mapped compounds | 417 | [Funnel](monarch_seeded/funnel.json) |
| ChEMBL-matched compounds | 69 | [Funnel](monarch_seeded/funnel.json) |

The fungal bioactivity join is a **coverage probe**: one Asclepias compound was classified inactive against the primary fungal panel, and 416 compounds remain unknown. One inactive Asclepias compound against that panel does not test the monarch-parasite mechanism. The genus-level join does not assign every mapped compound to the species tested in the behavioural experiments. [Downstream manifest](monarch_seeded/downstream_manifest.json)

Both infection groups occur in retained model records from the same Lefèvre experiment. The retained targets differ between groups, so the same-target infected/uninfected model panel remains incomplete. Uninfected no-preference records retain unknown direction and supply no directional chemistry inputs. Source-design recovery, retained model records and complete species-by-infection panels remain separate measures. [Semantic review](monarch_seeded/semantic_review.json)

All five requested seed PDFs were supplied locally and identity-verified after the initial public retrieval attempts failed. Europe PMC marks Lefèvre 2010, Lefèvre 2012, de Roode 2008, Sternberg 2012 and Gowler 2015 as `not_open_access`, with no indexed full-text route. The checked university PDF links for the first four returned HTTP 403; Gowler's publisher required subscription access. Local supply does not establish an open-access licence. Only the two Lefèvre papers entered extraction; the other seeds remain background sources in the combined corpus. [Access history](monarch_seeded/seed_access.json) [Local access](monarch_seeded/local_pdf_access.json) [Selected sources](monarch_seeded/preparation.json)

The [assay-scope manifest](monarch_seeded/assay_scope_manifest.json) records 16,322 functional assays across the three primary fungi: 11,912 for *Candida albicans*, 2,038 for *Cryptococcus neoformans* and 2,372 for *Aspergillus fumigatus*. It records 0 assays for the exact name *Ophryocystis elektroscirrha* across all assay types and confirms its absence against the complete inventory. Database assay coverage only; inactivity is unmeasured.

**Expected outcome:** the seeded run recovered the behavioural design and reached the parasite assay-coverage limit. The original discovery run's missing focal comparison remains a historical result. The completed fungal coverage probe provides no test of the monarch-parasite mechanism, and no analysis stage or inferential statistic ran. [Completed funnel](monarch_seeded/funnel.json) [Original discovery funnel](monarch/funnel.json)

## Attine actinomycete positive control

| Funnel stage | Leafcutter comparator | Attine control and discovery, including scoped taxonomy replay |
|---|---:|---:|
| Full-text papers available | 33 | 20 discovery + 2 references |
| Papers screened in | 13 | 5 discovery + 2 references |
| Extraction jobs completed | 23 | 11 |
| Model candidates | 61 | 11 |
| Grounded model records | 41 | 10 |
| Semantically retained model records | 9 | 5 |
| Accepted taxon identities resolved | 17 | 0 originally; 1 under the scoped microbial rule |
| Resolved genera | 11 eligible plant genera | 0 originally; 1 bacterial genus under the scoped rule |
| Genera with chemistry | 9 | N/A |
| Genera with classified compounds | 7 | N/A |

Three complete discovery papers and both complete reference documents were extracted. The five retained records contain two direct primary observations and three secondary reports. Semantic exclusions address unsupported activity claims, parent-compound versus analog confusion, and a reject claim lacking the required comparison in its quote.

| Fixed reference item | Full source exposed | Candidate records from that source | Recovered |
|---|---|---:|---|
| Currie 1999: historical *Streptomyces*–antibiotics–*Escovopsis* suppression | Yes, including corrigendum | 0 | 0/1 |
| Oh 2009: *Pseudonocardia*–dentigerumycin–*Escovopsis* inhibition | Yes, available author-manuscript text | 1 | 1/1 |
| Total | 2/2 | 1 | **1/2 (50%)** |

The two-item reference denominator was fixed before extraction. Recovery requires a semantically valid, quote-grounded producer–compound/class–target–inhibition record from the reference source; partial matches and secondary mentions do not count. The fixed control remains 1/2 recovered: Oh supplies the complete relation, while the diagnosed Currie miss reflects the prompt's modern *Pseudonocardia* target and the historical *Streptomyces* producer name in the 1999 source. The [Currie recovery diagnosis](attine_actino/currie_recovery/summary.md) records zero recoveries in three samples: samples 1 and 2 were empty, and sample 3 proposed the corrigendum's family statement while repairing printed line-break hyphenation, causing quote grounding to fail. The original *Streptomyces* wording remains separate from the later Pseudonocardiaceae family correction.

All five reviewed records name *Pseudonocardia*. The original filter rejected the exact GBIF genus match: confidence 93 was below its threshold of 95, and the response places Bacteria at domain and Bacillati at kingdom. The [scoped microbial taxonomy replay](attine_actino/taxonomy_microbial/summary.md) requires bacterial domain, exact genus rank, an `EXACT` match and confidence at least 90; it resolves all five records to one accepted *Pseudonocardia* genus using the cached response. This rule applies only to the microbial control. The original taxonomy outputs, plant rules and fixed control recovery score remain unchanged.

**Expected outcome:** recovery of explicit known compound–activity statements was partially observed, at 1/2 reference items. The scoped replay now completes taxonomy; chemistry and bioactivity remain disabled by design because this is a microbial extraction control. The remaining measured limitation is incomplete control recovery. The original execution `blocked_reason` is null, and its earlier taxonomy loss remains recorded in the original funnel.

Evidence: [Currie recovery diagnosis](attine_actino/currie_recovery/summary.md), [scoped microbial taxonomy](attine_actino/taxonomy_microbial/summary.md), [fixed reference set](attine_actino/reference_set.json), [source preparation](attine_actino/control_preflight.json), [semantic review](attine_actino/semantic_review.json), [positive-control scoring](attine_actino/positive_control.json), [original funnel](attine_actino/funnel.json), [original verification](attine_actino/verification.json).

## Reproducibility and interpretation

Each system has a request-hashed response cache, immutable model responses, source/block/quote provenance, recorded screening and semantic decisions, and separate offline replay outputs. For the original runs, all 20 discovery texts per system and all 33 extraction responses replayed; downstream records and scientific metrics were compared against replay artifacts. Verification also checks the approved payload hashes, reference-source checksums, and the primary funnel's recorded input hashes. Unknown activity is excluded from classified denominators. Missing or unavailable data retain explicit statuses, and absence from a list never supplies rejection.

The original verification passed all 859 artifact checks: 247 for propolis, 336 for monarch, and 276 for attine, with zero failed or unavailable checks. Its focused and stage-regression suite passed 82 tests; Ruff and whitespace checks passed. The linked v5, Currie and microbial-taxonomy reports document their own replay scopes. The seeded monarch report verifies completed extraction and downstream replay. Its overall preservation audit still fails the original file-set check because concurrent grounding files were added; captured file hashes remain unchanged. Concurrent unrelated workspace changes were preserved.

The current comparison identifies secondary-only recovered evidence for propolis, recovered focal behavioural evidence with a parasite assay-coverage gap for seeded monarch, and incomplete control recovery for attine after scoped taxonomy resolution. Its adapted extraction contract, corpus composition, source supplements, and differing curation histories limit generalisability claims. Outcome-level generalisation is not established; the reusable architecture and explicit funnel retain each system's distinct evidence limits.

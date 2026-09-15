# Any-fungus ChEMBL coverage of the mapped plant structures

Exploratory sensitivity analysis declared in
docs/amendment_2026-09-14_any_fungus_coverage.md. It describes database coverage
of the fixed mapped structures and changes no primary label, eligibility rule,
enrichment result, funnel or feasibility-failure label. Broader measurement
coverage is never newly established biological activity. Counts are database
records, not independent experiments.

Tiers overlap at compound and measurement level, so tier counts do not sum to any
total. A measurement on an assay carrying several roles is counted in each tier
it belongs to.

## 1. T4, reported first

**T4 resolved records: 0 compounds, 0 measurements.**

No cached assay resolves to Leucoagaricus gongylophorus, to its
authoritative synonyms, or to any other taxon documented as an attine
cultivar. This is a verified zero across the retrieved records, not an
unqueried gap: every assay identifier returned by the activity query was
fetched and every assay taxon resolved.

The absence of a ChEMBL record does not establish absence of published
measurements. Extract-level assays and uncurated literature remain a
separate gap that this retrieval cannot see.

Cross-check at the level of recorded names, which does not itself establish
membership: 0 cached assays carry an organism name mentioning
Leucoagaricus, Leucocoprinus, Myrmecopterula, Attamyces or Conioexocarpus,
and 0 carry a description mentioning attine or
leaf-cutting cultivation.

One caveat is recorded rather than hidden: the T4 anchor Leucoagaricus weberi did not resolve to a taxonomic node, so no
assay could have been matched to it by lineage. The name cross-check
above covers that gap, since no assay in the cache carries a name in
any of these genera at all.

Potential-cultivar records held separately: 0 measurements on broad Leucoagaricus, Leucocoprinus, Myrmecopterula or Conioexocarpus nodes that genus membership alone does not establish as ant-cultivated. These are excluded from the T4 counts above.

## 2. Coverage by tier, all mapped structures

Mapped structures in the denominator: 2198.

| Tier | Compounds with at least one measurement | Measurements | Convertible units | Non-convertible units | Distinct assay taxa |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 141 | 598 | 91 | 507 | 4 |
| T2 other human fungal pathogens | 115 | 773 | 73 | 700 | 63 |
| T3 plant and agricultural pathogens | 96 | 1282 | 53 | 1229 | 86 |
| T5 remaining verified fungi | 220 | 1047 | 280 | 767 | 46 |

### Endpoint groups

| Tier | MIC | IC50 | percent inhibition | zone of inhibition | other |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 236 | 60 | 52 | 30 | 220 |
| T2 other human fungal pathogens | 320 | 29 | 49 | 54 | 321 |
| T3 plant and agricultural pathogens | 112 | 25 | 223 | 67 | 855 |
| T5 remaining verified fungi | 96 | 236 | 264 | 20 | 431 |

Convertible means a finite positive standard value in one of nM, uM, µM, μM, mM. Mass
concentrations, percentages, zone diameters, missing values and every other unit
are non-convertible, and no mass-to-molar conversion is inferred. Convertibility
is assessed independently of organism, endpoint, assay type, validity flag and
potency, and it does not establish a frozen active or inactive label. Relations
are retained unaltered in the coverage table.

### Model organisms inside T5

| Group | Compounds | Measurements |
| --- | ---: | ---: |
| Declared model organisms | 151 | 492 |
| All other T5 taxa | 140 | 555 |
| of which Neurospora crassa | 1 | 1 |
| of which Saccharomyces cerevisiae | 149 | 480 |

Residual tier membership does not establish that a taxon is non-pathogenic.
Taxa outside the declared model set retain an unknown ecological role.

### Organisms carrying more than one tier

Assay taxa assigned to more than one tier: 20. Their measurements are counted in each tier they carry.

| Assay taxon | Tiers |
| --- | --- |
| Alternaria alternata | T2, T3 |
| Curvularia lunata | T2, T3 |
| Fusarium | T2, T3 |
| Fusarium culmorum | T2, T3 |
| Fusarium equiseti | T2, T3 |
| Fusarium fujikuroi | T2, T3 |
| Fusarium graminearum | T2, T3 |
| Fusarium incarnatum | T2, T3 |
| Fusarium oxysporum | T2, T3 |
| Fusarium oxysporum f. sp. dianthi | T2, T3 |
| Fusarium oxysporum f. sp. lycopersici | T2, T3 |
| Fusarium oxysporum f. sp. niveum | T2, T3 |
| Fusarium oxysporum f. sp. vasinfectum | T2, T3 |
| Fusarium solani | T2, T3 |
| Fusarium sp. | T2, T3 |
| Fusarium tucumaniae | T2, T3 |
| Fusarium udum | T2, T3 |
| Fusarium verticillioides | T2, T3 |
| Lasiodiplodia theobromae | T2, T3 |
| Rhizopus stolonifer | T2, T3 |

Oomycete records inside T3: 21 compounds, 55 measurements. Oomycetes are not true fungi and are excluded from any any-true-fungus union.

## 3. Coverage by tier, the nine genera with chemistry

Genera (9): Acalypha, Arabidopsis, Ocimum, Phaseolus, Randia, Sorocea, Spondias, Trema, Vicia. Mapped structures in this population: 1866.

| Tier | Compounds with at least one measurement | Measurements | Convertible units | Non-convertible units | Distinct assay taxa |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 128 | 573 | 88 | 485 | 4 |
| T2 other human fungal pathogens | 110 | 757 | 73 | 684 | 62 |
| T3 plant and agricultural pathogens | 91 | 1238 | 53 | 1185 | 84 |
| T5 remaining verified fungi | 202 | 984 | 274 | 710 | 46 |

### Endpoint groups

| Tier | MIC | IC50 | percent inhibition | zone of inhibition | other |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 228 | 57 | 52 | 30 | 206 |
| T2 other human fungal pathogens | 310 | 28 | 46 | 54 | 319 |
| T3 plant and agricultural pathogens | 112 | 23 | 211 | 63 | 829 |
| T5 remaining verified fungi | 96 | 227 | 258 | 20 | 383 |

## 4. Coverage by tier, the five rejected genera

Genera (5): Desmopsis, Hiraea, Randia, Sorocea, Trema. Mapped structures in this population: 101.

| Tier | Compounds with at least one measurement | Measurements | Convertible units | Non-convertible units | Distinct assay taxa |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 9 | 49 | 11 | 38 | 3 |
| T2 other human fungal pathogens | 7 | 29 | 2 | 27 | 15 |
| T3 plant and agricultural pathogens | 6 | 24 | 0 | 24 | 13 |
| T5 remaining verified fungi | 13 | 59 | 23 | 36 | 4 |

### Endpoint groups

| Tier | MIC | IC50 | percent inhibition | zone of inhibition | other |
| --- | ---: | ---: | ---: | ---: | ---: |
| T4 Leucoagaricus and attine cultivar fungi | 0 | 0 | 0 | 0 | 0 |
| T1 frozen three species lineages | 15 | 13 | 3 | 0 | 18 |
| T2 other human fungal pathogens | 11 | 5 | 5 | 1 | 7 |
| T3 plant and agricultural pathogens | 1 | 3 | 3 | 1 | 16 |
| T5 remaining verified fungi | 3 | 27 | 12 | 1 | 16 |

## 5. Assay taxa contributing to each tier, all structures

### T4

No assay taxon contributes to this tier.

### T1

| Assay taxon | Measurements | Compounds |
| --- | ---: | ---: |
| Candida albicans | 420 | 138 |
| Cryptococcus neoformans | 112 | 73 |
| Aspergillus fumigatus | 65 | 27 |
| Candida albicans SC5314 | 1 | 1 |

### T2

| Assay taxon | Measurements | Compounds |
| --- | ---: | ---: |
| Aspergillus niger | 77 | 36 |
| Nakaseomyces glabratus | 73 | 23 |
| Aspergillus flavus | 64 | 23 |
| Fusarium graminearum | 61 | 6 |
| Lasiodiplodia theobromae | 46 | 16 |
| Fusarium oxysporum | 39 | 11 |
| Lodderomyces parapsilosis | 39 | 22 |
| Candida tropicalis | 32 | 20 |
| Pichia kudriavzevii | 29 | 21 |
| Trichophyton mentagrophytes | 29 | 22 |
| Curvularia lunata | 25 | 6 |
| Trichophyton rubrum | 25 | 16 |
| Fusarium verticillioides | 23 | 6 |
| Nannizzia gypsea | 17 | 9 |
| Fusarium oxysporum f. sp. niveum | 16 | 2 |
| 48 further taxa | | |

### T3

| Assay taxon | Measurements | Compounds |
| --- | ---: | ---: |
| Monilinia laxa | 199 | 1 |
| Diplodia seriata | 75 | 16 |
| Colletotrichum acutatum | 71 | 19 |
| Fusarium graminearum | 61 | 6 |
| Rhizoctonia solani | 57 | 13 |
| Colletotrichum gloeosporioides | 56 | 30 |
| Lasiodiplodia theobromae | 46 | 16 |
| Botrytis cinerea | 43 | 12 |
| Botryosphaeria dothidea | 41 | 16 |
| Colletotrichum truncatum | 39 | 1 |
| Fusarium oxysporum | 39 | 11 |
| Sclerotinia sclerotiorum | 35 | 4 |
| Neofusicoccum luteum | 27 | 14 |
| Neofusicoccum parvum | 27 | 13 |
| Neofusicoccum ribis | 26 | 7 |
| 71 further taxa | | |

### T5

| Assay taxon | Measurements | Compounds |
| --- | ---: | ---: |
| Saccharomyces cerevisiae | 480 | 149 |
| Agaricus bisporus | 363 | 95 |
| Plenodomus lingam | 32 | 6 |
| Corticium | 26 | 13 |
| Penicillium chrysogenum | 19 | 19 |
| Williopsis jadinii | 16 | 16 |
| Trichoderma viride | 14 | 5 |
| Zygosaccharomyces bailii | 12 | 2 |
| Saccharomyces sp. | 9 | 9 |
| Schizosaccharomyces pombe | 8 | 2 |
| Curvularia | 6 | 1 |
| Helminthosporium | 5 | 1 |
| Pestalotiopsis sp. | 5 | 1 |
| Penicillium citrinum | 4 | 4 |
| Trametes versicolor | 4 | 2 |
| 31 further taxa | | |

## 6. Provenance, denominators and residual uncertainty

- ChEMBL service: ChEMBL_37, released 2026-05-01
- Mapped structures in the denominator: 2198
- Structures resolving to at least one ChEMBL molecule: 854
- Structures with no exact ChEMBL match, retained in the denominator: 1344
- Activities retrieved: 96406
- Assays retrieved: 37018
- Assays carrying no assay organism taxon: 5764
- Assays whose taxon did not resolve: 0
- Assays assigned to at least one tier: 1961
- Measurement rows after the compound and tier join: 3700
- Cached pages reporting an incomplete status: 0
- Unresolved T2 anchors: Wickerhamomyces anomalus
- Unresolved T4 anchors: Leucoagaricus weberi

Absence of a ChEMBL record does not establish absence of published
measurements. Extract-level assays and uncurated literature remain a separate
gap this retrieval cannot see.

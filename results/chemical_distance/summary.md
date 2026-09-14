# Chemical distance and retrieved assay coverage within the plant corpus

**This analysis produces a distance measurement and a ranked test list only.**
It contains no predicted activity label, no probability and no imputed value.
Compounds of unknown activity remain of unknown activity. Nothing here is
admissible to the enrichment analysis, and the feasibility-failure label is
unchanged.

## 1. Reference set: compounds with eligible measurements retrieved

The reference set is every compound for which the bioactivity stage retrieved
at least one measurement on an eligible functional assay against the target
fungi, verified against the complete eligible assay inventory.

- Eligible functional assay inventory: 16322 assays
- Assay organisms present: Aspergillus fumigatus, Candida albicans, Cryptococcus neoformans
- Requested organisms: Candida albicans, Cryptococcus neoformans, Candida auris, Aspergillus fumigatus
- Requested but absent from the frozen inventory: Candida auris
- Reference compounds: 98
- Active under the frozen 10 uM threshold: 7 (7.1%)
- Inactive under the frozen 10 uM threshold: 17 (17.3%)
- Tested but not classifiable, so still unknown: 74 (75.5%)
- With a structure RDKit could resolve: 98 (100.0%)

Classified compounds number 24, being 7 active and 17 inactive. The remainder were measured on an eligible assay whose value could not be read against the frozen threshold, often because the reported units were not converted to a molar concentration under the frozen rules.

## 2. Query set: unknown-activity plant structures

- Unknown-activity compounds: 2174
- With a structure RDKit could resolve: 2174 (100.0%)
- Without a resolvable structure, excluded from every distance: 0 (0.0%)
- Already carrying an eligible measurement that yielded no usable label: 74 (3.4%)

Each compound identifier is excluded from its own reference set. Distinct
identifiers can have identical fingerprints; the robustness analysis separately
collapses those classes to test sensitivity to repeated representations.

A further 22 query compounds (1.0%) carry fewer than 6 heavy atoms. Small structures
can set few fingerprint bits and have low similarity because of their size.
The two single-atom records lead the current ranking. The table retains heavy-atom
counts; the predeclared robustness analysis evaluates a size-filtered population.


## 3. Nearest-neighbour similarity distributions

Morgan fingerprints, radius 2, 2048 bits. Maximum Tanimoto similarity to any
compound in the stated reference set.

| Query set | n | Median | Q1 | Q3 | Min | Max | Below 0.4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unknown activity vs tested set | 2174 | 0.330 | 0.232 | 0.515 | 0.000 | 1.000 | 1325 (60.9%) |
|   of which no eligible measurement was retrieved | 2100 | 0.320 | 0.229 | 0.500 | 0.000 | 1.000 | 1309 (62.3%) |
|   of which tested but unclassifiable | 74 | 0.640 | 0.412 | 0.759 | 0.185 | 1.000 | 16 (21.6%) |
| Classified vs tested set (leave-one-out) | 24 | 0.649 | 0.491 | 0.727 | 0.247 | 1.000 | 3 (12.5%) |
| Unknown activity vs classified set | 2174 | 0.227 | 0.169 | 0.372 | 0.000 | 1.000 | 1694 (77.9%) |
| Classified vs classified (leave-one-out) | 24 | 0.439 | 0.321 | 0.599 | 0.163 | 0.667 | 9 (37.5%) |

The 0.4 similarity threshold is a working convention for
flagging a query compound as outside the applicability domain of a reference
set. Changing this convention changes the counts below the threshold. The
median-similarity randomization comparison is independent of that threshold.

## 4. Bemis-Murcko scaffold overlap

| Query set | Distinct scaffolds | Also in tested set | Compounds on a shared scaffold | Compounds with no Murcko scaffold |
| --- | ---: | ---: | ---: | ---: |
| Unknown activity | 809 | 37 (4.6%) | 437 (20.1%) | 385 |
| Classified | 14 | 14 (100.0%) | 21 (87.5%) | 3 |

The classified row shares every scaffold with the tested set by construction,
because those compounds are themselves members of it. The row is reported for
completeness and carries no information about scaffold coverage.

## 5. Per-genus statistics for unknown-activity compounds

A compound reported from several genera is counted once in each, so the
genus counts sum to more than the query set.

| Genus | Behavioural direction | n unknown | Median | Q1 | Q3 | Below 0.4 | Scaffolds | Shared |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Acalypha | accepted | 83 | 0.450 | 0.276 | 0.615 | 35 (42.2%) | 61 | 12 |
| Arabidopsis | accepted | 955 | 0.318 | 0.219 | 0.500 | 586 (61.4%) | 294 | 17 |
| Hymenaea | conflict | 50 | 0.230 | 0.208 | 0.391 | 37 (74.0%) | 23 | 1 |
| Inga | conflict | 61 | 0.351 | 0.306 | 0.446 | 37 (60.7%) | 37 | 4 |
| Miconia | conflict | 46 | 0.482 | 0.298 | 0.742 | 23 (50.0%) | 25 | 5 |
| Ocimum | accepted | 302 | 0.489 | 0.298 | 0.655 | 115 (38.1%) | 126 | 21 |
| Phaseolus | accepted | 392 | 0.331 | 0.231 | 0.524 | 243 (62.0%) | 167 | 21 |
| Randia | rejected | 12 | 0.311 | 0.295 | 0.333 | 12 (100.0%) | 6 | 0 |
| Sorocea | rejected | 61 | 0.311 | 0.261 | 0.527 | 35 (57.4%) | 55 | 3 |
| Spondias | accepted | 89 | 0.375 | 0.303 | 0.517 | 46 (51.7%) | 23 | 3 |
| Trema | rejected | 26 | 0.505 | 0.309 | 0.657 | 10 (38.5%) | 21 | 7 |
| Trichilia | conflict | 212 | 0.251 | 0.188 | 0.316 | 174 (82.1%) | 118 | 9 |
| Vicia | accepted | 208 | 0.449 | 0.282 | 0.722 | 90 (43.3%) | 92 | 19 |

## 6. Retrieved reference coverage under random selection

Each of 2000 draws takes a random subset of the corpus the size of the
tested set and measures how far it leaves every compound it does not contain. The
observed statistic is built identically, so no compound is ever its own neighbour
and membership of the reference set cannot inflate either number. This is the
control the classified-versus-unknown contrast cannot provide.

| Quantity | Value |
| --- | ---: |
| Median similarity, observed against the real tested set | 0.320 |
| Median similarity, random subsets of the same size | 0.400 |
| Random subsets, central 95% range | 0.377 to 0.425 |
| Draws at or below observed | 0 of 2000 |
| p | 0.0005 |

The observed median similarity is below the central 95% range of random-reference
statistics. This describes the retrieved reference's coverage within this corpus
under the size-matched randomization. Genus composition, molecular size, and
duplicate fingerprints require separate sensitivity checks.

### How much of the distance is the small reference set

| Reference compounds | Median nearest-neighbour similarity | Draws averaged |
| --- | ---: | ---: |
| 10 | 0.177 | 200 |
| 25 | 0.229 | 200 |
| 50 | 0.276 | 200 |
| 98 | 0.320 | 1 |

These points show sensitivity to reference size within the retrieved set.
The randomization matches the observed reference count. Expanding the retrieved
reference can change both similarities and the observed-versus-null comparison.

## 7. Limitations that bound every number above

**Reference membership is limited to compounds with eligible measurements
retrieved during this pipeline.** Activities were filtered by plant compound.
The 16322 eligible assays define the assay inventory; their complete set of
measured compounds was not retrieved. These similarities use the 98 retrieved
reference compounds. Adding compounds to a fixed reference can only increase or
preserve nearest-neighbour similarities for a fixed query set. The observed-versus-null
contrast can change direction when the reference and its randomization are expanded.

**Candida auris is absent
from the frozen inventory.** The retrieval asked ChEMBL for three organisms,
so nothing here speaks to that species.

**Reference and query are drawn from the same corpus.** Every reference
compound is also a plant structure from these genera, so this measures
distance within the corpus. Its relation to the wider antifungal assay universe
requires a broader reference retrieval.

## 8. Verdict

Compounds with no eligible assay measurement retrieved have median similarity
0.320 to the retrieved reference, compared with a random-reference median of 0.400.
The central 95% of random-reference statistics span 0.377–0.425; zero of 2000 draws
are at or below the observed value. Retrieved but unclassifiable compounds have
median similarity 0.640, and 37 of 809 unknown-compound scaffolds occur in the
reference. This comparison describes coverage within the retrieved plant corpus.
Its cause and its relationship to all compounds with antifungal assay data remain
unresolved.

The [predeclared robustness analysis](../chemical_distance_robustness/summary.md)
evaluates size filtering, fingerprint collapse, genus composition, and matched
random references. The original numerical tables, ranked CSV, and run manifest
are unchanged by this wording correction.

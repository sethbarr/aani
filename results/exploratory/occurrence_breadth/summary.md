# Occurrence breadth of tested versus untested structures in LOTUS

**Exploratory, not prespecified.** Post hoc analysis outside the frozen analysis plan at commit `98b5e09199a5eef0c46be452793e953f5a2af31e`. It reads the frozen chemistry join and bioactivity labels and changes nothing in them. Nothing here enters the primary analysis or alters its feasibility status.

## Question

Are the structures that carry a ChEMBL measurement against the three target fungi more taxonomically widespread across the full LOTUS v4 export than the structures without one?

## Definitions

- Tested: A structure is tested when the bioactivity stage assigned it an active or inactive label: at least one ChEMBL measurement on a functional assay against Candida albicans, Cryptococcus neoformans or Aspergillus fumigatus, with an eligible endpoint, a molar unit and a potency readable against the frozen threshold (labels.jsonl, label != unknown).
- Untested: every other mapped structure in the chemistry join, including the structures with a retrieved measurement that could not be read against the frozen threshold.
- Breadth: distinct organisms, genera, families and references over every row of the complete LOTUS export whose InChIKey (structure level) or InChIKey first block (connectivity level) matches. Genus and family come from LOTUS's aligned rank arrays; no taxonomy service was called. References are distinct DOI, else PMCID, else PMID, else the raw reference value.
- Difference in medians is tested with 10,000 label permutations at a fixed seed, as in the chemical-distance null model; p-values carry the plus-one correction. p (greater) is one-sided for tested more widespread; rank-biserial is 2*AUC-1 with ties counted as half, positive when tested units rank higher.

## Collapse to connectivity

- Mapped structures: 2198; distinct first blocks: 1620 (578 structures collapse into another structure's block).
- Tested structures: 24; tested first blocks: 24 (0 collapse). A block is tested when any of its stereoisomers is tested.

## Tested versus untested

| Level | Metric | n tested | n untested | Tested median (IQR) | Untested median (IQR) | Difference | p (greater) | p (two-sided) | Rank-biserial |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| structure | organisms | 24 | 2174 | 140 (53.5-338.5) | 4 (1-25) | +136 | < 0.0001 | < 0.0001 | +0.707 |
| structure | genera | 24 | 2174 | 87.5 (42-179.75) | 3 (1-19) | +84.5 | < 0.0001 | < 0.0001 | +0.706 |
| structure | families | 24 | 2174 | 44.5 (18-93.5) | 3 (1-14) | +41.5 | < 0.0001 | < 0.0001 | +0.696 |
| structure | references | 24 | 2174 | 100.5 (55-293.25) | 4 (1-22) | +96.5 | < 0.0001 | < 0.0001 | +0.735 |
| connectivity | organisms | 24 | 1596 | 175.5 (93-382) | 7 (2-45) | +168.5 | < 0.0001 | < 0.0001 | +0.713 |
| connectivity | genera | 24 | 1596 | 136.5 (51-192) | 6 (1-29) | +130.5 | < 0.0001 | < 0.0001 | +0.692 |
| connectivity | families | 24 | 1596 | 63.5 (18.5-100.25) | 4 (1-18) | +59.5 | < 0.0001 | < 0.0001 | +0.663 |
| connectivity | references | 24 | 1596 | 129 (92.75-323.25) | 7 (2-35.25) | +122 | < 0.0001 | < 0.0001 | +0.752 |

## Confound: breadth as a proxy for how well studied a compound is

Distinct genera compared within quartiles of distinct LOTUS reference count. Quartile boundaries are the 25th, 50th and 75th percentiles of reference count; ties stay together, so strata are unequal. Strata with fewer than 5 tested units are reported as not compared rather than pooled.

### Structure level

| Stratum | Reference range | n tested | n untested | Tested median (IQR) | Untested median (IQR) | Difference | p (greater) | Rank-biserial | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 fewest references | 1-1 | 1 | 740 | not compared | not compared | - | - | - | only 1 tested units; fewer than 5 |
| Q2 | 2-4 | 1 | 393 | not compared | not compared | - | - | - | only 1 tested units; fewer than 5 |
| Q3 | 5-23 | 1 | 514 | not compared | not compared | - | - | - | only 1 tested units; fewer than 5 |
| Q4 most references | 24-2493 | 21 | 527 | 117 (57-245) | 59 (30-111.5) | +58 | 0.0040 | +0.318 | |

Permuting tested labels only within strata (tested count per stratum held fixed): observed difference in medians +84.5, p (greater) = 0.0234, p (two-sided) = 0.0234.

### Connectivity level

| Stratum | Reference range | n tested | n untested | Tested median (IQR) | Untested median (IQR) | Difference | p (greater) | Rank-biserial | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q1 fewest references | 1-2 | 0 | 527 | not compared | not compared | - | - | - | only 0 tested units; fewer than 5 |
| Q2 | 3-7 | 1 | 291 | not compared | not compared | - | - | - | only 1 tested units; fewer than 5 |
| Q3 | 8-37 | 2 | 395 | not compared | not compared | - | - | - | only 2 tested units; fewer than 5 |
| Q4 most references | 38-2998 | 21 | 383 | 138 (76-273) | 83 (48.5-140) | +55 | 0.0103 | +0.274 | |

Permuting tested labels only within strata (tested count per stratum held fixed): observed difference in medians +130.5, p (greater) = 0.0013, p (two-sided) = 0.0013.

## Power

- Structure level: With 24 tested units against the rest of the corpus, the one-sided permutation test at alpha 0.05 rejects when the tested median exceeds the untested median by at least 6.5 genera. The smallest additive shift in the tested units' genera counts that reaches 80% power is 9 genera (simulated power 0.96 over 2000 draws), against an untested median of 3. Differences smaller than that are not detectable at this sample size, so a null result is not evidence of no difference.
- Connectivity level: With 24 tested units against the rest of the corpus, the one-sided permutation test at alpha 0.05 rejects when the tested median exceeds the untested median by at least 10 genera. The smallest additive shift in the tested units' genera counts that reaches 80% power is 12 genera (simulated power 0.81 over 2000 draws), against an untested median of 6. Differences smaller than that are not detectable at this sample size, so a null result is not evidence of no difference.

## Interpretation

The 24 tested structures occur in more LOTUS genera than the 2174 untested structures (median 87.5 vs 3, one-sided permutation p < 0.0001, rank-biserial +0.71; collapsing stereoisomers gives median 136.5 vs 6, p < 0.0001, rank-biserial +0.69). Most of that gap tracks how often a compound has been reported, since 21 of 24 tested structures fall in the most-referenced quartile; within that quartile a smaller difference remains (Q4 most references (21 tested vs 527 untested): median 117 vs 59, p 0.0040, rank-biserial +0.32), the within-stratum permutation gives p = 0.0234, and the other strata hold too few tested structures to compare (1 in Q1 fewest references, 1 in Q2, 1 in Q3), so the residual difference rests on one stratum and cannot be separated from residual differences in study intensity inside it.

## Inputs

- `occurrences`: data/interim/exploratory/occurrence_breadth_inputs/chemistry/occurrences.jsonl sha256 5b22d4cd15a6ce08f880bc079ec6ada48f53c4991155847f2bf851699c5cc400
- `labels`: data/interim/exploratory/occurrence_breadth_inputs/bioactivity/labels.jsonl sha256 95c7aac2c46bda48cbb112299aefe7c84f869fa567374ca6944234ce73c59b4d
- `lotus_export`: data/raw/chemistry_export/downloads/6893a0d2b680e5ecbe5b835c82d72aa4001c3ee0aa62e3d58932a03191cb8f31.body sha256 ffb310fffb395514e2fec5f42b682812d4f459c8783b884c67a737621ee2b5d2
- `chemistry_join`: input_hash 1dcd1d19cfbb269e4326c4a62979eed068fb4e1b03c69de8e611e1f37db806cb; unique_compounds 2198
- `lotus_rows_scanned`: 6467819 (0 malformed rows skipped)
- `input_note`: The chemistry join and labels were produced by the frozen chemistry and bioactivity stages replayed offline from the committed genus list; the input_hash above should equal the committed data/processed/chemistry/metrics.json.
- `seed`: 1729
- `permutations`: 10000

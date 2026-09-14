# Chemical-distance robustness

Predeclared in commit `e61139a5a431dd8d179c11634f722cae3c07e08e` before sensitivity draws. This exploratory analysis follows inspection of the original result.

Within-corpus separation is descriptively robust to the predeclared checks. The analysis does not establish the cause of uneven assay coverage.

The unrestricted gap was −0.0800 in the original corpus and −0.0840 after
removing small structures. After fingerprint collapse, joint size/genus matching
reduced the gap to −0.0382. Excluding every class linked to Arabidopsis left a
jointly matched gap of −0.0276. The adjustments attenuate the separation.

For the Arabidopsis-excluded, jointly matched comparison, observed similarity
was 0.2619 against a null median of 0.2895 and a central 95% range of 0.2647–0.3095.
The observation is only 0.0028 below that range's lower boundary; 30 of 2,000 draws
were at or below it. Joint matching forces 30 of 90 reference units in the collapsed
population and 7 of 41 after Arabidopsis exclusion. All cells have 2,000 distinct
sampled reference sets and nondegenerate statistic distributions.

## Population accounting

| Population | Units | Reference units | Source compounds | Collapsed compounds | Mixed measured/unmeasured classes |
| --- | ---: | ---: | ---: | ---: | ---: |
| original | 2198 | 98 | 2198 | 0 | 0 |
| size_filtered | 2176 | 97 | 2176 | 0 | 0 |
| fingerprint_collapsed | 1520 | 90 | 2176 | 656 | 38 |
| without_arabidopsis | 852 | 41 | 1144 | 292 | 12 |

## All sixteen controls

Difference is observed minus null median similarity. Negative values mean the retrieved reference leaves its complement further away than the median matched selection.

| Population | Match | Observed | Null median | Difference | Null 2.5–97.5% | Draws ≤ observed /2000 | Forced refs | Distinct sets |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |
| original | unrestricted | 0.3200 | 0.4000 | -0.0800 | 0.3770–0.4251 | 0 | 0 | 2000 |
| original | size | 0.3200 | 0.3977 | -0.0777 | 0.3722–0.4219 | 0 | 0 | 2000 |
| original | genus | 0.3200 | 0.3830 | -0.0630 | 0.3571–0.4091 | 0 | 18 | 2000 |
| original | joint | 0.3200 | 0.3750 | -0.0550 | 0.3516–0.4000 | 0 | 25 | 2000 |
| size_filtered | unrestricted | 0.3205 | 0.4045 | -0.0840 | 0.3810–0.4286 | 0 | 0 | 2000 |
| size_filtered | size | 0.3205 | 0.4000 | -0.0795 | 0.3750–0.4231 | 0 | 0 | 2000 |
| size_filtered | genus | 0.3205 | 0.3846 | -0.0641 | 0.3607–0.4118 | 0 | 18 | 2000 |
| size_filtered | joint | 0.3205 | 0.3761 | -0.0556 | 0.3542–0.4000 | 0 | 25 | 2000 |
| fingerprint_collapsed | unrestricted | 0.3134 | 0.3663 | -0.0528 | 0.3462–0.3846 | 0 | 0 | 2000 |
| fingerprint_collapsed | size | 0.3134 | 0.3632 | -0.0498 | 0.3438–0.3810 | 0 | 0 | 2000 |
| fingerprint_collapsed | genus | 0.3134 | 0.3548 | -0.0414 | 0.3333–0.3750 | 2 | 26 | 2000 |
| fingerprint_collapsed | joint | 0.3134 | 0.3516 | -0.0382 | 0.3333–0.3704 | 0 | 30 | 2000 |
| without_arabidopsis | unrestricted | 0.2619 | 0.3049 | -0.0430 | 0.2787–0.3306 | 3 | 0 | 2000 |
| without_arabidopsis | size | 0.2619 | 0.3010 | -0.0391 | 0.2768–0.3235 | 3 | 0 | 2000 |
| without_arabidopsis | genus | 0.2619 | 0.2881 | -0.0262 | 0.2642–0.3091 | 30 | 5 | 2000 |
| without_arabidopsis | joint | 0.2619 | 0.2895 | -0.0276 | 0.2647–0.3095 | 30 | 7 | 2000 |

## Interpretation limits

The rule requires negative differences and nondegenerate nulls in all sixteen cells, plus observed similarity below the 2.5th null percentile in the collapsed and Arabidopsis-excluded jointly matched populations. This is a descriptive sensitivity rule. The percentile ranges describe random selections; they are not confidence intervals for an effect. No new hypothesis-test p-values are computed.

Reference membership means an eligible assay measurement was retrieved. A compound outside the reference may have assay evidence absent from this retrieval. Size and genus matching conditions on observed corpus properties and cannot identify why coverage is uneven. Exact genus-membership strata retain multi-genus compounds without selecting an arbitrary genus. Forced reference units remain visible.

Fingerprint collapse treats identical bit vectors as equally weighted classes. A class is measured if any member is measured; every member is removed together from the query set. These classes can combine stereoisomers or fingerprint collisions. They do not change the source labels or establish molecular identity. The Arabidopsis exclusion removes every class linked to that genus and changes the population described.

All references come from this plant corpus. A larger external assay reference could change the absolute similarities and the observed-versus-null comparison. These results supply no activity prediction or biological enrichment estimate.

Every null statistic is saved under draws/, matching strata under cells/, and membership provenance under data/interim/chemical_distance_robustness. protocol.json and execution.json record hashes, versions, timestamps, and preservation checks.

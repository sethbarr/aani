# A first computational model: response-threshold constraints

Updated 12 September 2026. This pass extracts **conditional concentration ranges** from the existing growth experiments. It does not predict activity for an untested chemical. The [interactive explorer](constraint_browser.html) shows the underlying observations, source PDFs and changes under alternative assumptions. [Download the constraints](threshold_constraints.csv), [within-study comparisons](within_study_orderings.csv), or [sensitivity changes](sensitivity_changes.csv).

## What the model means

Define **C50** as the concentration at which inhibition first reaches 50% of the corresponding control growth in one particular assay. Assume a continuous, nondecreasing concentration-response function, beginning below 50% inhibition. Then:

* A response definitely below 50% at concentration d implies C50 > d, or that 50% inhibition is never reached.
* A response definitely at or above 50% at d implies C50 ≤ d.
* Combining those statements can bracket C50 without fitting a response-curve shape.

**These intervals are mathematical consequences of assumptions about the reported values. They are not new measurements, confidence intervals, or independently validated potency estimates.** The source concentrations, media, times and cultivar provenance remain part of each result. Monotonicity has not been demonstrated for most materials. Solubility, instability, non-monotone biology or unreliable measurements could invalidate it.

Three scenarios are provided: literal reported values, and buffers of ±10 or ±20 percentage points around them, clipped to 0–100%. For a reported bound such as >80%, the compatible response range is conservatively widened; it is not replaced by an exact 80%. Buffers are analyst-selected stress tests, **not experimentally estimated measurement error**. The 20-point scenario is displayed first to make weakly constrained results apparent. Both the scenarios and the threshold were chosen during exploratory review, not preregistered.

The model keeps a source's final or tabulated mass-per-volume basis. Only the arithmetic conversion 1 mg/mL = 1000 µg/mL is used. It performs no mass-to-molar, vapor-to-contact, or cross-protocol conversion. Unreported protocol details remain uncertain. A predicted concentration range from one paper cannot be ranked against another paper's range as if both used the same assay.

## Results

Of 71 molecular/reference records, **47 growth observations from six papers** can enter this calculation. They represent **39 material–study response groups: 38 natural-product groups and one reference chemical**. Thirty-one groups have only one tested concentration; eight have two. The other 24 records are listed with reasons in the [exclusion table](excluded_records.csv): fitted endpoints, damage incidence, recovery, qualitative nulls and ambiguous prose are not interchangeable with dose-specific percent growth inhibition.

| Scenario | Two-sided range | Lower bound only | Upper bound only | No bound |
|---|---:|---:|---:|---:|
| Literal reported responses | 5 | 18 | 16 | 0 |
| ±10 percentage points | 2 | 18 | 15 | 4 |
| ±20 percentage points | 2 | 18 | 13 | 6 |

Eleven groups change between the literal and 20-point scenarios. In particular, a visual score of exactly 50% becomes uninformative about which side of the threshold the true response lies on. Even in the literal scenario, a single 50% observation supplies an upper bound; it does not establish an exact C50.

Two brackets survive the 20-point scenario:

| Material and source | Observations used | Conditional C50 range |
|---|---|---|
| Caryophyllene oxide, Howard1988 | 25% inhibition at 10 µg/mL; 100% at 100 µg/mL | **10 < C50 ≤ 100 µg/mL** |
| Kokusaginine, Biavatti2002 | 20% inhibition at 50 µg/mL; 100% at 100 µg/mL | **50 < C50 ≤ 100 µg/mL** |

Originals: [Howard Table 1, PDF 7 / printed 65](../../sources/howard1988terpenoids.pdf#page=7); [Biavatti Table 1, PDF 3 / printed 68](../../sources/raulinoa2002.pdf#page=3). Different protocols prevent comparing these two ranges as a potency ranking. The Howard outcome uses an ordinal visual scale; Biavatti refers to an earlier assay protocol without restating all details.

The same-paper coumarin comparison remains informative under the 20-point buffer: **xanthyletin gives C50 ≤25 µg/mL**, whereas **clausarin gives C50 >75 µg/mL or never reaches 50%**. That supports testing the two materials side by side with confirmed exposure. It does not establish statistical superiority or a structural mechanism. [Godoy2005, Table 1, PDF 3 / printed 671](../../sources/coumarins2005.pdf#page=3).

There are 45 ordered material pairs in the literal scenario and 34 under the 20-point buffer, calculated only where one material's upper bound is at or below another's strict lower bound in the same study, readout, route and time. These are not 45 or 34 independent discoveries: pairs reuse the same observations. Reference chemicals are excluded from those pair counts. No cross-study ordering is calculated.

## Consequences for the next measurements

**Kokusaginine:** observations between the two existing concentrations would be particularly informative for narrowing its conditional bracket, after reproducing the reported endpoint and confirming delivery. **Caryophyllene oxide:** the current bracket spans an order of magnitude; intermediate observations and independent cultivar isolates would address different uncertainties. **Xanthyletin/clausarin:** a common concentration-response experiment would test the same-study contrast and whether the inactive result reflected delivery. These are experimental design implications, not a ready-to-run laboratory protocol.

For computational work without new experiments, the next source-recovery opportunity is the actual plotted concentration-response data and any author-supplied raw data. Reading a plotted mean adds information, but does not reconstruct independent observations or missing error bars. The dillapiol and Melo figures are candidates for carefully documented digitization; they remain outside this percent-growth constraint calculation until transcribed with their own dose and endpoint definitions.

## High-priority identity audit

Re-reading the original methods did not provide enough information to assign the four flagged panel materials to exact stereochemical assay identities:

| Material | What the original establishes | What remains needed |
|---|---|---|
| Argentilactone | NMR/MS identification, a drawn structure and comparison with earlier literature | Absolute stereochemistry of the tested isolate; the paper does not report an optical rotation or an explicit R/S assignment in the inspected characterization. [PDF 3–4](../../sources/napal2015.pdf#page=3) |
| Caryophyllene oxide | Isolation and comparison with an authentic sample in 1983 | Traceable stereochemical identity of the authentic/test material; a present-day database name hit does not identify the historical batch. [PDF 3](../../sources/hubbell1983.pdf#page=3) |
| Kolavenol | Named chemical, structural scheme and historical plant links; materials chosen for availability | Exact assay-batch origin and stereochemical correspondence. [Howard PDF 3](../../sources/howard1988terpenoids.pdf#page=3) |
| Citral | Purchased from Sigma-Aldrich | Product/lot and isomer composition; neither is established by the cited supplier name alone. [Melo PDF 2](../../sources/melo2020.pdf#page=2) |

The current source-code and candidate-structure flags therefore remain. This is a missing-material-specification problem, not a request for another copy of those full texts. No new full text is required to inspect the calculations delivered here.

## Reproducibility and interpretation

Run `python3 test_constraints.py`, then `python3 build_constraints.py` and `python3 render_constraints.py` from this directory. The input is the unchanged molecular assay table in the parent folder. [Summary and input hash](summary.json), [record-level scenario ranges](response_scenarios.csv) and [validation checks](validation_checks.json) support replay and inspection. This is an exploratory derivative; the frozen genus-level primary analysis remains unchanged.

Defining the endpoint, assumptions and scope before treating outputs as predictions follows the methodological concerns described in the [OECD QSAR validation principles](https://www.oecd.org/content/dam/oecd/en/topics/policy-sub-issues/assessment-of-chemicals/oecd-principles-for-the-validation-for-regulatory-purposes-of-quantitative-structure-activity-relationship-models.pdf). This calculation is a transparent feasibility tool, not a validated QSAR or regulatory assessment.

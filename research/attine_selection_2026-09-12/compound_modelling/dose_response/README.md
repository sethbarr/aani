# Published dose-response recovery and source audit

12 September 2026. This computational pass recovers plotted responses, tests descriptive curve fits, transcribes the behavioral portion of Howard's 50-plant supplement, and records four chemical connectivity graphs from original figures. Open the [interactive explorer](dose_response_browser.html).

## What was completed

| Output | Scope |
|---|---|
| [Digitized responses](digitized_points.csv) | 36 visible markers from Melo2020, Figure 2a-b; eight material/exposure series |
| [Descriptive fits](descriptive_fits.csv) | Probit and logistic fits to each series, with fixed 0/100% asymptotes; 16 fits of eight datasets |
| [Salazar dose envelopes](salazar_visible_envelopes.csv) | 14 dose groups across extract and dillapiole; no invented means or replicate counts |
| [Howard plant table](howard50_plants.csv) / [monthly values](howard_monthly_harvest.csv) | 50 plants; 148 plant-month harvest means and SDs; nonpolar-extract deterrence classes |
| [Chemical graphs](source_structure_graphs.csv) | One achiral coumarin and three lignan connectivity graphs, linked to source codes |
| [New Portuguese original](https://doi.org/10.1590/1809-43921988185442) | Fernandes et al. 1988, the isolation paper cited by Pagnocca1996 |

These are supplementary outputs. The original 149-record extraction, later 71-record molecular table, and frozen primary project analysis are unchanged. Digitized points are not new experiments and must not be counted alongside their published IC50 as independent observations.

## Curve results and their limits

The unweighted Probit reconstructions give the following approximate midpoints. All concentrations retain the source's administered-volume basis; neither exposure route measures the concentration actually reaching fungal cells.

| Material | Route | Published IC50 | Descriptive Probit C50 | Unit |
|---|---|---:|---:|---|
| M. lundiana oil, isopulegol chemotype | Fumigation | 145.1 | 142 | µL treatment/L air |
| Isopulegol | Fumigation | 150.1 | 154 | µL treatment/L air |
| M. lundiana oil, citral chemotype | Fumigation | 104.8 | 105 | µL treatment/L air |
| Citral | Fumigation | 31.7 | 32 | µL treatment/L air |
| M. lundiana oil, isopulegol chemotype | Contact | 238.1 | 241 | µL treatment/L medium |
| Isopulegol | Contact | 696.8 | 695 | µL treatment/L medium |
| M. lundiana oil, citral chemotype | Contact | 217.9 | 217 | µL treatment/L medium |
| Citral | Contact | 289.9 | 286 | µL treatment/L medium |

Original: [Melo2020, PDF 8 / printed 17310, Figure 2](https://doi.org/10.1007/s11356-020-08170-z#page=8), [publisher](https://doi.org/10.1007/s11356-020-08170-z). The eight series are two oils and two purchased materials, each in two exposure routes, not eight independent chemicals. The original source reports four replications, but does not identify the aggregation behind each plotted marker in the caption. Replicate-level values and run/isolate nesting were not recovered. The two oils are mixtures; exact isopulegol stereochemistry and citral composition remain unresolved.

Across both curve forms, reconstructed midpoints differ from the printed estimates by at most 3.2%. This is a consistency check on figure recovery, not external validation or improved precision. Agreement between two fixed-asymptote curves does not establish those asymptotes biologically. Curves are displayed only across each series' observed concentration range.

The exploratory models are `fraction = Φ(slope × [log10(dose) − log10(C50)])` and the analogous logistic function. Two parameters are fitted by unweighted nonlinear least squares using [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html). This is not the original authors' Probit likelihood/weighting. No binomial sample size is assigned to a continuous growth fraction. Printed slopes and confidence limits are retained separately in [metadata](series_metadata.csv).

**Sensitivity is separated from biological uncertainty.** Each fit is repeated on 200 coordinate perturbations: each marker independently moves within ±3 native image pixels (±5 for two overlapping markers); axis coordinates independently move within ±1 pixel. Uniform draws are a computational stress test, not a measured error distribution. The minimum and maximum from those draws are not exhaustive bounds and are not confidence intervals. [All perturbations](pixel_sensitivity_draws.csv) are saved. These perturbations cover coordinate reading, not incorrect material assignment, an unrecognized hidden marker, or source measurement error.

Each fit also omits one visible marker in turn. In four of eight series, removing one marker leaves responses entirely on one side of 50%, so the corresponding refit is withheld. Other omission estimates show how a few observations affect the result. These are sensitivity checks, not independent holdout validation. See [omission results](omission_sensitivity.csv).

**Practical finding:** the within-route evidence for citral versus isopulegol can be reproduced from the figure. This supports retaining both as an informative contrast. Comparing air-volume and medium-volume IC50s as a fold change in intrinsic potency would be inappropriate. The study's mixture synergism results concern ant mortality and do not establish antifungal synergy.

## Why dillapiole was not refitted

[Salazar2020, PDF 5 / printed 672, Figure 3](https://doi.org/10.1007/s10886-020-01170-w#page=5) contains overlapping open circles, particularly at complete inhibition. Methods specify five repetitions, but the image does not reveal every repetition or its multiplicity. Fitting each visible circle once would give hidden or coincident observations too little weight. Reconstructing five repeats from the picture would invent data.

The saved envelopes are rounded visible vertical extents at each dose, not estimated means, quartiles, confidence intervals or the full replicate range. They retain useful checks: dillapiole is below 50% at 25 ppm and above it at 50 ppm, consistent with the source's fitted IC50 of 38 ppm. The extract crosses between 100 and 250 ppm, consistent with the published 102 ppm. The source's three-parameter asymptotic exponential model and IC95s are not regenerated from these envelopes. Author-supplied per-plate responses or unambiguous per-dose summaries would permit a better refit. Another copy of the same PDF is not needed.

## Chemical identity progress

The four [rendered structures](source_structure_graphs.png) were transcribed from [Godoy Figure 1](https://doi.org/10.1590/S0103-50532005000400031#page=3) and [Pagnocca Figure 1](https://repositorio.unesp.br/entities/publication/44608eaa-b84f-4614-8e00-6f6fb9c5caf1#page=3), parsed and rendered with RDKit, then visually compared with the originals. This establishes a usable, explicit connectivity representation without choosing a compound solely by a name-database hit.

* **C043 / coumarin 8:** the figure and name support 7-hydroxy-3-(1,1-dimethylallyl)-8-methoxycoumarin, an achiral graph with calculated formula C15H16O4.
* **C010 / lignan 5:** a dibenzylbutyrolactone with one veratryl and one piperonyl substituent. The carbonyl-adjacent benzyl group is piperonyl in the assay figure.
* **C011 / lignan 6:** the analogous dibenzylbutyrolactone with two veratryl substituents.
* **C013 / lignan 8:** an open-chain dibenzylbutane diol with two piperonyl substituents.

The three lignan SMILES deliberately leave two stereocenters unassigned. Their connectivity InChIKeys are not identifiers for an exact stereochemical assay material. All four graphs remain in a supplementary audit instead of silently changing the registry's identity status. No molecular descriptor was treated as an activity measurement.

The newly recovered [Fernandes1988 original](https://doi.org/10.1590/1809-43921988185442), [DOI](https://doi.org/10.1590/1809-43921988185442), provides the earlier Virola leaf-isolation route and reports (2R,3R) assignments. However, its abstract and Scheme 1 disagree over numbering of the mixed versus doubly piperonyl lactones. Its drawings also require positional comparison, not a match by substituent names alone. This prevents an automatic source-code/stereochemical crosswalk to the 1996 assay. Historical batch identity is still unverified. The full text was obtained openly; no library help was needed for this paper.

## Howard's plant-selection comparison

The supplement's harvest and nonpolar-extract columns are now transcribed for all 50 plants. Nineteen have source class 3 (highly deterrent), eleven class 2, twelve class 1 (not statistically significant), and eight class 0. The monthly harvest values are means and SDs across three ant colonies. Jacquinia pungens has June only because leaves were present only in that month; missing months were not entered as zeroes.

This separates a plant being poorly harvested from evidence that its nonpolar extract deterred ants. It does **not** establish fungal toxicity. The source's alkaloid/tannin, nutrient, water and biomass columns are not yet fully transcribed. Taxonomic spellings are retained as printed; no modern synonym reconciliation was performed. Two partially obscured rendered rows were cross-read with the PDF text layer and flagged. Original: [Howard1987 supplement, definitions PDF 2 and table PDF 3–9](https://doi.org/10.2307/1938455#page=2).

## Remaining work and where your help would matter

No user action is needed for the calculations delivered here. A collaborator or the original authors could later provide dose-level replicate data, exact reagent specifications and fungal isolate identities. No messages were sent.

The earlier Morais2015 journal request remains open, specifically for the stock-versus-final-dose discrepancy. The 2012 thesis is already saved. Focused searches confirmed citations for Vitório1996 and Garcia1997 but did not recover the original theses in this pass. Forti1985 remains unresolved. The 1,834-record discovery pool has not been exhaustively screened; this pass closes one specific table gap rather than claiming completion of the entire search.

The next useful computational extension is a broader original-source assay extraction, especially from already-saved theses, with identity curation and explicit negatives. The current fits do not justify a general predictor for untested chemicals or a garden-level efficacy estimate.

## Reproduce and inspect

Run `digitize_figures.py`, `fit_curves.py`, `extend_source_audit.py`, `test_analysis.py`, and `render_browser.py` in that order in an environment with the saved [requirements](requirements.txt). [Calibration](calibration.json) includes source/image hashes and coordinate transforms. [Digitization overlay](digitization_audit.png), [standalone chart](dose_response_fits.svg), and [validation checks](validation_checks.json) support review. Tests check known synthetic curves, unit scaling, calibration, data scope and missing-value handling; they do not validate biological predictions.

# Compound evidence and modelling readiness

Updated 12 September 2026. **The next useful step is a standardized validation panel. The current collection does not support a validated general structure–potency predictor.** This conclusion is about this extracted dataset, not the entire available literature.

Open the [compound browser](compound_browser.html) for the proposed panel, compound identities, original assay values and source PDFs. The [panel table](validation_panel.csv) gives the question each material would answer. The [registry](compound_registry.csv), [molecular assay table](molecular_assay_evidence.csv) and [comparison blocks](comparison_blocks.csv) support independent review.

**Computational extension:** the [response-constraint explorer](response_constraints/constraint_browser.html) derives conditional 50%-inhibition concentration ranges from 47 growth observations. Its [methods and results](response_constraints/README.md) show the effects of monotonicity and response-buffer assumptions; these ranges are not measured IC50s or confidence intervals.

## What is actually available

| Coverage | Result |
|---|---:|
| Original extracted records, including extracts and controls | 149 |
| Additional records transcribed from three already-saved primary papers | 20 |
| Molecular-material and reference records in the expanded scope | 71 |
| Natural-product material concepts | 49 |
| Additional reference chemicals | 2 |
| Papers contributing molecular records | 11 |
| Conservative source blocks, grouping the potentially overlapping 1983/1988 cultures | 10 |
| Materials appearing in more than one paper in this extraction | 1: caryophyllene oxide |
| Largest same-paper, same-dose, same-endpoint comparison | 5 materials |

The 49 concepts include three source-coded lignans and citral with unspecified isomer composition. They are **not 49 fully resolved molecular structures**. PubChem returned candidate records for 45 of the 51 concepts including references. Twenty-three achiral identities were accepted from the source name/structure and database connectivity; 21 of these are natural-product concepts. The remaining 28 entries retain explicit identity review flags. Full InChIKeys and SMILES are assigned only to accepted identities; candidate structures have separate columns.

The additions preserve the original 149-row dataset and use IDs M001–M020: eight coumarins plus piperonyl butoxide from [Godoy2005, PDF 2–3](../sources/coumarins2005.pdf#page=2); nine numeric quinoline observations from [Biavatti2002, PDF 2–3](../sources/raulinoa2002.pdf#page=2); and argentilactone plus the fungicide reference MIC from [Diaz Napal2015, PDF 3–4](../sources/napal2015.pdf#page=3). Paper dashes and “not tested” cells are not converted into zero inhibition. This is a targeted extension, not complete extraction of the remaining bibliography.

## Why a general potency model would be premature

**Very few concentration endpoints are comparable.** The natural-product MIC set has one material: argentilactone. Five uncensored IC50 records describe only three materials: dillapiol, isopulegol and citral. The latter two are each tested by vapor and contact exposure. Dillapiol is reported in ppm, while the other two use volume per air or medium volume. The IC95 is a second estimate from the same dillapiol curve, not another experiment. Five other materials have censored IC50 bounds in both exposure routes, useful within the Melo study but not ten independent chemical negatives. See the [source-level extraction](molecular_assay_evidence.csv).

**Most observations are sparse growth screens.** The molecular table has 37 coarse visual growth records, eight ordinal growth records and two radial inhibition records. These include unequal doses, different observation times and incompletely restated methods. Percent values from visual scales are not precise continuous measurements. Complete inhibition at a single tested concentration is not an experimentally determined MIC. The largest matched block contains five compounds, in Pagnocca1996 or Biavatti2002, with different protocols between those papers.

**Paper and chemistry are confounded.** Many chemical families occur predominantly in one paper. A model could learn the laboratory or endpoint rather than transferable chemistry. Source blocks are bookkeeping groups; the publications do not establish ten molecularly distinct, independent cultivar isolates. The table groups the Hubbell/Howard pair conservatively and retains other strain-dependence uncertainty. A random split of rows would put repeated doses and closely related observations on both sides of evaluation.

There is enough evidence to prioritize experiments and describe within-study contrasts. There is not enough comparable replication to claim a reliable cross-study potency prediction or a validated estimate of model accuracy. No predictive model or pooled active/inactive threshold was fitted.

## Proposed ten-material panel

The panel contains eight leads and two reported inactive comparisons. Its order is for review and assay planning, **not a potency ranking**. It is a diversity-oriented starting set, not an optimized selection from fully known chemistry.

| Material | Original signal | Purpose |
|---|---|---|
| Dillapiol | IC50 38 ppm | Leaf-derived chemical linked to the non-foraging observation |
| Argentilactone | MIC 0.90 µg/mL | Strong fungal result plus rejection of compound-treated leaves |
| Xanthyletin | 100% inhibition at 25 µg/mL | Defined coumarin reference |
| Caryophyllene oxide | Ordinal growth inhibition and culture damage in two papers | Connect growth, damage and ecological evidence |
| Kokusaginine | 20% at 50; 100% at 100 µg/mL | Resolve a steep apparent concentration response |
| Syringaldehyde | 80% at 50 µg/mL | Phenolic aldehyde lead |
| Vanillic acid | 80% at 50 µg/mL | Phenolic acid lead with explicit medium-pH assessment |
| Citral, composition to be characterized | Vapor/contact IC50 and a recovery observation | Separate delivery and reversible inhibition from persistent effects |
| Clausarin | No inhibition at 75 µg/mL | Same-paper coumarin comparison |
| Kolavenol | No inhibition at 11 or 110 µg/mL | Ant deterrence without corresponding fungal inhibition |

Every row, exact page locator, identity caveat and proposed validation question is in the [source-linked panel table](validation_panel.csv) and browser. These compounds span different plant organs: roots or stems cannot explain leaf avoidance without additional occurrence and exposure evidence. The purchased compounds in Melo2020 are not assigned to a leaf batch just because they were tested alongside an oil.

For a volatile null comparator, the existing Melo data also support retaining **p-cymene**. The original assay references **piperonyl butoxide** and **carbendazim** are available separately; choice of a positive assay control should be validated in the intended cultivar and protocol. Commercial availability, cost and procurement have not been assessed.

## How to model activity as useful data accumulate

1. **Model the assay response first.** Measure concentration-response curves for characterized materials in a shared contact assay, using independent cultivar isolates and preserving plate/run/colony nesting. Fit inhibition versus concentration for each material and isolate, with intervals and explicit upper/lower bounds. A Hill-type curve is a candidate where the observed response is monotone; its form must be checked. Report an EC50 only when the response range supports estimating it. MIC and recovery endpoints remain separate.
2. **Keep exposure explicit.** Record the administered concentration, dissolved or otherwise available fraction where measurable, medium, pH, solvent, duration and material identity. Vapor studies use their own exposure model and controls. Pure compounds, defined mixtures and crude extracts require different representations. Do not infer synergy from a mixture merely outperforming one component.
3. **Then test a small chemistry model.** Begin with a low-complexity descriptor baseline and an intercept-only benchmark when enough independent, comparable compounds exist. Compare predictions with held-out compounds and, separately, held-out chemical families and studies. Do not let doses, papers reporting the same experiment, stereoisomers or repeated source material leak across evaluation groups. The present panel is for validation and contrast; it is not by itself a training set large enough for a general model.
4. **Validate the garden link.** After reproducible isolated-cultivar activity, test whether the compound reaches the garden and affects cultivar growth or function at that exposure. Record ant behavior, ant toxicity, substrate processing and nutritional effects separately. Whole-garden loss does not by itself identify direct antifungal action.

These are proposed exploratory modelling steps. The existing frozen genus-level behavior/enrichment analysis in the parent project remains unchanged, including its human-pathogen endpoints. It asks a different question.

## Identity problems preserved for review

* The `Episesamin` name query returned PubChem CIDs 72307, 101612 and 5204, including a sesamin record. No candidate was selected; sesamin and episesamin assay outcomes remain separate.
* The `citral` query returned CID 638011 with an E-isomer representation. That record does not establish the composition of the tested commercial material. The compound row therefore has no exact assigned structure.
* Philygenol, epigalgravin and the long-named coumarin 8 did not resolve through the attempted names. Three additional lignans remain source codes. Their original figures and outcomes are preserved for manual structure transcription.
* Stereochemistry, geometry and tested-batch identity remain unverified for the other flagged candidates. A PubChem hit alone is not verification of an assay material. The [identity review queue](identity_review_queue.csv) records each unresolved item.

Structure properties were retrieved through [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest), preserving raw results, query URLs and retrieval times in [the retrieval log](pubchem_retrieval_log.json). Candidate XLogP and related descriptors are database properties, not measured antifungal activities. No mass-to-molar conversions were performed. The Morais concentration ambiguity remains outside molecular potency modelling and does not block this panel.

## Reproduce and validate

`fetch_pubchem.py` performs the public identity lookups and caches successful or failed responses. `build_compound_evidence.py` rebuilds the registry, supplemental assays, annotations and coverage audit offline. `render_compound_browser.py` builds the panel CSV and browser from those files. Original PDFs and raw database responses remain the validation sources. [Input hashes](input_hashes.json), [coverage counts](feasibility_counts.json) and [validation checks](validation_checks.json) make the scope inspectable.

**Published curve recovery:** [Dose-response explorer](dose_response/dose_response_browser.html) and [methods](dose_response/README.md) now provide descriptive fits to Melo’s plotted responses, Salazar response envelopes, four source-derived chemical graphs and the Howard plant-selection transcription. These are supplementary outputs; the registry and assay input remain unchanged.

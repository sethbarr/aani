# Five supplied originals: validated findings and modelling implications

First-batch report,12 September 2026. **A [second update](FULL_TEXT_VALIDATION_BATCH2.md) now brings the collection to 33 PDFs and 149 combined assay records; Morais2015 alone remains pending, with its thesis available.**

At this first update, All five supplied PDFs have been copied into this collection and their relevant fungal methods and results checked. The collection now contains **25 PDFs**. Original files in Downloads were preserved. File hashes and original filenames are recorded in [user_supplied_fulltexts.json](user_supplied_fulltexts.json).

The new [assay CSV](compound_assays_batch1.csv) / [JSON](compound_assays_batch1.json) contains **40 records from five papers**: 22 pure-compound records and 18 extract, oil or fraction records. These are treatment results or fitted endpoints, **not 40 independent compounds or experiments**. Methods, controls and donor-colony limitations are in [assay_contexts_from_fulltexts.json](assay_contexts_from_fulltexts.json). The [evidence browser](evidence_browser.html) now includes a compound/extract assay view.

## What the full texts establish

| Original | Validated fungal result | Consequence for plant/compound selection |
|---|---|---|
| **Salazar 2020 — Piper holtonii** | Ethanolic leaf extract IC50/IC95 **102/369 ppm**; isolated **dillapiole 38/122 ppm**. Essential oil completely inhibited growth at 1000 ppm. Five-week acid-PDA assay, five repetitions/treatment. | Strong molecule-to-leaf link. Dillapiole was distinguished from apiole by NMR. Keep fitted concentrations separate from observed growth and oil-mixture results. [PDF, pp.2–5](sources/salazar2020.pdf#page=2), [DOI](https://doi.org/10.1007/s10886-020-01170-w). |
| **Howard 1988 — terpenoids** | At day 7, **caryophyllene epoxide 0.10 mg/mL** and **nerolidol 0.14 mg/mL** scored no growth. At tenfold lower doses, remaining growth was75% and 50%, respectively. Caryophyllene gave 50%/75% remaining growth at 0.14/0.014 mg/mL. **Kolavenol gave no inhibition at 0.11 or0.011 mg/mL.** | Preserve dose and ordinal score. Kolavenol is a useful ant-deterrent/fungal-null comparison. The paper links epoxide to Hymenaea/Melampodium/Vismia and nerolidol to Vismia through earlier isolation work; this is not proof that every assay used material freshly isolated from those plants. [Table 1, PDF 7](sources/howard1988terpenoids.pdf#page=7), [DOI](https://doi.org/10.1007/BF01022531). |
| **Pagnocca 1996 — lignans** | **Sesamin 70 µg/mL** and **epigalgravin 200 µg/mL** left **<20% growth** in Table 1. Episesamin and lignan 8 each left 100% growth at 200 µg/mL. Eudesmin, philygenol, lignan 5 and lignan 6 left 60%,80%,80%,40% growth at their respective tested concentrations. | Sesamin/episesamin provides a stereochemical contrast, although the doses differ. **Otoba parvifolia supplied philygenol from fruit: only 20% inhibition**, so that plant is downgraded to tentative. Epigalgravin came from unidentified **Virola sp.**, not established V. sebifera. [PDF 2–4, Fig 1/Table 1](sources/pagnocca1996.pdf#page=2), [DOI](https://doi.org/10.1007/BF02266969). |
| **Hubbell 1983 — Hymenaea courbaril** | Caryophyllene epoxide caused shrivelling, collapse and browning within 48 h in **8/10 cultures at 100 µg/mL**,10/10 at 3 mg/mL and 5/5 at 30 mg/mL; all 10 untreated controls stayed healthy. | The8/10 result is **culture-damage incidence**, not 80% growth inhibition. A recovery attempt failed, but the authors still leave killing versus reversible inhibition unresolved. Natural leaf concentration and a repellency experiment support ecological relevance; actual garden exposure remains unmeasured. [Methods PDF 3; results PDF 5](sources/hubbell1983.pdf#page=5), [DOI](https://doi.org/10.1007/BF00376846). |
| **Bigi 2004 — Ricinus communis** | Hexane/methanol extracts left 20% growth at 5 mg/mL. Active subfractions left 20% growth at 0.5–1 mg/mL. MFHE-9 contained fatty acids plus glycosylsteroids. | These are mixture results. **No individual fatty acid was established as responsible**; palmitic acid’s81% in the reported profile is not an activity measurement. Ricinine was ant-active; its fungal statement at 1 mg/mL is defective prose, discussed below. [PDF 2–4, Tables 1–3](sources/bigi2004.pdf#page=2), [DOI](https://doi.org/10.1002/ps.892). |

The exact dose-by-compound entries, including null and weak results, are in the CSV. Plant-level priorities still reflect usefulness for validation, not a potency comparison across different assays.

## Source problems preserved in the data

**Remaining growth versus inhibition.** Pagnocca and Bigi label their tables with remaining growth. A20% entry therefore corresponds to 80% inhibition, not20%. The extraction retains the reported endpoint and a separately labelled arithmetic transformation. These are coarse visual scores, not precise continuous measurements with known standard errors.

**The lignan text/table conflict.** Pagnocca’s prose calls sesamin and epigalgravin completely inhibitory, whereas Table 1 reports **<20% remaining growth**. The records preserve the bound, equivalent to **>80% inhibition**, and flag the contradiction. They are not converted to 100% inhibition or MIC values. Figure 1 depicts the compounds; lignans 5,6 and 8 retain source-local codes instead of guessed chemical names. Sesamin’s absolute stereochemical identity must be curated before merging it with later (+)-sesamin assays.

**The ricinine sentence.** Bigi PDF 3 literally says “Pure ricinine have any effect” at 1 mg/mL. The abstract and surrounding discussion distinguish fatty-acid fungal effects from ricinine ant effects, supporting a null interpretation, but no quantitative ricinine fungal result is tabulated. Its row is therefore **qualitative and held out from numeric or binary training** until that wording is resolved. It is not encoded as exactly 0% inhibition.

**Compounds identified but not tested.** Bigi explicitly says that the two glycosylsteroids, isofraxidine, scopoletin, a monoglyceride ketal and a monoglyceride were not individually tested because insufficient material was obtained. They are not added as positive or negative antifungal assays. The separate [fatty-acid composition table](bigi2004_fraction_composition.csv) contains chemistry observations, with causal activity explicitly unestablished. Its printed percentages total 98.2%; they were not renormalized. Table 3 names MFHE, whereas the nearby prose discusses MFHE-9; that fraction-level ambiguity is retained.

**Historical taxonomy and provenance.** Vismia appears as “Vismea baccifera” in Howard’s text. The unspecified Virola species remains unresolved. The older attine cultures lack modern molecular strain identification. Each paper remains grouped as a study; the 1983/1988 cultures should not be assumed independent lineages merely because they appear in separate papers.

## How these data should enter an activity model

My recommendation is to build an **assay-aware evidence model first**. These five papers alone contain too few independent chemical structures and too many different endpoints to establish a reliable general structure-to-potency model.

| Measurement | Suitable representation | What it must not become |
|---|---|---|
| Fitted IC50/IC95 | Separate concentration endpoints, retaining fungus, assay, units and fit uncertainty; IC50 and IC95 share a curve | Two independent observed treatment replicates, or MIC |
| Howard growth scores | Ordered categories conditioned on concentration and time | Precise continuous values with invented error bars |
| Pagnocca/Bigi visual growth | Coarse response, preserving bounds such as<20%; mixtures in a separate model | Exact IC50 estimates from a single dose |
| Hubbell damaged cultures | Counts with denominators, e.g.8/10; a binomial observation model is a reasonable starting assumption |80% inhibition of biomass or radial growth |
| Ant deterrence, mortality or plant non-selection | Separate explanatory evidence about choice or organism affected | Automatic fungal activity labels |

For a later molecular model, first curate structures, stereochemistry, units and negative assays across the wider collection. Predict a specified fungal response at a specified dose, or fit a separate comparable-potency model where enough concentration endpoints exist. Group repeated doses, fractions from one extraction, thesis–article overlaps and all labels from one compound when assessing performance. Then assess transfer to held-out studies and chemical families; ordinary row-level splitting would make the apparent sample size misleading.

Avoidance can be tested as an additional discovery signal. It should not determine the fungal outcome label. Kolavenol and episesamin provide useful null results; accepted-but-antifungal plants in the 89-plant screen provide the converse comparison. No model was trained and no records were inserted into the project’s frozen primary analysis tables.

## Remaining full texts

The five highest-priority requests are resolved. **Seven articles remained at this stage; see the [current request queue](FULL_TEXT_REQUESTS.md)**, led by the TRAMIL preparations paper, the papaya carpaine/squalene paper, and the Pilocarpus grandiflorus compound paper. Related theses already held are identified there. The broader search still has unresolved grey literature and unscreened discovery records, so this update does not establish exhaustive coverage.

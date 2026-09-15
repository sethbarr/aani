# Second full-text update: six requested papers, one review, and the Morais thesis

Updated 12 September 2026. All seven supplied files were identified and saved. **EBSCO-FullText-09_12_2026.pdf is the papaya paper; Unknown Title - Unknown Title.pdf is the 1990 sesame paper.** Araújo2022 is the review already used for discovery, now also available as a local PDF. The six requested primary papers have been checked against their fungal methods and results.

I also retrieved Morais’s original Portuguese master’s dissertation from UFV. The collection now holds **33 PDFs, 98 plant records, 157 bibliography records, and 149 assay/endpoint/control records**. The [109 new records](compound_assays_batch2.csv) extend the [first 40](compound_assays_batch1.csv); the [combined CSV](compound_assays_from_fulltexts.csv) and [evidence browser](evidence_browser.html) contain both batches. Counts include repeated doses, fitted endpoints, controls and qualitative observations; they are not independent experiments or unique compounds.

## The article you could not find

The [UFV article record](https://locus.ufv.br/items/c5c19be4-5ecf-44d1-ad24-1509cf280d52/full) lists an `artigo.pdf`, but its download route led to a repository login page. The 2015 journal full text remains unavailable in this collection.

The author’s **2012 master’s dissertation, Extratos botânicos e seus efeitos em Atta sexdens rubropilosa**, was downloadable: [institutional PDF](https://locus.ufv.br/server/api/core/bitstreams/da53d5c4-077b-4210-8036-f6bda05b963c/content), [saved copy](sources/morais2012thesis.pdf). Chapter 2 contains the same inhibition percentages as the article abstract; treat them as overlapping work.

**Dose ambiguity:** methods, PDF 44–45, describe 25/50/100 mg/mL DCM stocks, then 1 mL added to 9 mL medium. This implies nominal final 2.5/5/10 mg/mL, whereas Table 1, PDF 48, retains 25/50/100 labels. Both interpretations remain visible; neither is silently selected. Coriander’s 23%/27% reductions are not significant against solvent control. Ten plates contained three discs each; those discs are not 30 independent plates. The publisher version or author clarification would still be useful to resolve the concentration basis.

## What the supplied originals add

| Source | Findings useful for choosing chemical leads | Source location |
|---|---|---|
| **Boulogne2012: TRAMIL preparations** | Verified all five IC50 estimates and their confidence intervals. Senna alata has IC50 **251.51 µg/mL** and showed no MTT blue conversion at 500–2000 µg/mL. Garlic and cassava had the same MTT result only at 2000 µg/mL. Onion and green tomato retained MTT conversion at all tested doses. | [PDF 2–5](sources/boulogne2012.pdf#page=2), especially Tables 2–3 on PDF 5; [DOI](https://doi.org/10.1603/EC11313). |
| **Papaya: Lobo-Echeverri2020** | Leaf extracts completely inhibited growth at **2.5 mg/mL**. Squalene and carpaine gave **25.67% and 27.67% inhibition**, and the 1:1 combination 41.86%, at the labelled 0.5 mg/mL dose. Commercial quercetin had no reported effect. | [PDF 4–5,8](sources/lobo2020papaya.pdf#page=4), methods and Fig 3; [DOI](https://doi.org/10.1080/09670874.2019.1610812). |
| **Souza2005: Pilocarpus grandiflorus** | **Vanillic acid, syringaldehyde and platydesmine each gave 80% inhibition at 50 µg/mL.** Dictamine gave 40% at 40 µg/mL. Six compounds have tabulated null results. The new imidazole alkaloid in the title has **no activity-table entry**. | [Table 3, PDF 3](sources/souza2005.pdf#page=3); methods PDF 4 refer to the 1990 sesame protocol; [DOI](https://doi.org/10.1515/znb-2005-0715). |
| **Lapointe1996: forage grasses** | Marandú and Basilisk homogenates almost prevented outgrowth. Pasto Humidicola inhibited isolates from both ant species, with weaker inhibition on dilution. Carimagua1 and Llanero provide susceptible comparisons. Active molecules remain unidentified. | [PDF 3,5–7](sources/lapointe1996.pdf#page=3), Figs 3–5; [DOI](https://doi.org/10.1093/jee/89.3.757). |
| **Melo2020: oils and compounds** | **Citral IC50 is 31.7 µL/L air by fumigation and 289.9 µL/L medium by contact.** At 123.21 µL/L air, no regrowth followed transfer to untreated medium. Myrcia leaf oils and isopulegol were also inhibitory. Aristolochia trilobata **stem oil**, plus several tested compounds, gave null screening results. | [PDF 4–5,8–9](sources/melo2020.pdf#page=4), Figs 2–3; [DOI](https://doi.org/10.1007/s11356-020-08170-z). |
| **Pagnocca1990: sesame** | Chloroform/methanol leaf extracts left 40% growth at 60 mg **dry-leaf-equivalent**/mL, with low-dose nulls. Water extract stimulated growth. Fruits and seeds also inhibited. Sesamin/sesamine was not detected in leaves by the reported analyses; leaf activity cannot simply be assigned to it. | [PDF 2–3](sources/sesame1990.pdf#page=2), Tables 1–2; [DOI](https://doi.org/10.1017/S0007485300050550). |
| **Araújo2022 review** | Added the supplied PDF and corrected the first author to **Sean Araújo**. Its compound tables remain discovery aids; they are not additional independent assay observations. | [Saved review](sources/araujo2022.pdf); [DOI](https://doi.org/10.3390/insects13040359). |

## Qualifications that affect modelling

**Exposure basis matters as much as the number.** Melo’s air-volume and medium-volume concentrations cannot be placed on a common potency scale without an exposure model. Its contact screening method says 1400 µL/L, while the results and Fig 2 give inactive-compound IC50 bounds of >1000 µL/L; the extraction preserves the reported bound and the conflict. Sesame doses refer to original dry plant material, and grass doses to homogenate dilution. Neither is recovered extract mass. No density, extraction yield or molecular weight has been guessed to force comparable units.

**“More inhibition together” is not sufficient evidence of synergy.** The papaya mixture gave a larger effect than either component alone, but the 0.5 mg/mL label does not clearly specify mixture-total versus each-component concentration. The paper does not establish a dose-matched additivity benchmark. The combination is retained as a mixture result, with synergy unproven. Melo’s tested mixture synergy concerns **ant mortality**, not fungal inhibition.

**A metabolic assay and a recovery assay answer different questions.** Boulogne classified MTT-negative cultures as fungicidal, but no recovery-transfer test was reported. Melo did transfer citral-exposed mycelium to untreated PDA: the upper IC99 confidence-limit dose prevented regrowth during the seven-day observation. These remain separate endpoints. Boulogne’s IC50/IC99 fit basis is also incompletely specified across solid and liquid measurements, and several estimates extrapolate beyond the 500–2000 µg/mL treatment range.

**Chemical detection does not label every molecule active.** Papaya’s untested glycosides must remain distinct from the commercial quercetin aglycone. Souza’s new compound is not given a positive or negative label because it is absent from the activity table. The sesame study does not identify its active leaf constituent. Commercial citral and other purchased reagents need structure, isomer and purity curation before molecular descriptors are assigned.

The assay table preserves confidence intervals, exposure route, concentration basis, source pages and study-grouping cues. Qualitative observations and controls are marked for appropriate use. **No predictive model was trained, and the frozen primary analysis tables remain unchanged.**

## Access status and reproducibility

Eleven of the original twelve requested journal articles are now supplied and checked. **Morais2015 is the only journal article still pending**, with its related original thesis obtained and checked. See the [updated request list](FULL_TEXT_REQUESTS.md).

[Supplied-file provenance](user_supplied_fulltexts_batch2.json) records original filenames and SHA-256 hashes. [Morais retrieval log](morais_retrieval_log.json) records the successful thesis download and unsuccessful article route. [Assay contexts](assay_contexts_from_fulltexts.json) preserve controls and replication details. `extend_assays_batch2.py` rebuilds the combined extraction, then `build_bundle.py` rebuilds the browser and evidence tables. Existing record IDs F001–F040 and plant IDs P001–P095 were retained; three new plant controls were appended.

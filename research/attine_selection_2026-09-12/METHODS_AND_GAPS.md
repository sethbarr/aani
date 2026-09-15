# Search methods, provenance, and limits

Search date: **12 September 2026**. Question: which plants plausibly contain compounds harmful to the fungus gardens of fungus-growing ants, and where can the original observations and experiments be validated?

## Scope and inclusion

Searches included plant selection, preference, avoidance, rejection after collection, delayed rejection, chemical defense, leaf extracts, isolated plant compounds, cultivar growth, and garden deterioration. Atta and Acromyrmex dominate the evidence. Grass cutters and non-leaf-cutting fungus growers were also searched. Synthetic fungicides and microbial metabolites were retained only when they explain mechanisms or confounds; they are not plant-derived chemical candidates.

English, Portuguese, Spanish, French and German terms and sources were included. Theses, dissertations, university reports, conference abstracts, books/chapters, institutional records and journal papers were eligible. No starting publication date or language exclusion was imposed.

**This is not a PRISMA-complete systematic review.** The search is broad and reproducible, but the 1,834 discovery records were not all read in full or independently screened by two reviewers. The 157 selected bibliography entries include unresolved leads and background mechanisms. No formal risk-of-bias instrument or meta-analysis was applied, and citation chasing has not reached demonstrated saturation.

## Sources actually searched

- User’s local Obsidian notes and CSVs in `/Users/seth/Dropbox/ObsidianVault/anty fungals`.
- **Semantic Scholar public Academic Graph API**, accessed directly with `collect_s2.py`; no private connector or account installation was needed. Ten multilingual/taxon query families were paginated, yielding 1,834 distinct paper IDs. Paper-ID uniqueness does not guarantee unique intellectual works.
- Web search for primary publisher pages, PubMed/Europe PMC, SciELO, CONICET, UBA, UENF, UFSCar, UNESP, UFLA, EAFIT, UFS, UNIVALLE, HAL/INRAE, theses.fr, DNB, Southampton, Würzburg, Embrapa, SBQ, and regional institutional repositories.
- Backward reference searches from the 2022 cultivar-control review, the 2026 foraging review, original papers and downloaded theses. Selected newer papers and grey reports were sought explicitly through 2026.
- Publisher Figshare API and archive for Howard 1987 supplementary material.

Scopus and Web of Science were **not** searched through authenticated subscriptions. Mentions of those databases in a retrieved report describe that report’s methods, not searches performed for this bundle. Google Scholar was not exhaustively paginated. Semantic Scholar is an index and discovery aid; original papers/repository documents support extracted scientific claims.

## Search language families

Taxa included Atta cephalotes, A. colombica, A. sexdens, A. texana, A. laevigata, A. mexicana, A. insularis, A. capiguara, A. bisphaerica, A. vollenweideri, A. opaciceps, Acromyrmex, Amoimyrmex, and selected non-leaf-cutting genera including Trachymyrmex and Mycetomoellerius. Cultivar searches included Leucoagaricus, Leucocoprinus, Attamyces and historical names found in the sources.

| Language | Examples used in discovery |
|---|---|
| English | leaf-cutting / leafcutter / fungus-growing ants; plant selection; preference; avoidance; rejection; substrate; foraging; antifungal; extract; thesis; dissertation |
| Portuguese | formigas cortadeiras; seleção / seletividade; preferência; rejeição; forrageamento; extrato vegetal; fungo simbionte; tese; dissertação |
| Spanish | hormigas cortadoras / arrieras; selección; preferencia; rechazo; forrajeo; hongo simbionte; extractos; tesis |
| French | fourmis champignonnistes / attines; affouragement; antiappétants; antifongique; thèse |
| German | Blattschneiderameisen; Pflanzenwahl; Pflanzenvolatile; symbiotischer Pilz; Diplomarbeit; Dissertation |

Exact API queries, totals, page records and failures are in [s2_search_log.json](s2_search_log.json), [collect_s2.py](collect_s2.py), and `raw/s2_query_*`. The web searches and returned result text are archived in [web_search_archive.json](web_search_archive.json) and [web_search_final_additions.json](web_search_final_additions.json). The older `search_log.json` is an early partial snapshot, not the final complete log.

## Screening and extraction

Discovery records were screened selectively by title/abstract for relevance, with priority given to studies linking ant behavior to cultivar assays, isolated plant compounds, multi-plant comparisons and non-English grey literature. The full discovery pool remains available for further screening. Bibliographic duplicates in the selected set were consolidated by DOI or normalized exact title where recognized. Thesis–article pairs are retained as source routes, but flagged as potentially overlapping experiments.

The candidate table is a **plant-level evidence map**, not a fully normalized observation database. A separate [149-record extraction from twelve primary full texts](compound_assays_from_fulltexts.csv) now preserves individual treatment results, fitted endpoints and controls, with [assay context](assay_contexts_from_fulltexts.json). These records are not independent experiments and the extraction covers these twelve sources, not the entire bibliography. A row may link several experiments. It preserves study-specific doses and outcomes in text; it must not be treated as an assay-ready matrix of independent replicates. Priority categories mean:

- **1 — First validation:** especially useful chemical/evidence chain for the user’s purpose; some full-method checks remain.
- **2 — Direct assay:** reported cultivar inhibition, with details and read status distinguishing original tables from abstract-only or secondary quantitative values.
- **3 — Tentative:** partial or weak effects, unresolved species/doses, confounding, secondary leads, or chemical/behavioral evidence without a validated cultivar effect.
- **4 — Negative/control:** evidence that challenges a simple avoidance-to-antifungal inference; no universal safety claim.

PDF text was extracted with pypdf. Key numerical pages from Diaz Napal 2015, Arêdes 2018 and supporting materials were rendered for inspection with pypdfium2. Additional rendered pages are available in `validation_images`; a rendered page is not automatically a fully reviewed table. French Boulogne thesis text has defective embedded character mappings; reliable numeric extraction remains incomplete.

The 89-species Diaz Napal table was transcribed, retaining source spellings and both inactive and positive fungal outcomes. It passes count checks: 89 rows, 11 fungal positives, 12 AFI>70, two with both. This is a single-screen dataset with one ant colony, not 89 independent colony experiments. The local 33 Wirth leads are derived from the user’s existing transcription and are explicitly unvalidated against the original book tables here.

## Important source corrections and cautions

- **Ricinus:** Bigi2004 Tables 1–2 report remaining growth. Active fractions contain fatty acids, and MFHE-9 also contains glycosylsteroids; no individual acid was proven causal. Ricinine’s fungal sentence is grammatically defective, so its context-interpreted null at 1 mg/mL is held out of numeric and binary model labels.
- **Pagnocca1996:** Table 1 gives <20% remaining growth for sesamin/epigalgravin, whereas prose says complete inhibition; preserve the table bound. Otoba fruit philygenol shows only 20% inhibition.
- **Howard1988:** Table 1 gives day 7 ordinal scores, not MICs. Kolavenol has a null fungal result.
- **Hubbell1983:** 8/10 damaged cultures at 100 µg/mL is damage incidence, not 80% growth inhibition.
- **Salazar2020:** IC50/IC95 are fitted concentrations from the same curves, not independent treatment measurements; ppm retained, confidence intervals not supplied.
- **Gallesia:** Arêdes Figure 3 shows overlapping Tukey groups with untreated control despite lower numerical growth; candidate remains tentative.
- **Helietta:** PDF publication date is 2007; website metadata says 2009. Molecule concentrations conflict between methods and table (50 vs100 µg/mL).
- **Simarouba:** analogous methods/table conflicts for compounds and fractions; not silently reconciled.
- **Raulinoa:** table uses µg/mL while a discussion sentence prints mg/mL; compound 2 is kokusaginine in identification prose but Kokusagine in table.
- **Cipadessa:** the 2022 review’s 1000 mg/mL entries conflict with the 2003 original thesis’s 1000 µg/mL. Use the original assay units.
- **Febvay:** saved filename contains 1986, but the HAL wrapper cites Agronomie5(5),1985. Author’s first name is Alain Kermarrec on the article; the wrapper’s expanded author field differs.
- **Santos:** 2013 thesis defense versus 2014 repository deposit metadata.
- **Infante-Rodríguez:** issue2026; PDF’s online-first date lies after this search date, and a P-value sign conflicts with the significance wording. Retain the document, flag the inconsistencies.
- **Essential oils2026:** concentration is that of a surface-applied solution, not necessarily concentration throughout the agar.
- **Virola:** original sources support condition-dependent acceptance, not a blanket avoided-species designation. Related thesis and paper are not independent validation.

## Remaining coverage gaps

1. **The supplied 1983/1988 terpenoid,1996 lignan,2004 Ricinus and 2020 dillapiole full texts are now checked.** The TRAMIL, papaya, Pilocarpus, forage-grass, oil and sesame requests are now resolved. Morais2015 remains pending, with the original 2012 thesis obtained; see [FULL_TEXT_REQUESTS.md](FULL_TEXT_REQUESTS.md). Remaining issues in the supplied originals include lignan source codes/stereochemistry, an unidentified Virola species, defective ricinine wording, and unreported raw dose-response data or strain identities.
2. Hubbell1984’s 42-plant full table: university abstract found; direct PDF returned403. Howard1987’s recovered 50-plant supplement is the best immediately available related primary dataset, but has not been fully transcribed.
3. The original Wirth book tables behind local BCI non-harvest labels and modern taxonomic reconciliation. Preserve genus-level ambiguity and cultivar names.
4. Some catalogue-only theses, older regional bulletins, conference proceedings and non-digitized historical reports. Not all records have complete author/title/page metadata.
5. Grey-material leads cited in review references, including Forti1985’s plant-attack bulletin, Vitório1996’s grass-selectivity thesis, and Garcia1997’s Eucalyptus/secondary-forest foraging thesis. Original files not secured; see `review2026_references.txt` for the cited bibliographic strings.
6. Plant identity for IB151239 and genus-only Virola/Bauhinia/Licania/Pinus/lavender leads. No exact species is inferred from a code or common name.
7. Complete dose-response, solvent, replication and strain verification for abstract-only studies; whole-colony validation and chemical isolation for many extracts.
8. Coverage beyond the main Atta/Acromyrmex literature is sparse. Dietary DNA establishes material use but generally not avoidance or toxicity. Non-European-language indexing and undigitized literature may remain missed.

The search found additional leads in its final targeted passes, so **exhaustiveness or saturation cannot honestly be claimed**. This bundle provides a substantially expanded source map, strongest current starting candidates, and a transparent queue for validation instead of hiding uncertainty in a single avoided-plant list.

## Reproduce or update

`collect_s2.py` performs the recorded public API search and saves raw pages. `retrieve_sources.py` retrieves the URLs listed in `download_manifest.json`, checks the PDF signature, extracts text and writes page counts and SHA-256 hashes to `download_log.json`. Failed TLS/403 downloads are recorded, not bypassed.

`build_bundle.py` has no network calls. It builds the CSV/JSON/RIS files and the standalone evidence browser from curated source-linked entries, raw discovery metadata, the transcribed table, and the user’s local Wirth CSV. No records were added to the project’s primary observation/assay tables, and the frozen analysis plan was not changed.

## Supplied full-text update

Five user-supplied PDFs were added on 12 September 2026, bringing the collection to 25 PDFs. Relevant numerical pages were rendered and visually checked, including Pagnocca Table 1/Figure 1, Howard Table 1, Bigi Tables 1–3, Salazar Figures1–3 and Hubbell’s fungal results. The [validation report](FULL_TEXT_VALIDATION.md) distinguishes findings, source contradictions and proposed modelling decisions. `extract_supplied_fulltexts.py` reproduces the curated 40-record CSV/JSON and separate fatty-acid composition table; it does not infer missing structures or fit a predictive model. The source manifest preserves SHA-256 hashes and user-supplied filenames. The first five access requests were marked received and checked.

## Second full-text update

Six more requested primary papers and the already-consulted 2022 review were supplied by the user; Morais’s2012 UFV master’s dissertation was retrieved openly. The collection now contains 33 PDFs. New tables and figure annotations were visually checked.109 new records bring the combined assay/endpoint/control table to 149; three plant controls bring the evidence map to 98 plants. See [FULL_TEXT_VALIDATION_BATCH2.md](FULL_TEXT_VALIDATION_BATCH2.md) for dose-basis issues, mixture and recovery endpoints, and the one remaining journal article request. Run `extend_assays_batch2.py` before `build_bundle.py` to regenerate the combined extraction.

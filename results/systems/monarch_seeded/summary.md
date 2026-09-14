# Seeded monarch rerun — focal comparison recovered, fungal join is a coverage probe

This exploratory rerun is excluded from inference. **All five requested seed
PDFs are now supplied, cached and identity-verified.** Europe PMC still has no
indexed full-text route for these seeds; the supplied PDFs have separate local
provenance. The combined corpus contains 25 papers, with 8 screened in and 17
screened out. The extra de Roode virulence-transmission paper is outside the
declared five-seed set and the extraction budget.

Seeding known primary sources recovered the focal infected-versus-uninfected
comparison that the 20-source discovery corpus missed, the same
targeted-retrieval effect seen when Saverschek was added to the leafcutter
corpus. The [completed funnel](funnel.json) records one focal-eligible and
one infection-comparison-eligible Asclepias genus, with two infected and two
uninfected retained records. These runs do not establish biological
generalisation.

**Source-design recovery: confirmed in Lefèvre 2010 and 2012.** Both papers
report infected and uninfected female monarchs choosing between A. curassavica
and A. incarnata. The 2012 paper reports a distinct replication. Infected
females prefer A. curassavica; uninfected females show no species preference.
The latter direction remains unknown. Complementary egg shares do not create
an A. incarnata rejection record.

**Model-record recovery: both infection groups survive from Lefèvre 2010.**
Their retained target species differ, so a same-target infected/uninfected
panel remains incomplete. All twelve jobs completed:
five new jobs for the two Lefèvre seeds and seven exact cached discovery jobs.
The unchanged adapter produced 13 candidates, of which 9 passed grounding and
4 survived semantic review. No curator-added records were created. Lefèvre
2012 retains an uninfected no-preference record; its infected-preference
candidates failed the fixed grounding checks.

The fresh ChEMBL query returned **0 assays for the exact organism name
Ophryocystis elektroscirrha**, across all assay types, confirmed against the
complete inventory. Database assay coverage only; inactivity is unmeasured.

## Amendment and fixed methods

The amendment was committed before retrieval:

- Commit: `a70546497beeb59ba929bccf93bd4c46b19758b4`.
- Commit time: `2026-09-13T13:30:55-04:00` (`17:30:55 UTC`).
- Amendment SHA-256: `f1b930813d59578c52daa5fc95b50a5ba35875d2b816b115806eac0766a1bc68`.
- First Europe PMC seed request started at `2026-09-13T17:33:36.047810+00:00`.

The run uses the original monarch system adapter, Gemini model, prompt,
schema, 24,000-character whole-block chunking and `single_quote_v1` grounding.
The cap is 12 extraction jobs; selected papers are processed in full, with
seeds first. Multispan and v4 glyph recovery are excluded from this rerun.
All eight adapter compatibility checks passed, including exact regeneration
of the original ten payload hashes. User approval for the exact twelve-job
cohort was recorded at `2026-09-13T19:42:38+00:00`. Extraction ran from
`19:43:26.008722` to `19:43:37.253785 UTC`, with five new persisted provider
responses and seven reused discovery responses. The earlier preparation and
approval-gate reports preserve their pre-approval state; the approval and
extraction manifests record execution.

At semantic review, accept requires a species preferred in an oviposition
choice test; reject requires a species avoided in that test. Every reviewed
record receives evidence-linked choosing-female infection status: infected,
uninfected or unreported. Unreported status is flagged and cannot satisfy the
focal design. Raw model records remain unchanged. Source-design recovery,
original model-record recovery and any curator-added context are counted
separately.

## Seed retrieval table

| Seed | Verified DOI | Europe PMC status | Earlier public access result | Current local full text |
| --- | --- | --- | --- | --- |
| Lefèvre et al. 2010 | [10.1111/j.1461-0248.2010.01537.x](https://doi.org/10.1111/j.1461-0248.2010.01537.x) | `not_open_access`: no PMCID/fullTextXML route | Public Michigan PDF request: HTTP 403 | Retrieved from user; 9 pages; include |
| Lefèvre et al. 2012 | [10.1111/j.1365-2656.2011.01901.x](https://doi.org/10.1111/j.1365-2656.2011.01901.x) | `not_open_access`: no PMCID/fullTextXML route | Public Michigan PDF request: HTTP 403 | Retrieved from user; 10 pages; include |
| de Roode et al. 2008 | [10.1111/j.1365-2656.2007.01305.x](https://doi.org/10.1111/j.1365-2656.2007.01305.x) | `not_open_access`: no PMCID/fullTextXML route | Public Michigan PDF request: HTTP 403 | Retrieved from user; 7 pages; background |
| Sternberg et al. 2012 | [10.1111/j.1558-5646.2012.01693.x](https://doi.org/10.1111/j.1558-5646.2012.01693.x) | `not_open_access`: no PMCID/fullTextXML route | Public Michigan PDF request: HTTP 403 | Retrieved from user; 10 pages; background |
| Gowler et al. 2015 | [10.1007/s10886-015-0586-6](https://doi.org/10.1007/s10886-015-0586-6) | `not_open_access`: no PMCID/fullTextXML route | Publisher subscription access; full text not requested | Retrieved from user; 4 pages; background |

`not_open_access` above describes Europe PMC holdings. Local user supply does
not establish an OA licence. No citation was classified as not found, and no
paywalled text was scraped. All 40 supplied seed pages have text blocks with
source checksums and page coordinates. Thirty-three download-account margin
watermarks are excluded with hashes and bounding-box provenance; article text,
captions, references, printed hyphens and embedded-font glyphs are preserved.

The [Europe PMC access history](seed_access.json), [local PDF access manifest](local_pdf_access.json)
and [extraction manifest](extraction_manifest.json) distinguish the failed
public routes, supplied full texts and executed source selection.

Two tentative titles needed correction. Sternberg's indexed title is *Food
plant derived disease tolerance and resistance in a natural butterfly-plant-
parasite interactions*. Gowler's title ends *, Danaus plexippus*. The indexed
Sternberg wording is preserved. See the complete
[source-gap table](../../../docs/source_gaps_monarch_seeded.md)
and [bibliographic audit](bibliography_audit.json).

## Side-by-side funnel

The original column is the first monarch run, using single-quote grounding.
It excludes the later v4 replay. All seeded stages through bioactivity completed.
Both fungal bioactivity joins are **coverage probes**. One inactive Asclepias
compound against the primary fungal panel does not test the monarch-parasite
mechanism.

| Stage | First monarch run | Seeded rerun |
| --- | ---: | ---: |
| Ready discovery papers | 20 | 20 |
| Verified seed citations | 0 | 5 |
| Retrieved seed full texts | 0 | 5 user-supplied |
| Ready combined papers | 20 | 25 |
| Screened-in discovery papers | 6 | 6 inherited decisions |
| Full-text-screened seed papers | 0 | 5: 2 include, 3 exclude |
| Complete papers extracted | 5 | 6 |
| Extraction jobs completed | 10 | 12: 5 new, 7 cached |
| Model candidates | 5 | 13 |
| Grounded model records | 5 | 9 |
| Semantically retained records | 2 | 4 |
| Resolved taxon identities | 2 | 2: A. curassavica and A. incarnata |
| Eligible directional genera | 1 ancillary genus | 1 focal-design genus; infected accept only |
| Genera with LOTUS chemistry | 1 | 1 |
| Mapped compounds | 417 | 417 |
| Compounds matched in ChEMBL | 69 | 69 |
| Classified compounds: fungal coverage probe; does not test the monarch-parasite mechanism | 1 inactive | 1 inactive; 0 active |
| Unknown-activity compounds | 416 | 416 |
| Genera with classified compounds: fungal coverage probe | 1 | 1 |
| Focal source experiments recovered | 0 | 2 |
| Experiments with both infection groups in retained model records | 0 | 1: Lefèvre 2010 |
| Same-target infected/uninfected model panels | 0 | 0 |
| Exact-name Ophryocystis assays, all types | 0 | 0, fresh query |

The 20 discovery texts and their recorded screening decisions are retained
with separate original-source provenance. The six screened-in discovery
papers remain the original extraction pool. The stricter seeded semantic
rules still require a direct between-species choice for an included record;
within-species watering or aphid treatments cannot satisfy that rule.

The selected papers are LEFEVRE2010 (2 jobs), LEFEVRE2012 (3), PMC12585044
(2), PMC10370756 (2), PMC10430791 (1) and PMC9197062 (2). The whole-paper
cap excludes PMC9351326 and PMC9273743. All seven selected discovery hashes
match their original cached jobs. The three background seeds remain in the
25-source corpus: de Roode 2008 assigns larval host plants, Sternberg 2012
assigns larvae to 12 plant species, and Gowler 2015 assigns larval leaf-disc
and latex treatments. Sternberg's oviposition statement cites the two Lefèvre
experiments and supplies no third primary oviposition experiment.

| Primary focal source | Choosing female groups | Choice design |
| --- | --- | --- |
| Lefèvre 2010, Experiment 2 | 22 infected; 29 uninfected | Western North American source population; two-hour individual dual-species trials, repeated on separate days |
| Lefèvre 2012, trans-generational medication experiment | 10 infected; 10 uninfected | Eastern North American source population; one-hour individual dual-species trials, repeated after two days |

These are source-reported sample sizes. The
[source-design review](source_design_review.json)
binds the two experiments to eight exact source quotes in the final payloads.
These annotations are independent of model output.

The four retained model records comprise two infected-female A. curassavica
accept records from the same 2010 experiment, one uninfected-female
A. incarnata unknown-direction record from that experiment, and one
uninfected-female A. curassavica unknown-direction record from the 2012
experiment. The two 2010 accept records describe the main analysis and its
foliage-biomass reanalysis. They count as one experiment. Four source-supported
taxonomy query expansions add full binomials in separate metadata and preserve
the abbreviated raw model names.
Pairing above uses source and experiment identity. The 2010 infected rows
target A. curassavica; the uninfected row targets A. incarnata. No missing
species-by-infection records were added. The uninfected no-preference records
remain in the reviewed dataset and contribute no directional chemistry inputs.

Four candidates failed grounding: two expanded a target name beyond the name
in their quoted span, one joined a split figure caption, and one crossed the
2012 results page boundary and changed a printed ﬁ ligature. The latter two
failed exact single-block quote grounding. No alternate grounding method was
applied. The split-caption candidate also concerns larval chemistry and spore
loads, outside the adult oviposition design.

The first run's two retained records do not form the focal comparison. Its
eligible directional evidence concerns a within-species watering treatment,
and its genus-level chemistry coverage does not establish chemistry for the
particular tested species.

## Assay inventory and where the join ends

ChEMBL reported version `ChEMBL_37`, release date `2026-05-01`. The exact-name
parasite request completed at `2026-09-13T17:37:03.305245+00:00`, returning an
empty assay list and `page_meta.total_count = 0`. The request used
`assay_organism=Ophryocystis elektroscirrha`, with no assay-type filter, and has
hash `c570c012a4fdb98120fb583d27ff3a2d0b1cab97ff6b8999a1cb72bdad2cd1b1`.
This query makes no claim about alternate spellings or unindexed experiments.
The [assay-scope manifest](assay_scope_manifest.json) confirms the exact-name
parasite absence against the complete inventory. Database assay coverage
only; inactivity is unmeasured.

| Primary organism | Functional assays (`assay_type=F`) |
| --- | ---: |
| Candida albicans | 11,912 |
| Cryptococcus neoformans | 2,038 |
| Aspergillus fumigatus | 2,372 |
| Total | 16,322 |

The inventory queries ran before the user supplied the seed texts and were
replayed from this run's cache during downstream processing. Live downstream
processing completed at `2026-09-13T19:50:04 UTC`, within the declared deadline.
All four retained records resolved to two species. The two infected accept
records support one eligible Asclepias genus; the two uninfected records keep
unknown direction. There are no directional genus conflicts.

The pinned LOTUS export is `zenodo:6582121:v4`, SHA-256
`ffb310fffb395514e2fec5f42b682812d4f459c8783b884c67a737621ee2b5d2`.
It yields 511 distinct occurrences and 417 distinct full InChIKeys for the
genus-wide join. Exact A. curassavica rows contain 150 compounds and exact
A. incarnata rows contain 101; their union contains 249. These species-level
coverage counts did not change the genus-level selection rule.

ChEMBL matched 69 structures. One compound, acetyl oleanolic acid
(`CHEMBL486822`; `RIXNFYQZWDGQAE-DFHVBEEKSA-N`), has one eligible measurement:
Candida albicans MIC = 250,600 nM, assay `CHEMBL5583151`, activity `26033117`.
The frozen 10 µM threshold classifies it inactive. LOTUS records this compound
in A. curassavica. The remaining 416 compounds have unknown activity under
the frozen panel and rules; none had a retrieval failure.
This fungal bioactivity join is a **coverage probe**. One inactive Asclepias
compound against the primary fungal panel does not test the monarch-parasite
mechanism.

The behavioral source gap is resolved, and the unchanged extractor recovers
both infection groups at the 2010 experiment level. Model recovery remains
incomplete for matched species-by-infection panels and the 2012 infected
group. The downstream join reaches a genus-wide chemical set; its one inactive
fungal classification is a coverage probe and does not test the monarch-parasite
mechanism. The exact-name parasite assay gap prevents a measured
Ophryocystis activity join. No analysis stage or inferential statistic ran.

## Verification and preservation

All executed seeded stages passed offline verification. The audit reconstructs
Europe PMC metadata, access decisions, local PDF text, the 25-source corpus,
screening and source-design annotations from their caches. It verifies the
exact approved Gemini requests against raw provider responses, regenerates
all 13 candidates through the unchanged validator, and checks all semantic
adjudications against their source evidence. Extraction, semantic observations
and semantic decisions match their offline replay files byte-for-byte.

Taxonomy, infection-aware genus aggregation, pinned LOTUS occurrences and
ChEMBL measurements and labels also reproduce offline. Documented comparisons
exclude only operational fields such as replay paths and timestamps.
Scientific counts and record content remain checked. The verifier made zero
network or model calls. An initial sandbox taxonomy transport failure is
preserved in `execution_history/`; the subsequent network-enabled run completed
with no stage errors or failed compounds.

The artifact audit records **753 passed checks, 1 failed check and 0 unavailable
checks**. The sole failure is original-file-set membership: 29 `grounding_v5`
files appeared under the original monarch namespace after its snapshot. All
277 captured files retain their hashes, all 200 files covered by the earlier
audit match, and frozen primary inputs match `98b5e09`. No original file was
removed. The full snapshot was captured at `2026-09-13T17:40:20.212387+00:00`,
after retrieval; the earlier audit dates to `17:07:26.825793 UTC`. The seeded
workflow preserves the additions and reports the file-set discrepancy. It
cannot attribute those concurrent writes, so the overall audit retains its
failed status despite successful seeded-stage replay.

The scoped regression suite passes 192 tests, and Ruff passes. The
[verification report](verification.json)
contains each check. The
[semantic report](semantic_review.json)
separates source experiments, experiment-level infection-group recovery and
same-target panels. The
[downstream manifest](downstream_manifest.json)
and [funnel](funnel.json)
record the completed joins. This rerun remains excluded from inference;
outcome-level biological generalisation is not established.

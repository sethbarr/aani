# Implementation decisions

The initial protocol commit is `98b5e09`. No joined behavioural/antifungal
outcomes were inspected before this commit.

On 2026-09-12 the first corpus request returned zero because a sort field was
mistakenly embedded as a search term. The corrected request supplies
`sort=FIRST_PDATE_D desc` separately. The failed request remains in the raw cache.

The first working, unscoped query returned 813 hits; 30 full texts were retrieved
from 31 attempts. Inspection of their titles showed unrelated medical articles,
consistent with matching Atta as an author name. Before extracting observations
or inspecting activity, the pilot query was narrowed to require the ant terms in
`TITLE_ABS`. Behavioural terms remain unrestricted. The original corpus is retained
under `data/interim/corpus_unscoped`; the corrected corpus has its own manifest.
This improves precision and may miss papers whose abstract omits the ant taxon.
It is a documented retrieval refinement, not an outcome-selected query.

LOTUS/COCONUT are implemented through an explicit occurrence import contract.
Versioned export conversion and source licensing must be verified for the chosen
download before scaling; no undocumented taxon API is assumed. CO-ADD is reserved
for separate validation because availability of a reusable compound-level dataset
has not been established in this build.

The local scaffold now includes offline tests for quote grounding, namespaced
JATS parsing, GBIF response interpretation, assay threshold boundaries,
discordant activity labels and seeded permutation results. The README framing
also states the method claim explicitly: the novelty is tractable extraction
and joining at literature scale, while the biological prior comes from older
zoopharmacognosy work.

The corrected query's cached Europe PMC responses were replayed offline into a
30-paper pilot manifest (30 full texts, 67 extraction chunks). No model
responses are cached yet, so extraction has not been attempted and no
behavioural/antifungal outcome has been inspected.

## Screened pilot execution — 2026-09-12

Before the first model extraction, title/abstract relevance screening was added
as an explicit execution amendment. The original 30-paper manifest and query
remain unchanged. `config/pilot_screening.json` records a decision and reason
for every paper. Clear unrelated topics are skipped; uncertain plant-choice,
treated-substrate, extract and secondary-report papers remain eligible for
extraction. Screening does not depend on an antifungal assay outcome.

The screened subset is a feasibility pilot within the original retrieval
sample; it is not a new sample of 30 relevant papers. Skipped papers are counted
separately from no-observation responses and failed requests. The extraction
schema, prompt, confidence threshold and primary biological eligibility rules
remain as frozen. The selected extraction model is `gpt-5.4` as requested.
Outputs and per-request responses are checkpointed, with request hashes and
token usage retained. Subsequent runs use the raw response cache.

The Obsidian notes were inspected before this extraction and contain prior
behavioural interpretations and qualitative compound-activity claims. These
are existing hypothesis-generating knowledge; the build is not blinded to
those notes. No pipeline chemistry/activity join or enrichment has been run.

Screening retained 10 papers and excluded 20, producing 20 extraction jobs.
The first live `gpt-5.4` smoke run attempted the two chunks of PMC12941067.
Both received HTTP 429 with `credit_balance_exhausted` / `insufficient_quota`.
The original generic retry policy made four
attempts per chunk, all cached. No successful model response or extracted
observation was produced; the record rejection rate is undefined, not 0%.
Quota errors now stop retries and halt the remaining run immediately.

An offline replay verifies that the first cached quota failure stops the
screened run with the other 19 chunks marked blocked. Its metrics are a replay
status, not a claim that only one live chunk was attempted. The live smoke
metrics and raw HTTP attempt histories remain available separately.

Targeted retrieval of Crumière et al. (2021), DOI 10.1111/ele.13865,
successfully cached PMC9292433 under `data/interim/corpus_targeted_crumiere`.
Its two extraction jobs are kept separate from the screened 30-paper pilot.
The six-source gap audit is in `docs/source_gaps.md`.

## Gemini provider — 2026-09-12

At the user's request, the extraction client now also supports Gemini, after
the OpenAI credit failure and before any successful model extraction. Official
Google documentation was checked for the current Interactions REST endpoint,
structured JSON response format and `model_output` response steps. Gemini
3.8 Flash is the configurable default. The schema, prompt and source blocks
are preserved, and the existing per-record grounding checks still run.

Provider, requested and returned model, response ID, request hash and token
usage remain traceable. Gemini credentials travel only in an uncached header.
Successful requests can replay offline without a key. The original OpenAI path
is retained; provider selection is explicit or configured with
`EXTRACTION_PROVIDER`. No automatic model/provider fallback occurs.

The Gemini setup preflight reached the intended provider and stopped before
network access because no Gemini key is configured. Live authentication and
schema acceptance remain unverified. Offline tests exercise the documented
wire contract, replay, failure handling and shared grounding validation.

Validation: all 33 tests pass, including 14 Gemini cases, and Ruff passes for
`src`, `scripts` and `tests`. The frozen analysis configuration and protocol
remain identical to commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.

## Live Gemini smoke and semantic review — 2026-09-12

The user configured the Gemini key locally. Presence was checked without
displaying its value. Network-enabled requests returned HTTP 200 and confirmed
authentication, access to `gemini-3.8-flash` and acceptance of the complete schema.
An earlier sandbox-only attempt failed DNS resolution before an API response.

The first live run used medium thinking and a 16,384-token generation cap. Its
first chunk returned `incomplete`, with 15,728 thought tokens and 642 visible
output tokens; its second chunk completed. Initial outputs remain under
`data/interim/extraction_gemini_smoke_medium_16384`, alongside both raw requests.
Google's current thinking guide confirms that `max_output_tokens` includes
thought tokens. Operational settings were changed to low thinking and a
32,768-token cap before pilot scaling, to allow a completed structured answer.
The frozen source prompt, schema and scientific eligibility rules did not change.

The rerun at `data/interim/extraction_gemini_smoke` completed both chunks of
PMC12941067 with four candidates and no response failures. Two candidates
failed `plant_not_in_quote`. The two passing automated schema/grounding checks
were then excluded on source review: the Eucalyptus quote says seedlings were
offered, and the Acalypha quote describes leaves placed daily for husbandry.
Neither establishes an observed acceptance outcome. This demonstrates why
text grounding alone is insufficient for semantic validity.

`semantic_review.json` records each exclusion and its source block, and
`semantic_review_observations.jsonl` is empty. Raw model output and automated
metrics remain unchanged for audit. There are zero semantically approved
observations from this smoke paper. The treated rejection candidates were
labelled experimentally treated, but the smoke does not establish that a
downstream treatment-exclusion stage has been exercised. The full 20-job
pilot has not run. All 33 tests and Ruff still pass after the settings change.

## Full screened Gemini extraction — 2026-09-12

At the user's request, all 20 jobs covering the 10 included pilot papers were
run with the existing prompt, schema, Gemini 3.8 Flash, low thinking and
32,768-token cap. The two successful smoke responses were reused from the raw
cache. All jobs and papers completed without API failures or unattempted chunks.
Outputs are at `data/interim/extraction_gemini`.

The run returned 47 candidates: 35 passed automatic validation and 12 failed,
for an automatic rejection rate of 12/47 (25.5%). All 35 passes received a
separate source review with exact record, input and response hash checks. Six
were included as observed natural-leaf acceptance, 26 were excluded from the
primary evidence table, and three remain pending. Every retained record comes
from PMC11543716. They require taxonomy; there is no retained rejection evidence
and no estimable behavioural contrast at this stage.

The review found autoclaved diets labelled natural, husbandry construed as
acceptance, artificial-substrate assays, duplicated secondary reports and
mixed control/exposed-colony contexts. No raw candidate was changed or rescued
after a failed grounding check. `semantic_review.json`, the three separate
review-result JSONL files and `evidence_review.csv` preserve the audit. Agent
shards contain source-specific limitations, including missing supplements,
overlapping datasets and genus names detected only in garden DNA.

All 20 jobs were then replayed without network access into
`data/interim/extraction_gemini_offline`. Observations, rejections, failures,
chunk status and metrics matched the live outputs byte-for-byte. The protocol
and extraction code were unchanged during this run. No taxonomy/chemistry join
or activity outcome was computed.

## Taxonomy, source recovery and design critique — 2026-09-12

Five source-specific name mappings resolve six pilot records into four distinct
scientific queries. The new mapping adapter validates exact source-document
hashes and quote anchors, keeps original extracted names/ranks and IDs, and adds
separate query fields and mapping provenance. GBIF returned six exact matches
at confidence 99–100, with Tococa quadrialata resolving to Miconia microphysca.
Taxonomy replay matched cached outputs exactly. Eight new mapping tests pass;
taxonomy code and tests pass Ruff. The broader suite has 49 passes and one
unrelated experiment-viewer failure (missing viewer.template.html); broad Ruff
also reports an unused json import in that separately changing planner module.

The three pending pilot claims were resolved through original Tozin/Kost papers
and the explicit fungus-free Acalypha control context. Three separately labelled
Codex-assisted manual corrections were reviewed and integrated without overwriting
Gemini records. Each supersedes one pending claim. All three have exact GBIF
matches. They add acceptance, not rejection.

Saverschek 2010 was prepared separately from the fixed pilot. Direct download
failed; complete public web-tool PDF text (lines 0–1004) was archived with exact
tool request/results and hashes. Original PDF bytes and numerical-table visual
verification are unavailable. Three Gemini jobs succeeded: 14 candidates, six
automatic passes. Review retained Spondias acceptance, Desmopsis rejection and
context-specific Hymenaea rejection; a CHX-conditioned retest was excluded and
two additional leads remain pending. Opposite natural directions in source
prose are preserved as conflicts even when the model failed to extract them.

The user's supplied critique prompted a separate construct audit. The original
six are real harvesting records from a shared study, but do not establish
comparative preference; the source explicitly calls Arabidopsis and faba bean
nonhosts. The implementation's behavioural_choice field means observed collection,
feeding or rejection, not mandatory simultaneous alternatives. That broader
definition is unchanged. The new design audit makes the distinction explicit
and reports an alternatives-only descriptive view separately, without silently
amending the frozen endpoint or selection rules.

The provisional source-following/targeted snapshot at data/interim/evidence_current
holds out Hymenaea and Miconia for source-known conflicting directions. It has
six consistently accepted genera and one rejected genus, before chemistry.
The original pilot remains a distinct fixed sample; these additions are not
presented as its original yield. Enrichment remains non-estimable. No activity
dataset or chemistry join was used to decide these mappings or inclusions.

## Complete Saverschek text audit — 2026-09-12

Three parallel Codex source reviews covered natural assays, manipulation phases,
and original-source access. The root integrated and cross-checked their evidence
into `results/saverschek_audit`, with an eight-page PDF under `output/pdf`.
Seventy-one exact source anchors support the audit; one comes from the recovered
Figure 7 caption after the historical parser's References cutoff. Original source
blocks, model responses, extraction metrics, and protocol files were not changed.

The natural matrix contains 110 distinct aggregate contexts: 87 directional and
23 unresolved. Table 1 retains all 66 original tokens alongside explicitly
provisional glyph normalization. No graphical coordinates or independently
verified numerical measurements were invented. Twelve manipulation/context
phases, seven figures, one table, secondary claims, and the model's 14 candidates
are covered. Post-CHX rejection remains excluded; three baseline/control items
remain on review for treatment ambiguity.

GBIF returned ten exact species matches and one VARIANT at confidence 98 for
Trema micrantha. The exact-match rule was preserved. Source-level behavioural
counts are one accepted, five rejected, five conflicted; after exact taxonomy,
one accepted, four rejected, five conflicted. Replacing the old Saverschek rows
in a new combined snapshot yields six accepted and four rejected genera; the
five conflicts are excluded. Strict alternatives leave only one accepted genus.
No chemistry was joined and no enrichment result was computed.

Four source-specific scientific regression checks pass and the new scripts/tests
pass Ruff. The final report was rendered and all eight pages inspected. Audit
rebuild is offline; curator corrections are explicitly distinct from Gemini
outputs. Discovery of the omitted caption does not retroactively increase model
coverage or change its candidate denominator.

## End-to-end coverage run — 2026-09-12

Stages 4–6 now execute from the merged, source-audited taxonomy inputs. The
three requested original taxonomy outputs remain intact. Their 12 records were
read, with three coarse Saverschek model records replaced by 80 taxonomy-matched
directional audit contexts. The current table contains 89 grounded contexts,
16 resolved species and 15 genera. Unanimity retains six accepted and four
rejected genera; five conflicts are excluded. Explicit record-level checks put
Miconia microphysca acceptance and Miconia argentea's opposing directions together
in the Miconia conflict, outside primary inference. Context counts are not
independent biological replicates.

The complete LOTUS v4 export from Zenodo 6582121 was downloaded and its published
checksum, CC BY 4.0 licence and CSV transformation verified. The stage manifest
records the source URL, release, retrieval time, file hash and attribution.
Scanning 6,467,819 export rows produced 27,033 imported provenance rows, 3,774
distinct occurrences and 2,183 structures across 12 of the 15 audited genera.
Eight primary-eligible genera have chemistry; Desmopsis and Hiraea have missing
coverage. Taxonomy-ambiguous export rows remain in a separate transform review.

ChEMBL 37 retrieval completed for all 2,183 structures, including the additional
332 required to support sensitivity reaggregation. Labels are seven active,
17 inactive and 2,159 unknown, with no retrieval failures. Fifty-one measurements
meet the frozen assay and concentration rules. Unknowns remain outside the
classified denominator. Randia's 12 mapped structures have no classified
activity, so it is excluded.

The primary join contains seven genera: six accepted and one rejected. Both
coverage gates fail. Primary and sensitivity outputs therefore report
feasibility_failure with null effects and P-values; no shortlist or enrichment
figure is generated. R is installed but lme4 is unavailable, recorded explicitly
without a substitute model. The stricter reporting gate and the provenance of
the Saverschek replacement are documented in a dated amendment; neither frozen
file was edited.

The machine-readable funnel preserves the original model branch:
33 retrieved sources, 13 selected, 23 model jobs, 61 candidates, 41 grounding
passes and nine original semantic inclusions. Curator recovery is a separate
96-context branch before taxonomy. README and the pipeline guide now describe
the real outputs and the runnable `scripts.run_pipeline` chain.

All network stages replay from request-hashed raw caches. The complete offline
chain returned zero for every stage, and 109 artifact comparisons across the
upstream replay and final chain were byte-identical. Run-manifest timestamps and
output paths are excluded from byte comparisons; scientific funnel fields match.
The 73 pipeline tests passed, as did scoped Ruff checks. The separate prospective
experiment planner was outside this test run. Both frozen files were compared
byte-for-byte with commit 98b5e09199a5eef0c46be452793e953f5a2af31e and are unchanged.
See results/end_to_end_manifest.json and results/offline_replay.json for evidence.

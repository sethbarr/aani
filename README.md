# aani: learning to listen to millions of years of coevolution

**Before there was artificial intelligence there was animal intelligence.
Here we're raising one to the power of the other.**

When our ancestors got sick, we used herbs to heal ourselves. We learned which
herbs by trial and error, and by watching other animals treat themselves.

Today we face compounding problems:

1. Infectious diseases emerge more often than they used to.
2. Our existing treatments lose ground as pathogens evolve resistance.
3. We are slow to develop new ones.
4. We are losing the biodiversity that might hold the next generation of
   treatments, every day.
5. We can't AI our way out of this. Or can we?

Maybe we need to listen to a different kind of AI. Animal Intelligence.

Wild animals defend themselves against infection, and some do it chemically. If we
re-learn how, we may unlock tools for some of the hardest problems in human and
agricultural medicine. Fungal disease is one of them.

Fungi don't get the attention that viruses like SARS-CoV-2, dengue and HIV do, or
bacteria like tuberculosis and cholera. They are a harder problem than either.
Fungi are close relatives of ours — humans and fungi are far closer to each other
than either is to bacteria — so a compound that kills a fungal infection tends to
harm us too. That shared biology is why we have so few antifungal drugs.

Leafcutter ants farm a fungus and select the plant material they bring to it.
This project asks whether documented rejection provides useful evidence for
antifungal discovery. Plant choice has several causes, so the chemical hypothesis
requires a separate test.

aani makes them computable: papers in, grounded behavioural observations out,
resolved to accepted plant names, joined to chemical structures and measured
antifungal activity, with a source anchor at every link.

**Current status — 14 September 2026.** The primary pipeline executes end to end
with the analysis plan frozen before outcomes were examined. The biological test
remains a feasibility failure: seven usable genera fall below the 25-genus gate,
and only one is in the rejected arm. Two measured limits guide the next work:

1. **Eligible assay coverage is sparse.** Of 2,198 mapped structures, seven have
   active labels, 17 have inactive labels and 2,174 remain unknown under the frozen
   assay criteria for the three selected fungi. These compounds span accepted and
   rejected plant groups and include genus-level chemistry. Unknown activity stays
   outside the classified denominator.
2. **Extraction coverage varies between model draws.** Of 61 original candidate records,
   41 passed automatic grounding, 9 survived source review; these are stage yields.
   The current [behaviour metrics](data/processed/behaviour/metrics.json) record
   96 directional contexts: 6 from model extraction and 90 from curator audit,
   including 87 Saverschek contexts. The [development baseline](results/recall_baseline.md)
   measures the original extractor against one panel from one paper: all six PRIMARY
   species were detected, and two survived grounding with the correct direction.
   V6 retains all six PRIMARY directions in three saved development samples.
   The fresh fourth sample retains two of six because four species were never
   proposed. It does not exceed the baseline's two-of-six survival count. The
   [reader series](#extraction-validity) separates development from held-out results.
   A subsequent [predeclared schema comparison](results/detection_variance/summary.md)
   made 24 calls with frozen v6 and zero retries. All seven complete draws detected
   and retained all six PRIMARY species; the eighth draw returned invalid JSON.
   The comparison cannot distinguish sampling variance from proposal suppression.

The [chemical-distance robustness analysis](results/chemical_distance_robustness/summary.md)
reports 16 predeclared controls and 32,000 random-reference draws. The within-corpus
similarity gap persists after small-structure removal, fingerprint collapse,
size/genus matching, and exclusion of classes linked to Arabidopsis. Matching and
collapse reduce its magnitude. This describes retrieved assay coverage within the
plant corpus; it supplies no antifungal activity prediction or explanation of why
coverage is uneven. The original biological feasibility result remains unchanged.

The prior is old; the proposal to mine it dates to zoopharmacognosy work in the
1990s. What is new is that extracting and joining scattered behavioural
observations to chemical structure is now tractable. Leafcutters are case one
because the behaviour is well documented and the target class is unambiguous. The
method is intended to generalise to any coevolved system where a behaviour implies
a chemical claim.

The public artifact snapshot contains summaries and source-span references.
Publication cleanup on 13 September replaced embedded paper passages, table
strings and request bodies in 23 files with private-file references, block IDs,
UTF-8 byte offsets and hashes. Byte-exact originals remain locally under ignored
`data/interim/publication_safety/originals/`; full text is not redistributed in
these public projections. The [file audit](results/publication_safety/audit.md)
records each change and the [licence inventory](results/publication_safety/licences.json)
records source-specific permissions and uncertainty. Attributed quotations retained
elsewhere have at most 15 words each.

These checks cover the current staged and working snapshot. Earlier Git commits
contain unsanitized reference artifacts; history has not been rewritten. Review
that history before publishing it. The detection experiment and chemical-distance
implementation are committed with their validation tests.

Offline replay requires the prepared inputs and populated cache described in
[the pipeline guide](docs/pipeline.md); a fresh clone alone cannot reproduce the
full run, but it can render the committed results to a PDF (see Quick start below). With those inputs available, run the offline command below with the
explicit Trema taxonomy supplement.

Reader replay against the original reference hashes uses the private mirror:
`.venv/bin/python -m scripts.publication_safety replay`. The
[publication guide](docs/publication_safety.md) explains the public references,
private-byte checks and local replay. Regenerated scientific reports can contain
paper text and must pass publication checks before staging.

The idea has a history: zoopharmacognosy was an established research proposal by
the early 1990s, including Rodriguez and Wrangham's 1993 chapter on medicinal
plant use by animals ([author bibliography](https://kibalechimpanzees.wordpress.com/publications/)).
The contribution proposed here is a reproducible method for extracting scattered
behavioural observations, resolving the organisms they describe, and joining
them to chemistry. Whether enough usable observations exist, and whether their
signal survives that join, are empirical questions.

Leafcutter ants are case one. They provision a cultivated fungus with plant
material. Experiments show that they can learn to reject material harmful to
that fungus ([Herz, Hölldobler & Roces, 2008](https://doi.org/10.1093/beheco/arn016)).
That gives us a specific hypothesis: **plant genera rejected by leafcutters are
enriched for compounds with measured antifungal activity compared with genera
they accept.** Rejection is an imperfect prior: plant nutrients, moisture and
chemistry also influence selection ([Howard, 1990](https://pubmed.ncbi.nlm.nih.gov/28312716/)).

The ecological target is the fungal cultivar. The translational test asks
whether this signal extends to *Candida albicans*, *Cryptococcus neoformans*, and
*Aspergillus fumigatus*. Activity against one fungus does not establish activity
against another. A positive enrichment would justify follow-up experiments;
the deliverable is a prioritisation result, not a drug discovery claim.

## The 72-hour experiment

Build a public-data pipeline linking:

**paper → ant–plant observation → accepted plant name → compound structure → fungal assay**

Every link retains its source. The analysis plan is frozen in a Git commit before
outcomes are examined. Unknown activity stays unknown. Conflicting behavioural
observations and unmatched names remain visible in review tables.

When the prespecified coverage gates pass, the pipeline estimates enrichment
against a permutation null and reports the required clustered models and
sensitivities. Otherwise it returns a coverage funnel and non-estimable status.
The current run does not meet those gates and produces no enrichment claim or
ranked shortlist.

A precise null or negative effect would argue against this prior in the defined
dataset. Sparse coverage or wide uncertainty would leave the hypothesis
unresolved. Neither outcome licenses changing the threshold to manufacture a hit.

The broader method is intended for coevolved systems where a documented behaviour
supports a testable chemical hypothesis. Each new system needs its own mechanism,
comparison group and validation; generalisation is a future test.

## Status and execution

Stages 1-6 have executed. **The primary test is non-estimable at the prespecified
thresholds:** seven joined genera, comprising six accepted and one rejected,
fall below both the 25-genus trigger and the minimum two genera per direction.
Effect estimates and P-values are null. R 4.5.0 and lme4 2.0-6 are available;
the feasibility gate prevents model fitting on the current data.

| Coverage stage | Current result |
| --- | --- |
| Retrieved sources | 33 in this run's corpus lineage: 30 fixed-pilot plus three targeted additions |
| Selected sources | 13: ten formally screened in and three source-following/targeted inclusions |
| Model extraction | 23 jobs; 61 candidates; 41 grounding passes; nine original semantic inclusions |
| Current source-audited evidence | 96 directional contexts before taxonomy; 96 matched contexts; 17 resolved species |
| Genus aggregation | Eleven eligible genera: six accepted, five rejected; five conflicts excluded |
| Verified LOTUS chemistry | Nine eligible genera; Desmopsis and Hiraea have missing chemistry |
| Classified-compound coverage | Seven eligible genera; Randia and Trema have zero classified compounds and are excluded |
| Primary test | Feasibility failure; no inferential statistic computed |

The current [behaviour metrics](data/processed/behaviour/metrics.json) retain
96 contexts: 6 model and 90 curator. The 87 Saverschek contexts include the
seven taxonomy-supplement contexts. Curator recovery replaces incomplete model
summaries and retains separate provenance; contexts share source evidence and
are not independent replicates. The Miconia conflict was verified from tococa/M. microphysca acceptance
and Saverschek M. argentea acceptance and rejection. Trema now resolves to accepted
T. micranthum through a [dated taxonomy supplement](docs/amendment_2026-09-13_trema_taxonomy.md).
Its 26 compounds all have unknown eligible activity. See [the machine-readable funnel](results/funnel.json),
[run report](results/pipeline_report.md), and
[Miconia verification](data/processed/behaviour/miconia_verification.json).

Chemistry uses the complete, checksum-verified LOTUS v4 export, with a documented
local genus filter and CC BY 4.0 attribution. Activity retrieval uses ChEMBL 37
and retains unknowns outside the classified denominator. All 2,198 mapped
structures were queried: seven active, 17 inactive and 2,174 unknown, with zero
retrieval failures. The primary subset contains 1,866 structures; the remainder
supports sensitivity reaggregation. See [export provenance](docs/chemistry_export.md).

### Quick start from a fresh clone

Requires Python 3.12 (`python3.12 --version`). No system packages are needed:
the PDF is rendered with pure-Python ReportLab.

```bash
git clone https://github.com/sethbarr/aani.git
cd aani
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.render_report
```

The PDF appears at `output/pdf/pipeline_report.pdf` and the command prints its
path, page count and SHA-256. It is rendered from the committed
`results/pipeline_report.md`, `results/funnel.json` and `results/summary.json`,
so it works without the private caches. The committed copy of that PDF is
also tracked at the same path for reference. Run the tests with
`.venv/bin/python -m pytest`.

### Full pipeline run

The commands below re-run stages 3-6. They need prepared inputs that are not
tracked by Git (`data/interim/`, `data/raw/`); without them the command exits
with a `prepared_inputs_missing` message and touches nothing. See
[the pipeline guide](docs/pipeline.md) for how to prepare them.

Run stages 3-6 from the prepared, source-audited taxonomy inputs:

```bash
.venv/bin/python -m scripts.run_pipeline --taxonomy-supplement data/interim/trema_resolution/manifest.json
```

Replay with no network requests:

```bash
.venv/bin/python -m scripts.run_pipeline --offline --taxonomy-supplement data/interim/trema_resolution/manifest.json
```

The [frozen analysis plan](docs/analysis_plan.md) and `config/analysis.json` are
unchanged at commit `98b5e09199a5eef0c46be452793e953f5a2af31e`.
The user's stricter reporting gate is documented in a separate
[dated amendment](docs/amendment_2026-09-12_reporting_gate.md).
See [the pipeline guide](docs/pipeline.md) for individual commands and
[the design audit](docs/design_audit.md) for the distinction between observed
cutting, natural acceptability and comparative preference.

Python 3.12; pandas for tables; validated structured JSON for extraction; R/lme4
for the secondary model. API responses are cached under `data/raw/` by request
hash. Each stage also supports replay from cached or explicitly imported data.

### Extraction validity

The Saverschek reader series uses the unchanged baseline convention: detection
counts proposed species or direction pairs, survival counts those with a grounded
record, and correctness matches surviving structured directions to the reference.
PRIMARY contains six stable species-direction pairs. CONTEXT contains five
context-dependent species and ten direction pairs, scored separately. Candidate
stage yield counts surviving records and has its own denominator. A matching
structured direction leaves the underlying biological interpretation subject to
source review.

| Reader | PRIMARY directions retained | Mechanism and sample scope |
| --- | --- | --- |
| [Baseline](results/recall_baseline.md) | 2 of 6 | All six species were proposed; four lacked surviving literal quotes. |
| [v1](results/grounding_development_v1/summary.md) | 0 of 6 | Separate evidence spans still fail chunk-level ant identity; the full name lies outside the producing chunk. |
| [v2](results/grounding_development_v2/summary.md) | 4 of 6 | Source-level ant identity and same-block plant-name support remove identity failures in sample 1. |
| [v3](results/grounding_development_v3/summary.md) | 6 of 6 | Fixed control-to-glyph mappings recover table quotes in saved sample 1. |
| [v4](results/grounding_development_v4/summary.md) | 6 of 6 in samples 1 and 2 | Unique source-span inference resolves model-side control characters; both samples informed the rule. |
| [v5](results/grounding_development_v5/summary.md) | 6 of 6 in samples 1–3 | Bounded printable-character equivalences preserve previous leafcutter survivors. |
| [v6](results/grounding_development_v6/summary.md) | 6 of 6 in samples 1–3; 2 of 6 in fresh sample 4 | Cache-side control inference recovers seven sample-3 records; sample 4 omits four PRIMARY species. |

The [14 September detection experiment](results/detection_variance/summary.md)
compares four new two-span draws against four new single-span draws with identical
source-level ant identity context and frozen v6 validation. Arm A detected six
PRIMARY species in every draw (mean 6; range 6–6), with 85 of 99 candidates
surviving. Three complete Arm B draws also detected six each (mean 6; range 6–6),
with 38 of 55 candidates surviving. B2's table response was invalid JSON and remains
unscorable; no retry or repair was used. No PRIMARY species was omitted in a
complete draw. The ceiling counts and incomplete B arm leave both hypotheses
unresolved. Single-span records remain isolated from biological outputs.

[Held-out sample 3](results/grounding_development_v4/heldout_summary.md)
retained PRIMARY 6 of 6 and CONTEXT 5 of 10 under the frozen v4 rule. Seven records
failed because the model rendered cached U+0002 as an ASCII hyphen U+002D;
this cache-side control case falls outside v4's model-side control recovery.

[V5](results/grounding_development_v5/summary.md) adds bounded printable-character
equivalence after the v4 checks. Across the saved leafcutter and system replays,
it loses zero prior survivors and changes zero directions. It preserves the
leafcutter survivors and the held-out cache-side-control failures; propolis
grounding improves while focal semantic retention remains zero.

[V6](results/grounding_development_v6/summary.md) adds a cache-side route after
exact, v4 and v5 matching. It permits one non-whitespace control character in the
cache to align with one printable punctuation mark or symbol in the quote, with
unique equal-length alignment, exact agreement elsewhere and consistent mappings.
Offsets and code points are logged. Changed digits, letters, direction words and
two differing positions fail the new route. Across samples 1–3, v6 loses zero
previous survivors and changes zero structured directions.

Sample 3's failures informed v6, so samples 1–3 are development evidence for that
rule. [Sample 4](results/grounding_development_v6/heldout_sample4_summary.md) used
the same three request descriptors in a separate cache: three model calls, zero
retries, a frozen rule and scoring before failure inspection. Each sample is
reported separately; proposals are never pooled.

#### PRIMARY under v6 — six pairs

| Stage | Sample 1: development | Sample 2: development | Sample 3: development | Sample 4: held-out draw |
| --- | --- | --- | --- | --- |
| Detection | 6 of 6 | 6 of 6 | 6 of 6 | 2 of 6 |
| Survival | 6 of 6 | 6 of 6 | 6 of 6 | 2 of 6 |
| Correctness | 6 of 6 | 6 of 6 | 6 of 6 | 2 of 6 |

#### CONTEXT under v6 — five species, ten pairs

| Stage | Sample 1: development | Sample 2: development | Sample 3: development | Sample 4: held-out draw |
| --- | --- | --- | --- | --- |
| Detection | 10 of 10 | 9 of 10 | 10 of 10 | 3 of 10 |
| Survival | 10 of 10 | 9 of 10 | 10 of 10 | 3 of 10 |
| Correctness | 10 of 10 | 9 of 10 | 10 of 10 | 3 of 10 |
| Species: both directions / one / absent, at every stage | 5 / 0 / 0 | 4 / 1 / 0 | 5 / 0 / 0 | 1 / 1 / 3 |

All eleven species remain scorable in every sample. Candidate stage yields are
23 of 26, 18 of 18, 20 of 24 and 7 of 13, respectively. Sample 4's six rejections
comprise four identity/name-link failures and two plant-name-surface failures.
All detected reference pairs survive and match; six candidate records fail.
Proposal omissions limit sample-4 reference recall. None of its thirteen proposals
uses the new cache-side route, so v6's cache-side generalisation to an untouched
draw remains untested. All 39 development replay artifacts and all 13 sample-4
replay artifacts match byte for byte.

This is a DEVELOPMENT SET: one panel from one paper, with reference labels known
to the implementers. It is not a sample from any population. The curator matrix
was produced from the same text blocks the extractor read, so shared blind spots
could inflate apparent recall. The curator had the complete cache including
tables; the original extractor worked chunk-wise under a strict quote constraint.
Six species have author-prose reference labels and five have table-derived labels.
The table transcription remains visually unverified against the original PDF,
making those labels weaker ground truth. The [day-two report](results/day2_status.md)
preserves the baseline and provenance split. Unseen-paper performance remains
unmeasured.

Grounding-development recoveries do not enter the primary biological join;
its frozen rules, current counts and feasibility-failure status remain unchanged.

The [exploratory systems](results/systems/summary.md) use adapted schemas and
different source-selection histories; these runs do not isolate biological
transfer. Propolis has two grounded secondary reports and zero retained direct
observations. Attine bacteria recover one of two reference relationships; the
scoped microbial taxonomy rule resolves all five retained records, while chemistry
and activity retrieval remain disabled for that control.

Adding five user-supplied primary PDFs to the monarch corpus recovered infected
and uninfected behaviour missed by the initial 20-source search. The
[seeded rerun](results/systems/monarch_seeded/summary.md) completed with 13 candidates,
nine grounded records, four retained records and two resolved names. Its
[funnel](results/systems/monarch_seeded/funnel.json) records one focal-eligible and
infection-comparison-eligible Asclepias genus, with two infected and two uninfected
records. The retained groups use different target plants: zero complete same-target
infection panels survived extraction. The two infected records include separate
analyses of one experiment and do not count as independent replicates.

The seeded monarch fungal bioactivity join is a **coverage probe**: of 417 mapped compounds, 69 matched ChEMBL, one was classified inactive and 416 remain unknown. One inactive Asclepias compound against the primary fungal panel does not test the monarch-parasite mechanism. The [assay inventory](results/systems/monarch_seeded/funnel.json) contains 16,322 functional assays across the three primary fungi: 11,912 for C. albicans, 2,038 for C. neoformans and 2,372 for A. fumigatus. It confirms 0 assays for Ophryocystis elektroscirrha across all assay types against the complete inventory. Database assay coverage only; inactivity is unmeasured.

The full local test suite passed 1,019 tests during the 13 September review.
Scientific replay and file-preservation checks have separate outcomes: the
[seeded monarch verification](results/systems/monarch_seeded/verification.json)
records 753 passed checks and one failed file-set check because 29 concurrent
files were added. All 277 originally captured files retain their hashes. That
failed check remains disclosed.

## Prospective experimental validation

The hackathon now includes a [diverse-fungus experiment planner](docs/experiment_workflows.md):
an ant cultivar as an ecological reference, four model-fungus comparisons,
source-linked materials, and local handoff drafts for Potato, Emerald Cloud Lab,
and the Gerardo lab. Those partners and sample sources are possibilities, not
confirmed integrations or arrangements.

Run `.venv/bin/python -m scripts.plan_experiments`, then open
[the offline planner](results/experiment_planner/index.html). It exports a
structured study plan, an illustrative plate map, and a water-only OT-2 protocol.
Biological methods remain unassigned and no experiments have been run. This
prospective work is separate from the frozen retrospective analysis.

## Repository

```text
docs/analysis_plan.md       analysis decisions, frozen before outcomes
docs/local_notes.md         how the supplied Obsidian leads enter review
config/analysis.json        machine-readable analysis constants
src/corpus/                 Europe PMC retrieval and XML parsing
src/extraction/             schema, model requests and grounding checks
src/taxonomy/               GBIF name matching and review queue
src/chemistry/              provenance-preserving occurrence imports
src/bioactivity/            ChEMBL retrieval and activity classification
src/analysis/               joins, permutation test, shortlist and R model
data/raw/                  request-hashed source/API/export cache
data/interim/              original extraction, taxonomy and source audits
data/processed/behaviour/  merged observations, genus table and conflicts
data/processed/chemistry/  imported occurrences and export provenance
data/processed/bioactivity/ ChEMBL labels, measurements and retrieval audit
data/processed/analysis/   prepared primary and sensitivity join tables
results/funnel.json        machine-readable coverage and blocked reasons
results/primary/           non-estimable summary, coverage tables and review
results/experimental/      experimental-evidence sensitivity
results/delayed/           delayed-rejection sensitivity
results/nondiscordant/     discordance sensitivity
results/saverschek_audit/  completed text audit and evidence bundle
results/experiment_planner/ prospective planning artifacts
results/business_case/     project business-case artifacts
output/pdf/                 pipeline_report.pdf, rendered by scripts.render_report
scripts/                    one CLI entry point per stage
tests/                      scientific edge cases and offline integration
```

There is no enrichment figure for this run because the feasibility gate fails.

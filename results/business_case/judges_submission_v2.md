# aani: animal intelligence and artificial intelligence

## 1. Short writeup

Before there was artificial intelligence there was animal intelligence. aani connects animal observations to plant names, chemistry and assays. [README][readme]

Of 2,198 mapped structures, 24 have eligible measurements under the frozen assay criteria. Reader development addressed stitched quotes, source identity, supporting evidence and glyph copying. V6 was developed on three samples and tested on one untouched draw, which recovered 2 of 6 PRIMARY directions and never exercised the new cache-side repair. Sample 4 was a held-out test: v6 was frozen before the draw, and scores were saved before any failure was inspected.

The three exploratory systems stopped at different stages for system-specific reasons. The propolis corpus retained no direct behavioural observation. The checked ChEMBL inventory contained zero assays for Ophryocystis elektroscirrha against 16,322 functional assays for the fungal panel. The attine prompt pinned modern Pseudonocardia producer naming while the historical source used Streptomyces. These runs used adapted schemas and different source histories; biological transfer remains untested.

Why now: open LOTUS occurrence exports, programmatic ChEMBL whole-organism assays, GBIF name resolution at scale and structured-output models holding a quote constraint had to exist together.

The pipeline retrieved 33 sources, selected 13, and ran 23 jobs producing 61 candidates, 41 grounded and nine source-reviewed. Curator replacement yielded 96 contexts (6 model, 90 curator; 87 Saverschek), 17 species, 11 eligible genera, nine with chemistry and seven classified. Those seven (six accepted, one rejected) failed gates of 25 genera and two per direction. Inference remains non-estimable. Primary scope contains 1,866 structures. [Pipeline][pipeline] [Funnel][funnel]

The baseline detected six PRIMARY species and retained two. Later runs exposed separate identity, supporting-evidence and glyph-copying problems. PRIMARY directions retained were 0 of 6 under v1, 4 of 6 under v2, 6 of 6 under v3 and 6 of 6 under v4 on samples 1–2. [Reader][reader] [V4][v4] Held-out sample 3 retained PRIMARY 6 of 6 and CONTEXT 5 of 10; cache-side controls caused the losses. [Held-out][heldout] V5 added printable equivalence with zero regressions. [V5][v5] V6 added cache-side inference, lifting sample 3 to CONTEXT 10 of 10 as a development-set result. [V6][v6] Held-out sample 4 under frozen v6 retained PRIMARY 2 of 6 and CONTEXT 3 of 10. All detected reference pairs survived and matched; six other candidate records failed identity or name checks. The model omitted four PRIMARY species, and the candidate stage yield was 7 of 13. [Sample 4][sample4] Proposal omissions limited reference recall in sample 4. This single-paper panel has visually unchecked table semantics. Grounding development records remain outside the primary biological join.

- Propolis v5 grounded both secondary reports; semantic review retained zero direct observations. [Systems][systems]
- Monarch seeding recovered the focal infected-versus-uninfected comparison missed by discovery; the fungal join is a coverage probe, with parasite activity unmeasured. [Seeded][seeded]
- Attine recovered 1 of 2 controls; scoped taxonomy resolved all five records; chemistry stayed disabled. [Taxonomy][microbial]

These runs reused extraction and coverage reporting. Their failures locate the work each new system requires.

The business asset is the reusable platform. R&D teams could pay for shared research workspaces, private deployments and sponsored discovery programmes. Initial applications are leaf cutter ant control in Brazilian forestry and citrus, crop fungicide discovery, and human antifungals after separate validation. Licensable chemistry would add upside; platform revenue could arrive earlier from demonstrated research utility.

Our next milestone is a paid research deployment that measures time, cost and consequential errors against expert review using existing tools. A separate prospective experiment will test whether ecological evidence improves discovery yield. No novel molecule, validated general predictor, customer revenue or prospective hit-rate improvement is claimed from the current runs.

## 2. Spoken pitch — 60 seconds

Spoken figures are rounded; exact counts are in section 1.

Before there was artificial intelligence, there was animal intelligence.
Leafcutters can learn to avoid material harmful to their cultivated
fungus. We are testing whether their choices help prioritise antifungal
chemistry.
aani links papers, plant names, compounds and fungal assays, with traceable sources.
Our frozen biological test stopped at seven usable genera, below its
25-genus gate. Only twenty-four of roughly two thousand two hundred
compounds have an eligible measurement against our three fungi.
The baseline detected six PRIMARY species and retained two. We traced
four separate problems, from stitched quotes to a corrupt cache.
V6 was developed on three samples and had one held-out test. Under v6,
across four draws the validator never lost a detected reference pair,
and detection itself ranged from six of six to two.
The held-out test never exercised the new cache-side repair.
Our next milestone is a paid deployment measuring whether aani saves a
research team time.

## 3. Demonstration links

- [README coverage funnel](../../README.md#status-and-execution)
- [Machine-readable primary funnel][funnel]
- [Primary pipeline report][pipeline]
- [Primary feasibility status](../metrics.json)
- [Grounding development v1](../grounding_development_v1/summary.md), [v2](../grounding_development_v2/summary.md), [v3][reader] and [v4][v4]
- [V4 on held-out sample 3][heldout]
- [V5 printable-confusable development and semantic outcomes][v5]
- [V6 cache-side control development][v6] and [held-out sample 4][sample4]
- [Exploratory systems and their distinct stopping points][systems]
- [Separate attine microbial taxonomy replay][microbial]
- [Seeded monarch follow-up and source-access limits][seeded]
- [Experiment planner](../experiment_planner/index.html), a planning export
- [Frozen analysis plan](../../docs/analysis_plan.md), retained at commit `98b5e09`

The [September 12 reporting amendment][gate] contains counts of 2,183 total structures, 1,851 primary-scope structures and 80 Saverschek contexts, which were correct when written and precede the Trema resolution and v2–v4 recovery series; the [current pipeline report][pipeline] and [funnel][funnel] supply this submission's counts.

The reader series in section 1 runs through held-out sample 4. Sample 4 did not exercise the v6 cache-side route, so that route's generalisation to an untouched draw remains untested. Direction agreement leaves table semantics unadjudicated.

The attine miss reflects a prompt pinned to modern Pseudonocardia while the historical source uses Streptomyces; the [Currie diagnosis](../systems/attine_actino/currie_recovery/summary.md) separates proposal omission from line-break hyphenation. The [systems summary][systems] records the original stopping stages and subsequent grounding, taxonomy and source-access follow-ups.

Eligible assay coverage is 24 of 2,198 mapped structures. Unknown activity stays outside the classified denominator. Model stage yields and curator contexts have different denominators, and contexts can share biological evidence. The exploratory systems used adapted schemas and different corpora and curation histories; their comparison does not isolate biological transfer.

The current staged artifact snapshot contains compact run summaries and source-span references. Publication cleanup replaced paper passages, table strings and embedded request bodies in 23 files with private-file references, block IDs, UTF-8 byte offsets and hashes. Byte-exact originals remain in ignored local storage; paper quotations retained elsewhere have at most 15 words each. The [publication audit](../publication_safety/audit.md) records the file-by-file changes and [licence inventory](../publication_safety/licences.json). Full texts and raw API caches are excluded from the current public projections. Earlier Git commits still contain unsanitized reference artifacts and require separate history review before publication. Offline replay uses the private mirror described in [the publication guide](../../docs/publication_safety.md); a fresh clone alone cannot reproduce the full run.

[readme]: ../../README.md
[pipeline]: ../pipeline_report.md
[funnel]: ../funnel.json
[reader]: ../grounding_development_v3/summary.md
[v4]: ../grounding_development_v4/summary.md
[heldout]: ../grounding_development_v4/heldout_summary.md
[v5]: ../grounding_development_v5/summary.md
[v6]: ../grounding_development_v6/summary.md
[sample4]: ../grounding_development_v6/heldout_sample4_summary.md
[seeded]: ../systems/monarch_seeded/summary.md
[systems]: ../systems/summary.md
[microbial]: ../systems/attine_actino/taxonomy_microbial/summary.md
[gate]: ../../docs/amendment_2026-09-12_reporting_gate.md

## 4. Rubric emphasis

| Category | Weight | What to demonstrate |
| --- | --- | --- |
| Innovation & Creativity | 30% | Animal observations linked to chemistry and assays through source anchors; ecological discovery remains a testable hypothesis. |
| Technical Implementation | 25% | The primary funnel and feasibility gate, separate model and curator yields, reader development and held-out results, and distinct exploratory stopping points. |
| Business Value & Impact | 25% | Proposed research workspaces, private deployments and sponsored programmes; a paid deployment will measure utility for the intended buyers. |
| Presentation & Communication | 20% | The short pitch, inspectable counts, the held-out limitation and clear separation of measured results, derived results and planned work. |

Rubric weights follow the supplied team playbook. The organiser's corrected schedule has three check-ins: midnight Saturday, noon Sunday and midnight Sunday; the final is noon Monday. Placement = final score + average of the three check-in scores.

## 5. Boundaries

Observed results are source-linked extraction yields, curator recoveries and system-specific stopping points. Derived results are coverage fractions and reader direction agreement, with the frozen-protocol feasibility failure reported as a substantive result. Planned work comprises paid utility testing and prospective experiments; no novel molecule, validated predictor, customer revenue or prospective hit-rate improvement is claimed.

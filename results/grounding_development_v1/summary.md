# First multi-span grounding experiment — DEVELOPMENT SET

This experiment reduced grounding survival. All three model jobs completed;
seven candidates were proposed and zero survived. The model returned no
table-based observations. This is one panel from one paper and is not a sample
from any population. All 11 species remain in their original groups.

| Stage | PRIMARY baseline | PRIMARY first experiment | CONTEXT baseline: both / one / absent | CONTEXT first experiment: both / one / absent |
| --- | --- | --- | --- | --- |
| Detection | 6 of 6 | 2 of 6 | 0 / 4 / 1 of 5 | 1 / 1 / 3 of 5 |
| Survival | 2 of 6 | 0 of 6 | 0 / 1 / 4 of 5 | 0 / 0 / 5 of 5 |
| Correctness | 2 of 6 | 0 of 6 | 0 / 1 / 4 of 5 | 0 / 0 / 5 of 5 |

CONTEXT direction-pair counts were 4 of 10 detected and 1 of 10 surviving/correct
in the baseline; the experiment detected 3 of 10 and retained 0 of 10. Hymenaea
had both directions proposed; Miconia had acceptance proposed. The reference
provenance remains six author_prose and five author_table_grouping species: PRIMARY two
and four, CONTEXT four and one. Directions were checked against Table 1 of the
original PDF and follow the authors' printed headings, so these are
author-assigned groupings rather than inferences from numerical signs. What
remains unverified is the semantic support for individual rows and captions.

Six first-run records failed `ant_requires_review`. Every candidate used
`A. colombica`, and the producing chunk lacks its full name. One Hymenaea
record failed `name_surface_not_in_quote`: its primary quote uses “it,” while
the declared plant name occurs in a supporting span. These are ordered first
failure reasons; the latter candidate also has the abbreviated ant name.

Review also found a full-name validator defect for `S. lindenianum`. The corrected
validator rejects that abbreviated full-name anchor during a separate cached
replay. Its rejection reason changes; the stage counts stay unchanged. The
first-run responses and outputs remain intact. No additional model sample was
requested to improve this result.

Correctness is zero because there are no surviving records to review. The saved
baseline used structured-direction matching, while the new evaluation requires
semantic review for any survivors. That review-depth difference limits direct
correctness comparisons. Detection and survival retain the same definitions.

The curator matrix was produced by reading the same text blocks the extractor
read, so shared blind spots would inflate apparent recall. The curator had
complete cached text including tables; the original extractor worked chunk-wise
under a strict quote constraint. The implementers also knew this reference
during development. This run cannot estimate generalization to other papers.

The debugging review identified the chunk-local ant-name blocker and the
full-name check defect. Data-validation checks retained all denominators,
separated proposed directions from surviving correctness, and checked source
and baseline integrity. Assessment: share with these caveats as a failed
development experiment. Next work is source-anchored ant identity across chunks,
table coverage and primary-quote context; the default extractor is unchanged.

The biological analysis remains a feasibility failure. No new extraction record
entered the join, and frozen protocol files, assay eligibility, activity unknowns,
unanimity and the 25-genus gate are unchanged.

Verification passed 26 exact artifact comparisons across the default-mode replay,
first experimental replay and hardened replay. The hardened rejection file has
only the expected reason change described above. Scoped Ruff checks passed.
The test suite finished with 142 passing tests and one pre-existing failure:
the experiment planner cannot find `src/experiments/viewer.template.html`.
That unrelated failure remains open.

See the [full count comparison](compare.md), [machine-readable comparison](compare.json),
[verification](verification.json), and
[dated amendment and commands](../../docs/amendment_2026-09-13_multispan_development.md).

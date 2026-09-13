# Dated reporting amendment: end-to-end coverage run

Date: 2026-09-12. Project: aani.

The user explicitly requested an end-to-end run and required the primary test
to remain uncomputed if fewer than 25 joined genera, or fewer than two genera
in either direction, survive the prespecified chemistry/activity join. This is
a stricter reporting gate than version 1's allowance to calculate exploratory
statistics below the feasibility threshold.

The implementation will emit `status: feasibility_failure`, `estimable: false`
and null inferential endpoints when either gate fails. It will retain actual
coverage counts and exclusions. Descriptive counts are not substituted for the
primary endpoint. The within-family sensitivity and mixed-effects availability
will remain explicit; no unclustered substitute is permitted.

This amendment was written before any LOTUS occurrence/bioactivity join or
antifungal outcome inspection in this run. It changes reporting, not the 10 uM
threshold, assay filters, genus unanimity rule, missingness treatment, frozen
25-genus trigger, or biological estimand. `docs/analysis_plan.md` and
`config/analysis.json` remain byte-identical to commit
`98b5e09199a5eef0c46be452793e953f5a2af31e`.

## Input reconciliation

The three requested taxonomy directories contain 6 pilot, 3 recovered and
3 early Saverschek rows. That early Saverschek table does not contain Miconia
argentea. The completed text audit at `results/saverschek_audit/` contains
80 taxonomy-matched directional contexts, including its accepted and rejected
observations. The end-to-end merge explicitly replaces the three coarse
Saverschek rows with that audited set. It does not append duplicate rows or
erase contrary directions that the original extraction missed.

The merged observations retain their original model/curator provenance, exact
source anchors, habitat/day/design context and input hashes. Deduplication acts
within source and genus on identical grounded observations; distinct contexts
remain distinguishable. All retained directions determine the genus label;
Miconia must be excluded as a conflict across both its within-study and
cross-study evidence. Curator context counts are not model-candidate counts or
independent biological sample sizes.

Corpus retrieval, screening and model-extraction counts will be reported by
cohort in `results/funnel.json`, with the source-following and curator recovery
branches identified separately. A targeted extension is not relabelled as part
of the original fixed 30-paper feasibility sample.

## Retrieval scope for sensitivity completeness

The initial ChEMBL run covered 1,851 structures mapped to primary-eligible
genera. During the required sensitivity check, removing immediate rejection
reclassified Miconia as accepted in the delayed subset. That subset therefore
needs chemistry/activity coverage beyond the primary genus set.

Retrieval was extended to all 2,183 structures in the already imported,
behaviour-selected LOTUS subset: 332 additional structures. This decision was
made to complete every prespecified reaggregation, not by activity label or
statistical result. The initial primary-scope run is retained separately. All
five conflicting genera remain excluded from primary inference; activity
retrieval does not confer behavioural eligibility. Primary and full-retrieval
structure counts are reported separately. No primary statistic is estimable
at this sample size, and no model or threshold was changed.

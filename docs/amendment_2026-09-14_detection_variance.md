# Detection variance experiment predeclaration

Declared on 2026-09-14 before any new model request. Task start: 2026-09-14
12:14:26 UTC; hard deadline: 2026-09-14 14:14:26 UTC. The declaration commit
hash and Git timestamp will be recorded in results/detection_variance/provenance.json
before sampling. Existing samples 1–4 are background observations and are excluded
from the eight new draws.

## Arms and fixed inputs

- Arm A: four independent draws, A1–A4, of the three complete Saverschek jobs
  using the current multispan_v2 prompt and schema, including source-level ant
  identity context. This is the existing two-span configuration, which also
  permits supporting evidence spans.
- Arm B: four independent draws, B1–B4, of the same three jobs with a single-span
  response contract. Remove name_evidence and supporting_evidence from the response
  schema. Keep all other fields and constraints, including name_surface_form and
  name_link. Change only prompt instructions about evidence multiplicity and the
  removed fields: request one contiguous primary evidence_quote, permit the full
  name to be read elsewhere in the supplied blocks, and express the existing
  direction/context and table-interpretation rules using that one span. Retain the
  exact source-level identity suffix and every unrelated instruction.
- Both arms use Gemini gemini-3.8-flash through the existing stateless Interactions
  request function, store=false, max_output_tokens=32768, thinking_level=low,
  thinking_summaries=none, and the same unspecified temperature/seed defaults.
  Corpus bytes, title, source IDs, block boundaries/order, identity context, and
  non-evidence schema fields are identical across arms. No reference labels or
  target species list are added to either prompt.
- There are 24 planned model calls: three per draw, four draws per arm. Each draw
  has its own fresh cache; no response reuse, conversational state, or resampling.
  Execute A1, A2, A3, A4, B1, B2, B3, B4, with chunk order 0, 1, 2. This prioritizes
  completion of Arm A within the time box. Arm order is a limitation if provider
  behavior changes during the run.

## Frozen validation and isolation

Use the existing v6 validator and policy without modifying any grounding,
identity, confidence, or lexical gate; minimum_confidence remains 0.8. Hash the
validator, its dependencies, scorer, reference, corpus, and exact prepared jobs
before sampling and verify them after sampling and scoring. Compare the v6 rule
files with their previously recorded v6 hashes. Keep docs/analysis_plan.md and
config/analysis.json byte-identical to commit 98b5e09.

For Arm B only, an external mechanical adapter copies block_id, section, and
evidence_quote into name_evidence and sets supporting_evidence to an empty list
before calling v6. It adds no source text, inference, lookup, or reconstructed
span. The original response is preserved. Thus a B proposal whose sole quote
lacks the full name can fail the unchanged name-evidence gate. Report that survival
cost explicitly. This is a response-format adapter, with identical v6 validation
in both arms. Do not repair any candidate or use the reference to fill fields.

All experiment records and caches stay in dedicated detection_variance paths.
Arm B records must never enter primary or exploratory biological outputs. Only
reader measurement artifacts and count summaries are produced; no biological
pipeline is run.

## Outcomes and analysis

The primary comparison is the PRIMARY detection count per complete draw, from
zero to six exact reference species, under the saved recall baseline convention.
Detection is candidate presence before grounding, regardless of correctness.
Survival is at least one v6-passing candidate for that species. Correctness is a
surviving structured species/outcome match to the fixed reference; quoted words
alone add no outcomes. Use the existing score_species and summarise_group functions.
Also retain reference-pair counts and every candidate's pass/failure reason.

Report all eight draws with PRIMARY detection, survival and correctness (each
out of six), total proposed candidates and total candidate passes/failures.
For each arm report the four detection counts, mean and range, omissions for each
PRIMARY species and their frequencies, and total proposed candidates. Report
survival means/ranges and candidate yields so an increase in detection accompanied
by reduced survival is visible. Candidate totals include proposals outside PRIMARY.
Each draw is the comparison unit. Pooling candidates does not increase the sample
count. Compute descriptive counts, means and ranges only; no statistical test,
p-value, confidence interval, or population effect claim.

The following descriptive interpretation rules are fixed before drawing:

- Support H2 (proposal suppression) if all four B detection counts exceed all
  four A detection counts: min(B) > max(A). This is a consistent directional
  pattern at this sample size; any survival loss remains part of the finding.
- Support H1 (sampling variance) if A has a detection range of at least two
  species, the arm detection ranges overlap, and the absolute difference in
  detection means is at most 0.5 species. This directly reproduces variable
  reading with comparable arm averages. It does not exclude a smaller schema effect.
- Otherwise state that the data cannot distinguish H1 and H2 at n=4 per arm.
  Equal ceiling counts, a smaller or overlapping B advantage, a B disadvantage,
  and incomplete arms all fall in this category. Neither rule is a statistical
  test. H1 and H2 can coexist; these criteria describe which visible pattern is
  supported in this development experiment.

## Stopping and missingness

Stop after the 24 predeclared calls or at 14:14:26 UTC, whichever occurs first.
Make one transport attempt per job, disable HTTP retries, and record every attempt,
HTTP failure, timeout and any unexpected transport retry. Never replace a failed
or low-yield response. Save results incrementally. A failed or unattempted job
makes its draw incomplete; identify the job and reason and report partial candidate
counts separately, with full-draw scores unavailable. Do not count missing draws
as zero or include them in complete-draw means. A structural integrity failure
also stops affected work and is reported. There is no outcome-dependent stopping.
If B is incomplete, report Arm A alone as the complete-arm result and name each
missing B draw; retain every available B observation with its completeness status.

This is a development set: one paper, one panel, and implementers know the
reference. The table-derived labels retain the baseline's unverified numerical
transcription caveat. The experiment measures the reader on this source and
cannot establish general extraction performance.

# Source-level ant identity — September 13, 2026

This dated development amendment adds an optional `multispan_v2` extraction
mode. The baseline and first multi-span experiment remain intact. The biological
analysis plan and configuration remain frozen at
`98b5e09199a5eef0c46be452793e953f5a2af31e`; thresholds, unanimity, assay eligibility,
activity unknowns and the 25-genus trigger are unchanged.

## Changes under test

Resolve ant identity once per source before constructing model requests. Use an
explicit source override, explicit corpus metadata, the abstract, or the first
block that supplies an unambiguous full binomial. Record the method, source
hash, source block and exact name anchor. Ambiguity or unavailable evidence has
an explicit `blocked_reason`. Overrides require a full name and justification;
an override with a source quote must match the declared source block.

Carry the same resolution into every source job. The model receives the
unchanged v1 prompt followed by the source identity and a short instruction
explaining its cross-chunk scope. This context supplies ant identity only;
behavioural and plant evidence still comes from the job's original blocks.
Saverschek contains `Atta colombica` in block `b00000`, outside the results job.

Records retain their emitted ant-name field and add resolved identity metadata.
The ant-name check accepts a full binomial in a grounded quote or a name matching
the resolved source identity. Metadata distinguishes a full quoted name, a
source-linked abbreviation and a full name matched to source context. It records
the span or source anchor used. A conflicting epithet remains unresolved.

The plant-name surface check also accepts a grounded supporting span from the
primary quote's own block. This permits a primary quote containing a pronoun
when its same-block support supplies the declared name. The output records
which supporting span satisfied the check. Other-block name links do not qualify
for this exception.

The v1 multi-span schema, required evidence/name spans, table instructions and
chunk boundaries remain unchanged. The prior full-name-anchor correction stays
in place. V2 makes no table-extraction change and makes no prompt change beyond
the source-identity context.

## Measurement and attribution

Run the three Saverschek jobs once with Gemini 3.8 Flash, the existing low-thinking
setting and 32,768-token output cap. Preserve that run, including failures, with
its request hashes. Do not draw additional model samples to improve the result.
Separately apply the v2 checks to the seven saved v1 candidates as a deterministic
diagnostic; these counts are explicitly separate from the fresh v2 model run.

Score baseline, v1 and v2 with the original baseline functions and unchanged
reference labels. Correctness is a surviving structured direction matching the
reference. The v1 semantic-adjudication reporting gate does not apply to this
comparison. PRIMARY retains six species/pairs; CONTEXT retains five species and
ten direction pairs, with both / collapsed / absent counts at each stage.
Incomplete runs remain explicitly blocked, with all 11 species retained.

This DEVELOPMENT SET is one panel from one paper, is not a sample from any
population, and its reference is known to the implementers. The curator and
extractor share cached source text, so shared blind spots can inflate apparent
recall. The curator saw the complete text including tables; the extractor uses
chunks and exact spans. Table-derived reference labels remain weaker because
the table transcription was never visually verified against the PDF.

If PRIMARY detection remains below six of six, inspect missing species against
the supplied blocks and the unchanged two-span requirements. One model sample
per variant cannot isolate a schema effect from prompt effects or sampling
variation. Record evidence of suppressed proposals and its uncertainty without
reverting to the single-span mode.

## Execution and replay

Prepared source text and the local cache are required. Source overrides, if used,
are a JSON mapping from source ID to an object with `scientific_name`, `reason`
and optional exact `block_id` / `evidence_quote`, supplied through
`--ant-identity-overrides PATH`. This Saverschek run uses the source itself.

```bash
.venv/bin/python -m scripts.extract --provider gemini --model gemini-3.8-flash --grounding multispan_v2 --corpus data/interim/corpus_targeted_saverschek --output data/interim/extraction_saverschek_multispan_v2
.venv/bin/python -m scripts.compare_grounding_v2
.venv/bin/python -m scripts.verify_grounding_v2
```

The verification command replays all three variants offline into separate
directories. V1 replay uses its already-hardened checker: its response bytes and
stage counts match the first run, with the previously documented change to the
`S. lindenianum` rejection reason. No prior artifact is overwritten. None of the
new records enters the biological join.

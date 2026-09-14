# 2026-09-13 — printable-confusable grounding

V5 extends source-anchored grounding to four narrowly defined printable-character classes. A saved propolis proposal emitted U+2011 NON-BREAKING HYPHEN where the cached source contains U+2010 HYPHEN. V4 correctly rejects that printable substitution. This amendment adds the explicit `multispan_v5` mode and preserves every earlier validator, including `multispan_v4`.

The analysis plan and analysis configuration remain frozen at `98b5e09199a5eef0c46be452793e953f5a2af31e`. Extraction confidence, unanimity, assay eligibility, activity labels, and the 25-genus feasibility gate are unchanged. This experiment does not change the biological join or its feasibility-failure label.

## Permitted equivalence classes

Printable-confusable inference is limited to substitutions within one of these classes:

- Hyphen and dash: U+002D HYPHEN-MINUS, U+2010 HYPHEN, U+2011 NON-BREAKING HYPHEN, U+2012 FIGURE DASH, U+2013 EN DASH, U+2014 EM DASH, and U+2212 MINUS SIGN.
- Single quotation marks: U+0027 APOSTROPHE, U+2018 LEFT SINGLE QUOTATION MARK, and U+2019 RIGHT SINGLE QUOTATION MARK.
- Double quotation marks: U+0022 QUOTATION MARK, U+201C LEFT DOUBLE QUOTATION MARK, and U+201D RIGHT DOUBLE QUOTATION MARK.
- Spaces: U+0020 SPACE and U+00A0 NO-BREAK SPACE.

No character outside these four classes is equivalent. Digits, letters, other signs, and direction words receive no printable-confusable treatment. A substitution is permitted only when the emitted and cached characters are distinct members of the same listed class.

## Ordered comparison rule

1. Apply the existing whitespace-normalized exact substring comparison first. Exact matches keep the existing first-occurrence behavior.
2. If exact comparison fails, apply the complete v4 control-glyph inference rule. The permitted model characters remain non-whitespace C0 controls, and the permitted cached targets remain exactly ± and ¼.
3. If v4 control-glyph inference fails, consider printable-confusable alignments. Each candidate alignment must have the same normalized length as the emitted quote. Every mismatch must be a substitution within one permitted printable equivalence class, and every other character must agree exactly.
4. Require literal printable context on both sides of every substituted run under the v4 anchor rule. Require one unique acceptable source alignment. Reject inserted or deleted text, conflicting inferred mappings, ambiguous alignments, and changes outside the listed classes.
5. Keep mappings candidate-local. The same emitted character cannot map to different cached characters within one quote or across a record's spans. Mappings never carry into another record or response.
6. Log every substitution with its emitted and cached characters, Unicode code points, emitted normalized offset, and raw cached-source offset. Also retain the block hash, raw emitted quote, matched cached quote, and source span coordinates.
7. Run the unchanged v2 span, source-identity, plant-name, section, and confidence checks using a temporary copy of matched source quotes. Preserve original model quotes and record digests in emitted records.

V5 has no paper, source, or block exception. Each job binds its declared source ID and exact block text hashes before its input hash is calculated. These bindings establish provenance for cached text; they do not verify the cache against a PDF.

## Scope and measurement

Prompt, extraction schema, required spans, source-identity context, chunks, provider request bodies, and saved proposals remain unchanged. The v5 policy and source hashes are local validator metadata. The default extraction mode and the v1 through v4 modes remain unchanged.

All evaluations use saved response artifacts in offline mode with zero model calls. Leafcutter samples 1, 2, and 3, when present, are replayed independently. V5 must retain every v4 survivor and preserve every previously assigned direction. Propolis, monarch, and attine proposals are audited as separate saved proposal sets. A grounding pass advances a candidate to semantic review and does not establish semantic retention.

Synthetic checks cover each permitted printable class and adversarial nearby changes. They include a changed digit next to a permitted hyphen substitution, a changed word in a quote containing a smart-quote substitution, and a changed direction word in text containing an NBSP substitution. Each adversarial case must reject because every other character must agree exactly.

This is a DEVELOPMENT SET. The observed propolis failure informed the printable-confusable policy, so propolis is not an independent test of v5. The saved leafcutter, monarch, and attine proposal sets are also development artifacts. Synthetic probes test implementation scope and do not estimate performance on unseen papers or model runs.

The curator and extractor may share cached-source blind spots. Curators can see complete cached documents while extraction operates chunk-wise under strict quote constraints. Table-derived reference labels retain the warning that the transcription was never visually checked against the PDF. Structured-direction agreement does not adjudicate semantic support in table rows or captions.

## Reproduction and audit

The v5 results directory records protected-file checks, proposal identity, offline replay, candidate-level deltas, substitution evidence, synthetic expectations, and test status. Reproduction commands and exact artifact paths are listed in `results/grounding_development_v5/summary.md` after the implementation and saved-data inventory have been verified.

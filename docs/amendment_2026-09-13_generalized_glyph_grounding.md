# 2026-09-13 — source-anchored control-glyph grounding

V4 generalizes the model-side control codes that can stand in for cached ± and ¼. The two saved samples used different codes for those same source glyphs. This amendment introduces the explicit `multispan_v4` mode and leaves all earlier validators and experiment artifacts intact.

The analysis plan and analysis configuration remain frozen at `98b5e09199a5eef0c46be452793e953f5a2af31e`. Extraction confidence, unanimity, assay eligibility, activity labels, and the 25-genus feasibility gate are unchanged. This experiment does not change the biological join or its feasibility-failure label.

## Comparison rule

1. Apply the existing whitespace-normalized exact substring comparison first. Literal control characters already present in the source retain their exact interpretation.
2. If exact comparison fails, consider equal-length alignments within the candidate's declared block. Every mismatch must pair a non-whitespace C0 model character with cached ± or ¼. Every other character must agree exactly. Printable substitutions, inserted or deleted text, and changes to digits, signs, names, or direction words fail.
3. Require literal printable context on both sides of every control-character run, ignoring intervening controls and whitespace. Reject leading or trailing unanchored runs.
4. Require one unique acceptable source alignment. Reject inconsistent inferred mappings where the same emitted control corresponds to different cached glyphs within a quote or across a record's spans. A mapping never carries into another record or response.
5. Run the unchanged v2 span, source identity, plant-name, section, and confidence checks using a temporary copy of the matched source quotes. Preserve original model quotes and record digests in the emitted record.

The source-glyph whitelist is exactly ± and ¼. C0 means code points U+0000 through U+001F; code points treated as whitespace by the existing Python whitespace rule are excluded from substitution. Other Unicode and OCR errors remain outside this rule. The fixed policy is in `config/grounding_glyphs_v4.json`.

V4 has no hard-coded paper or block identifier. Each job binds its declared source ID and exact block text hashes before its input hash is calculated. The fallback checks that binding, and every matched span records the block hash, raw source coordinates, emitted quote, cached quote, inferred mapping, and per-position code points. These bindings provide provenance; they do not verify that PDF text was transcribed correctly.

## Scope and measurement

Prompt, extraction schema, required spans, source identity context, chunks, and provider request bodies remain unchanged. The new policy and block hashes are local validator metadata. Baseline and v1 through v3 job hashes remain reproducible. The default extraction mode is unchanged.

Both saved samples are processed offline using their original separate response caches. No fresh model sample is requested. Each sample's v3 and v4 outputs are scored separately with the baseline structured-direction convention, with PRIMARY six pairs and CONTEXT five species/ten pairs. Missing proposals remain missing. Recoveries and lost survivors are both reported; records are never selected or pooled across samples.

This is a DEVELOPMENT SET: one panel, one paper, and implementers know the reference. Both model samples informed this rule, so neither is an independent test of v4. Synthetic probes include controls not previously observed replacing these two glyphs, alongside adversarial cases, to check the algorithm's scope and rejection behavior. Those probes do not establish performance on unseen papers or model runs.

The curator and extractor shared cached source text, so shared blind spots would inflate apparent recall. The curator saw the complete cached text including tables; the extractor worked chunk-wise under strict quote constraints. Table-derived reference labels retain the warning that the transcription was never visually checked against the PDF. Structured-direction agreement leaves semantic support of table rows and captions unadjudicated.

## Reproduction and audit

The recorded experiment uses these scripts:

```shell
.venv/bin/python -m scripts.verify_grounding_v4 --capture-inputs
.venv/bin/python -m scripts.verify_grounding_v4
.venv/bin/python -m scripts.check_glyph_generalization
.venv/bin/python -m scripts.report_grounding_v4
```

The capture and execution scripts refuse to overwrite prior snapshots or outputs. Each saved sample has a distinct fresh v4 output directory and an additional offline replay. `results/grounding_development_v4/verification.json` records original-file preservation, frozen-file checks, identical requests/proposals, and scientific output byte comparisons. `generalization_checks.json` records every synthetic case and its expected and actual result.

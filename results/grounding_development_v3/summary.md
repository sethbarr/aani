# V3 glyph-only grounding — DEVELOPMENT SET

V3 reaches PRIMARY 6 of 6 at detection, survival, and correctness. It recovers all 13 glyph-blocked records in the original 26-candidate v2 sample; the stage yield rises from 10 of 26 to 23 of 26. This reruns the three saved jobs through the v3 validator offline, with identical request hashes and raw proposals. No new v3 model sample was drawn.

## Four-variant comparison

Correctness uses the unchanged baseline structured-direction convention. PRIMARY has six species-direction pairs; CONTEXT has five species and ten direction pairs. Zero species are unscorable in these completed runs.

### PRIMARY

| baseline | v1 | v2 | v3 |
| --- | --- | --- | --- |
| Detection: 6 of 6 | Detection: 2 of 6 | Detection: 6 of 6 | Detection: 6 of 6 |
| Survival: 2 of 6 | Survival: 0 of 6 | Survival: 4 of 6 | Survival: 6 of 6 |
| Correctness: 2 of 6 | Correctness: 0 of 6 | Correctness: 4 of 6 | Correctness: 6 of 6 |

### CONTEXT

Each cell lists **both directions / collapsed to one / absent**, followed by surfaced species-direction pairs. The three species counts always sum to five.

| baseline | v1 | v2 | v3 |
| --- | --- | --- | --- |
| Detection: 0 / 4 / 1; 4 of 10 pairs | Detection: 1 / 1 / 3; 3 of 10 pairs | Detection: 5 / 0 / 0; 10 of 10 pairs | Detection: 5 / 0 / 0; 10 of 10 pairs |
| Survival: 0 / 1 / 4; 1 of 10 pairs | Survival: 0 / 0 / 5; 0 of 10 pairs | Survival: 1 / 1 / 3; 3 of 10 pairs | Survival: 5 / 0 / 0; 10 of 10 pairs |
| Correctness: 0 / 1 / 4; 1 of 10 pairs | Correctness: 0 / 0 / 5; 0 of 10 pairs | Correctness: 1 / 1 / 3; 3 of 10 pairs | Correctness: 5 / 0 / 0; 10 of 10 pairs |

## Byte diagnosis and change

The substitutions occur in saved API model-output response bytes. All nine source blocks survive job export and decoded request JSON exactly. The request input retains literal JSON escapes `\u00b1` and `\u00bc`; the response introduces `\u0001` and `\u0003` at the affected positions. For the middle job, the saved request descriptor shows the original caption at byte 22131 and row at byte 23318; raw response bytes show affected caption and row text at bytes 2134 and 6094. [Byte forensics](byte_forensics.json) records hashes and each mismatch. Actual outbound wire bytes were not captured: request-side evidence is the saved descriptor plus an explicitly labeled HTTPX serialization reconstruction.

Between v2 and v3, only quote comparison changes: a hash-pinned Saverschek table-block policy permits the two observed one-way equivalences, U+0001→± and U+0003→¼, after exact comparison fails.

Fallback requires a unique alignment and exact agreement on every other character. Existing source controls remain literal. Prompt, schema, two-span requirements, chunks, identity context, raw quotes, and raw record digests are unchanged. Every candidate has a comparison audit; every surviving span records its source offsets, emitted quote, source quote, route, and substituted code points.

## Records recovered through the glyph route

All 13 newly surviving records use `bounded_glyph_equivalence` in block `b00005`:

- Spondias mombin accepted and Hiraea grandifolia rejected: one caption substitution each, U+0003→¼, in supporting spans.
- Hymenaea courbaril: one accepted and one rejected record, each with U+0001→± in a supporting table row.
- Inga goldmanii, Tetragastris panamensis, and Trichilia tuberculata: each has one accepted and two rejected records recovered through U+0001→±. Each genus has one repaired primary row quote and two repaired supporting spans.

This accounts for 28 ± substitutions across eleven records and two ¼ substitutions across two records. [Machine-readable comparison](compare.json) identifies each record and span. The local `data/interim/extraction_saverschek_multispan_v3/glyph_grounding_audit.jsonl` ledger covers all 26 candidates, including rejections.

## Remaining limit and repeat sample

No reference pair is missing in this fixed sample; the dominant remaining rejection is `unabbreviated_genus_required` for two outside-panel `S. lindenianum` records, alongside one outside-panel `name_surface_not_in_quote` rejection.

The independently sampled v2 repeat completed all three requests with one attempt each, using identical request descriptors and a separate HTTP cache. PRIMARY detection again reaches 6 of 6; survival and correctness are each 1 of 6. Its stage yield is 6 of 18 candidates. CONTEXT detection is 4 / 1 / 0, with 9 of 10 pairs; survival and correctness are each 1 / 1 / 3, with 3 of 10 pairs. The repeat stays separate from the main comparison; [repeat provenance](repeat_status.json) records its cache paths and distinct response-byte hashes. Detection varies across the full experiment series, and the repeat confirms 6 of 6 only for these two v2 samples.

## Limits and verification

This DEVELOPMENT SET is one panel from one paper, implementers know the reference, and it is not a sample from any population. The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had complete cached text including tables; the extractor worked chunk-wise under a strict quote constraint.

Reference provenance remains PRIMARY: 2 author_prose and 4 table_derived; CONTEXT: 4 author_prose and 1 table_derived. The table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. Structured-direction agreement leaves semantic support of table rows and captions unadjudicated. Generalization remains unmeasured.

Offline replay passed for v3 and the separate v2 repeat. All 108 protected files and both files frozen at `98b5e09` are unchanged; [verification](verification.json) contains byte comparisons. The biological feasibility-failure label and its counts are unchanged. Scoped lint passed. The full test suite has 300 passing tests and one pre-existing failure from missing `src/experiments/viewer.template.html`.

Blocked reason: none for this grounding experiment.

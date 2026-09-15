# V6 sample 4 — held-out model draw

V6 adds cache-side control inference after exact, v4, and v5 quote matching. The new route permits one cached non-whitespace C0 control aligned to one printable punctuation or symbol, with unique equal-length alignment, literal anchors, exact agreement elsewhere, and candidate-local consistency.

This is one panel from one paper; implementers know the reference. It is not a sample from any population. The curator matrix used the same text blocks as the extractor, so shared blind spots would inflate apparent recall. The curator had the complete cache including tables; the original extractor worked chunk-wise under a strict quote constraint.

Samples 1–3 are DEVELOPMENT-SET evidence for v6; sample 3's failures informed the cache-side rule. Sample 4, if drawn, is a held-out model draw under the frozen rule. It measures a fresh draw of the same requests; unseen-paper performance remains untested. Every sample is separate and no proposals are pooled.

All counts use the unchanged baseline structured-direction convention. PRIMARY and CONTEXT remain separate, with fixed denominators and explicit unscorable species.

## PRIMARY — six pairs

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 | Sample 4: v6 (held out) |
| --- | --- | --- | --- | --- |
| Detection | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 2 of 6 species; 2 of 6 pairs |
| Survival | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 2 of 6 species; 2 of 6 pairs |
| Correctness | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 2 of 6 species; 2 of 6 pairs |
| Unscorable species | 0 | 0 | 0 | 0 |

## CONTEXT — five species, ten pairs

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 | Sample 4: v6 (held out) |
| --- | --- | --- | --- | --- |
| Detection | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |
| Survival | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |
| Correctness | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |
| Unscorable species | 0 | 0 | 0 | 0 |

## Candidate stage yield

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 | Sample 4: v6 (held out) |
| --- | --- | --- | --- | --- |
| Grounding survivors | 23 of 26 | 18 of 18 | 20 of 24 | 7 of 13 |

## Regression on development samples

Sample 3 is DEVELOPMENT-SET evidence because its failures informed v6.

| Sample | Previous rules | Survivor retention | Lost | Direction changes |
| --- | --- | --- | --- | --- |
| sample1_v6 | v4 | 23 of 23 | 0 | 0 |
| sample1_v6 | v5 | 23 of 23 | 0 | 0 |
| sample2_v6 | v4 | 18 of 18 | 0 | 0 |
| sample2_v6 | v5 | 18 of 18 | 0 | 0 |
| sample3_v6 | v4 | 13 of 13 | 0 | 0 |
| sample3_v6 | v5 | 13 of 13 | 0 | 0 |

## Held-out procedure

Sampling status: complete; network attempts: 3; retries: 0. Scores were saved at 2026-09-13T19:29:02.782336+00:00 before the failure audit. The pre-draw rule and request hashes are in [heldout_sample4_protocol.json](heldout_sample4_protocol.json).

## Sample 4 ordered rejections

| First ordered reason | Records |
| --- | --- |
| `ant_identity_mismatch` | 1 |
| `invalid_genus_reference_link` | 1 |
| `name_surface_not_in_quote` | 2 |
| `unabbreviated_genus_required` | 2 |

These are the first failed gates; later checks remain unadjudicated.

| Rejection class | Records |
| --- | --- |
| identity | 4 |
| name_surface | 2 |
| other | 0 |
| printable_substitution | 0 |
| unresolved_cache_control | 0 |
| unresolved_model_control | 0 |

Per-record reasons, offsets, and any observed unsupported character substitutions are recorded in [heldout_sample4_failures.json](heldout_sample4_failures.json).

## Generalization verdict

Sample 4 leaves v6’s cache-side generalisation untested because none of its 13 proposals exercised the new route; proposal omissions limited PRIMARY to 2 of 6 and CONTEXT to 3 of 10.

## Replay and scope

Offline replay and preservation status: passed.

Directions were checked against Table 1 of the original PDF and follow the authors' printed headings, so these are author-assigned groupings rather than inferences from numerical signs. What remains unverified is the semantic support for individual rows and captions. Reference labels are unchanged.

The frozen protocol files remain at `98b5e09`; thresholds, unanimity, assay eligibility, unknown activity, and the 25-genus feasibility gate are unchanged. The biological feasibility-failure label is unchanged.

Blocked reason: none.

## Route exposure and missing proposals

The frozen audit records 42 exact quote spans and 1 v4 model-control span. It records 0 cache-side and 0 printable-confusable spans. All detected reference pairs survived and matched under the baseline convention.

No proposals surfaced Hiraea grandifolia, Randia armata, Sorocea affinis or Trema micrantha. CONTEXT omitted both directions for Inga goldmanii, Tetragastris panamensis and Trichilia tuberculata, plus rejected Miconia argentea. These absent pairs remain in the denominators.

Sample 4 was scored at 2026-09-13T19:29:02.782336+00:00, within the task window of 19:20:05–20:50:05 UTC. Three model calls completed with 0 retries; request descriptors matched all earlier samples and response bytes were distinct. All 13 sample-4 replay artifacts match byte for byte. All 355 frozen inputs remain unchanged. No rule or code changes followed the draw.

Supporting files: [scores](heldout_sample4_scores.json), [ordered rejection audit](heldout_sample4_failures.json), [route exposure](heldout_sample4_interpretation.json), [replay verification](heldout_sample4_verification.json), and [pre-draw tests](test_status.json).

# V6 — DEVELOPMENT SET

V6 adds cache-side control inference after exact, v4, and v5 quote matching. The new route permits one cached non-whitespace C0 control aligned to one printable punctuation or symbol, with unique equal-length alignment, literal anchors, exact agreement elsewhere, and candidate-local consistency.

This is one panel from one paper; implementers know the reference. It is not a sample from any population. The curator matrix used the same text blocks as the extractor, so shared blind spots would inflate apparent recall. The curator had the complete cache including tables; the original extractor worked chunk-wise under a strict quote constraint.

Samples 1–3 are DEVELOPMENT-SET evidence for v6; sample 3's failures informed the cache-side rule. Sample 4, if drawn, is a held-out model draw under the frozen rule. It measures a fresh draw of the same requests; unseen-paper performance remains untested. Every sample is separate and no proposals are pooled.

All counts use the unchanged baseline structured-direction convention. PRIMARY and CONTEXT remain separate, with fixed denominators and explicit unscorable species.

## PRIMARY — six pairs

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 |
| --- | --- | --- | --- |
| Detection | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs |
| Survival | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs |
| Correctness | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs | 6 of 6 species; 6 of 6 pairs |
| Unscorable species | 0 | 0 | 0 |

## CONTEXT — five species, ten pairs

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 |
| --- | --- | --- | --- |
| Detection | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| Survival | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| Correctness | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | both 4; collapsed 1; absent 0; unscorable 0; pairs 9 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| Unscorable species | 0 | 0 | 0 |

## Candidate stage yield

| Stage | Sample 1: v6 | Sample 2: v6 | Sample 3: v6 |
| --- | --- | --- | --- |
| Grounding survivors | 23 of 26 | 18 of 18 | 20 of 24 |

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

These three samples informed v6 development; their results do not establish performance on an untouched draw. Any separately scored sample 4 is reported in [heldout_sample4_summary.md](heldout_sample4_summary.md).

## Replay and scope

Offline replay and preservation status: passed.

Directions were checked against Table 1 of the original PDF and follow the authors' printed headings, so these are author-assigned groupings rather than inferences from numerical signs. What remains unverified is the semantic support for individual rows and captions. Reference labels are unchanged.

The frozen protocol files remain at `98b5e09`; thresholds, unanimity, assay eligibility, unknown activity, and the 25-genus feasibility gate are unchanged. The biological feasibility-failure label is unchanged.

Blocked reason: none.

The seven newly surviving sample-3 records exactly match the seven prior cache-control failures, preserving every raw schema field and structured direction. Each logs cached U+0002 at block b00003 offset 4321 aligned to model U+002D. The three development replays match all 39 scientific artifacts. All 390 pre-draw tests and lint checks passed.

# Bounded glyph grounding — DEVELOPMENT SET

This is one panel from one paper; implementers know the reference. It is not a sample from any population. All variants use the unchanged baseline structured-direction matching convention for correctness.

v3 changes only quote comparison through the two observed control-character/glyph equivalences; the v2 requests and raw model proposals are reused.

## PRIMARY

| baseline | v1 | v2 | v3 |
| --- | --- | --- | --- |
| detection: 6 of 6 species; 6 of 6 pairs | detection: 2 of 6 species; 2 of 6 pairs | detection: 6 of 6 species; 6 of 6 pairs | detection: 6 of 6 species; 6 of 6 pairs |
| survival: 2 of 6 species; 2 of 6 pairs | survival: 0 of 6 species; 0 of 6 pairs | survival: 4 of 6 species; 4 of 6 pairs | survival: 6 of 6 species; 6 of 6 pairs |
| correctness: 2 of 6 species; 2 of 6 pairs | correctness: 0 of 6 species; 0 of 6 pairs | correctness: 4 of 6 species; 4 of 6 pairs | correctness: 6 of 6 species; 6 of 6 pairs |

## CONTEXT

| baseline | v1 | v2 | v3 |
| --- | --- | --- | --- |
| detection: both 0; collapsed 4; absent 1; unscorable 0; pairs 4 of 10 | detection: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 | detection: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| survival: both 0; collapsed 1; absent 4; unscorable 0; pairs 1 of 10 | survival: both 0; collapsed 0; absent 5; unscorable 0; pairs 0 of 10 | survival: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | survival: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| correctness: both 0; collapsed 1; absent 4; unscorable 0; pairs 1 of 10 | correctness: both 0; collapsed 0; absent 5; unscorable 0; pairs 0 of 10 | correctness: both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | correctness: both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |

The dominant remaining grounding failure is unabbreviated_genus_required: 2 of 3 failed candidates per listed reason.

## Recovered records

- Spondias mombin — accepted; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:1`.
- Hymenaea courbaril — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:3`.
- Hymenaea courbaril — accepted; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:4`.
- Hiraea grandifolia — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:6`.
- Inga goldmanii — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:12`.
- Inga goldmanii — accepted; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:13`.
- Inga goldmanii — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:14`.
- Tetragastris panamensis — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:15`.
- Tetragastris panamensis — accepted; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:16`.
- Tetragastris panamensis — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:17`.
- Trichilia tuberculata — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:18`.
- Trichilia tuberculata — accepted; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:19`.
- Trichilia tuberculata — rejected; route `bounded_glyph_equivalence`; candidate `1926aadfb5b1a4f175a50a3767f71daef949b0f1055a141db707b059881ca511:20`.

## Repeat sample

The independent v2 repeat sample detected 6 of 6 PRIMARY species, retained 1 of 6, and carried the reference direction for 1 of 6. Its records are reported separately and are never pooled with v3.

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. Implementers know the reference. This is one panel from one paper and is not a sample from any population.

The numerical table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. Reference labels remain unchanged.

Candidate pass/failure counts are stage yields.

Comparison status: complete. Blocked reason: none.

# Source-level ant identity — DEVELOPMENT SET

This is one panel from one paper; implementers know the reference. It is not a sample from any population. All three variants use baseline structured-direction matching for correctness. An extra direction in a quote counts only if emitted as a structured outcome.

## PRIMARY

The denominator is six species and six species-direction pairs.

| Stage | baseline | v1 | v2 |
| --- | --- | --- | --- |
| detection | 6 of 6 species; 6 of 6 pairs | 2 of 6 species; 2 of 6 pairs | 6 of 6 species; 6 of 6 pairs |
| survival | 2 of 6 species; 2 of 6 pairs | 0 of 6 species; 0 of 6 pairs | 4 of 6 species; 4 of 6 pairs |
| correctness | 2 of 6 species; 2 of 6 pairs | 0 of 6 species; 0 of 6 pairs | 4 of 6 species; 4 of 6 pairs |

## CONTEXT

Each stage classifies five species as both directions surfaced, collapsed to one, absent, or unscorable; the pair denominator is ten.

| Stage | baseline | v1 | v2 |
| --- | --- | --- | --- |
| detection | both 0; collapsed 4; absent 1; unscorable 0; pairs 4 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 | both 5; collapsed 0; absent 0; unscorable 0; pairs 10 of 10 |
| survival | both 0; collapsed 1; absent 4; unscorable 0; pairs 1 of 10 | both 0; collapsed 0; absent 5; unscorable 0; pairs 0 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |
| correctness | both 0; collapsed 1; absent 4; unscorable 0; pairs 1 of 10 | both 0; collapsed 0; absent 5; unscorable 0; pairs 0 of 10 | both 1; collapsed 1; absent 3; unscorable 0; pairs 3 of 10 |

v2 PRIMARY survival is 4 of 6, above the baseline 2 of 6.

The dominant recorded v2 grounding failure reason is supporting_evidence[0]:ungrounded_quote, supporting_evidence[1]:ungrounded_quote (5 of 16 failed candidates per listed reason).

Reference provenance remains 6 author_prose and 5 table_derived species. PRIMARY has 2 author_prose and 4 table_derived; CONTEXT has 4 author_prose and 1 table_derived. The numerical table transcription was never visually verified against the PDF, so table-derived labels are weaker ground truth. Reference labels remain unchanged.

The curator matrix was produced by reading the same text blocks the extractor read, so shared blind spots would inflate apparent recall. The curator had the complete cached text including tables; the original extractor worked chunk-wise under a strict quote constraint. Implementers know the reference. This is one panel from one paper and is not a sample from any population.

The original v1 report and artifacts are preserved. Its candidates are rescored here with the baseline convention, which is also used for v2.

Candidate pass/failure counts are stage yields.

Baseline artifacts and recorded inputs unchanged: True. Comparison status: complete. Blocked reason: none.

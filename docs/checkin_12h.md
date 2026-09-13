# aani — check-in, hour 12

**Team:** aani (solo)
**Track:** Life Sciences / drug discovery
**Repo:** <add public GitHub URL>
**Video:** <add link>

## The problem

Animal behaviour encodes chemical information that no screening library contains.
When a leafcutter colony refuses a plant, that refusal is a chemical assay run by
evolution, scored against a live fungus and replicated across colonies and seasons.
Fifty years of those observations sit in the behavioural literature, unstructured
and unjoinable to chemistry.

## What aani does

A public-data pipeline: paper → ant–plant observation → accepted plant name →
compound structure → fungal assay. Every link retains its source. The analysis
plan and thresholds were frozen in commit `98b5e09` before any outcome was
examined. Every network response is cached by request hash, so the entire run
replays offline with no API key.

## Status at hour 12

All stages execute. **The primary test is non-estimable at the prespecified
thresholds**, and the coverage funnel identifies exactly where the evidence dies.

| Stage | Result |
| --- | --- |
| Sources retrieved | 33 |
| Sources selected | 13 |
| Extraction jobs | 23 |
| Candidate records | 61 |
| Passed automatic grounding | 41 |
| Retained after source review | 9 |
| Directional contexts to analysis | 89 (6 model, 83 curator audit) |
| Genera after conservative aggregation | 10 (6 accepted, 4 rejected, 5 conflicts excluded) |
| Genera with verified LOTUS chemistry | 8 |
| Genera with ≥1 classified compound | 7 (6 accepted, 1 rejected) |
| Mapped structures with an eligible antifungal measurement | 24 of 2,183 (1.1%) |
| Primary test | Feasibility failure; no inferential statistic computed |

Seven joined genera falls below both the 25-genus trigger and the minimum of two
genera per direction. No enrichment estimate, P-value or ranked shortlist is
reported. No threshold was relaxed to obtain one.

## Two findings that do not depend on the biology

**1. Assay coverage is the binding constraint, not behaviour or chemistry.**
Behavioural evidence is recoverable. Phytochemistry is recoverable — 27,033
occurrences imported from a checksum-verified LOTUS v4 export, 2,183 unique
structures. Whole-organism antifungal activity data for plant natural products
essentially does not exist: 7 active, 17 inactive, 2,159 unknown, with zero
retrieval failures. Anyone attempting this class of join will hit the same wall,
and now there is a number for it.

**2. Quote-grounding is necessary and far from sufficient.**
41 records passed automatic grounding; 9 survived source review. The failures were
not fabrications — they were exact quotes describing the wrong event, typically a
plant being *offered* or *placed* rather than chosen. More importantly, of the 89
directional contexts that reached analysis, 6 came from model extraction and 83
from curator audit of the same texts. The binding constraint is recall: exact-
substring grounding cannot survive tables, abbreviations or encoding artifacts, so
the discipline that makes output trustworthy also discards most of the signal.

We report the 6-versus-83 split rather than presenting curated evidence as pipeline
output. Curator contexts carry separate provenance and are not counted as model
successes or independent replicates.

## Why the negative result is the point

With ~10 genera and this many defensible analytic choices — potency threshold, unit
of inference, unanimity versus majority, endpoint definition, permutation scheme —
some combination would clear p < 0.05 by construction. Four specific relaxations
would have manufactured a hit here: majority voting to reclaim the five conflict
genera, a looser potency threshold, switching to documented-active fraction, or
widening the corpus. Each is arguable; none was made. The freeze is what makes
"non-estimable" a finding instead of an excuse.

## Next 12 hours

1. Multi-span grounding tolerant of tabular and abbreviated text, measured as
   before-and-after on the same Saverschek records. This is the direct attack on
   the 6-versus-83 gap.
2. A construct gate separating documented cutting, single-substrate acceptability
   and comparative preference — three things the pilot conflated.
3. Recall measurement against the 11-species reference matrix, which is now a
   labelled evaluation set with author-assigned directions.

## Reproduce

```bash
.venv/bin/python -m scripts.run_pipeline --offline
```

No API key required. Every figure above regenerates from the request-hash cache.

## Known limitations

- The single rejected genus reaching the assay stage has 2 classified compounds and
  0.0 species-level chemistry match; its chemistry is genus-level inference.
- Rejection evidence derives predominantly from one field study, one plant panel,
  one island. A leave-source-out diagnostic removes the rejected arm entirely.
- That panel was selected for rarely-harvested species, so its rejection fraction
  is not an unbiased estimate for plants generally.
- lme4 is unavailable in this environment; no substitute model was fitted.

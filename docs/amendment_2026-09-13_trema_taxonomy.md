# Trema taxonomy resolution — 2026-09-13

The Saverschek source spells the plant `Trema micrantha`. Its original GBIF
request returned an accepted `Trema micranthum (L.) Blume`, key `582Z4`, family
Cannabaceae, with match type VARIANT and confidence 98. That response remains
ineligible under the exact-match rule and remains archived unchanged.

NCBI taxonomy record 28954 explicitly identifies `Trema micrantha` as an
orthographic variant of `Trema micranthum`. The ITIS record distributed by GBIF
also links both names, and Kew accepts `Trema micranthum`. These external records
support a source-specific reviewed query spelling. A second GBIF query for
`Trema micranthum` returns EXACT at confidence 100, with the same accepted key.

The supplement preserves the original plant name, record IDs, directional
labels, quotes, source hashes and experimental contexts. It adds the reviewed
query spelling, accepted taxonomy and authority provenance to the existing
directional Trema contexts. It is an explicit additional merge input; original
curator audit and extraction outputs remain intact. Three unresolved Figure 4
contexts remain unresolved in the source audit.

This decision was requested after the initial feasibility failure was known.
The decision uses taxonomic evidence; no activity result selects the name.
The frozen confidence threshold, exact-match requirement, unanimity rule,
activity eligibility, unknown-activity handling and 25-genus feasibility gate
remain unchanged. The protocol files at commit
`98b5e09199a5eef0c46be452793e953f5a2af31e` remain unchanged.

Reproduce the supplement with `.venv/bin/python -m scripts.resolve_trema
--offline`. Its manifest archives the original and exact GBIF responses, NCBI
response, source artifact and supplement hashes. Pass its manifest explicitly
to the behaviour or pipeline command using `--taxonomy-supplement
data/interim/trema_resolution/manifest.json`.

Sources checked September 13, 2026:

- [NCBI taxonomy 28954](https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=28954&lvl=0)
- [ITIS record distributed by GBIF](https://www.gbif.org/species/102279411)
- [Kew Plants of the World Online](https://powo.science.kew.org/taxon/1018059-2)
- [GBIF accepted taxon](https://www.gbif.org/taxon/582Z4)

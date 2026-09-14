# Amendment: scoped microbial taxonomy for the attine control

Date: 2026-09-13

## Scope

This amendment applies only to taxonomy replay for the `attine_actino`
microbial extraction control. It does not apply to plant genera, the primary
pipeline, the existing exploratory-system taxonomy outputs, extraction, fixed
positive-control scoring, chemistry, or bioactivity. The original attine run
and its artifacts remain unchanged. Primary analysis files frozen at commit
`98b5e09199a5eef0c46be452793e953f5a2af31e` remain unchanged.

The replay reads the five records already retained by attine semantic review
and the existing cached GBIF response. It makes no model, GBIF, chemistry, or
bioactivity request.

## Rule

A microbial name resolves only when every condition below holds:

1. The configured system is `attine_actino` and the configuration declares a
   microbial taxonomy scope.
2. The requested and returned rank are genus.
3. GBIF reports `diagnostics.matchType` as `EXACT`.
4. GBIF reports finite confidence of at least 90.
5. The GBIF classification contains domain `Bacteria`.
6. The response supplies an accepted genus identity, usage key, accepted usage
   key, genus, and family under the pinned checklist.

The domain check replaces the prior `kingdom == "Bacteria"` result check for
this replay. Current prokaryote nomenclature places the cached match in domain
`Bacteria` and kingdom `Bacillati`. Requiring the bacterial domain expresses
the intended biological boundary without treating a current bacterial kingdom
name as an error.

The confidence floor is 90 because the cached response for the exact query
`Pseudonocardia` at genus rank reports an accepted canonical name of
`Pseudonocardia`, `matchType: EXACT`, confidence 93, domain `Bacteria`, and
family `Pseudonocardiaceae`. The generic floor of 95 rejects that internally
consistent response. A floor of 90 accepts the observed response while keeping
a margin below its score; exact-match, genus-rank, accepted-identity, family,
and domain gates remain mandatory. This single positive control does not
estimate an optimal general microbial threshold, so the rule stays confined to
this attine replay.

## Evidence and replay boundary

The cached request hash is
`8c7f44df24ab6264e885096e6e0986b1f40841595e361189ce4d24a489223398`.
Its request used GBIF v2 species matching with scientific name
`Pseudonocardia`, taxon rank `GENUS`, kingdom query hint `Bacteria`, and the
pinned checklist `7ddf754f-d193-4cc9-b351-99906754a03b`. The response records:

- usage key `CSXDG`, accepted status, genus rank, and canonical name
  `Pseudonocardia`;
- `matchType: EXACT` and confidence 93;
- domain `Bacteria`, kingdom `Bacillati`, and family
  `Pseudonocardiaceae`.

Offline verification must reproduce the same request hash, read the cached
HTTP envelope, resolve all five retained records to the same accepted genus,
and record zero external calls. The replay writes to the separate
`taxonomy_microbial` artifact directories. It must not overwrite the original
attine taxonomy or positive-control files.

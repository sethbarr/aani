# Reference verification against the original Saverschek Table 1

Dated 2026-09-14. This is a documentation and provenance correction. No
retrieval was run, no analysis was recomputed, no recall number changed, and no
file frozen at 98b5e09 was edited.

## What was checked

Saverschek Table 1 was checked manually, by the user, against the original PDF.
The check established how the table presents its species, not what its numeric
cells contain.

Table 1 groups species under the authors' own printed headings:

- `Acceptance`
- `Immediate rejection`
- `Habitat-related rejection`

A species placed under one of those headings therefore carries a direction the
authors assigned categorically in print. It is not a direction we inferred from
the sign of a numerical cell.

## What changed

**A provenance class was added.** `author_table_grouping` records a species
placed under a printed author heading in Table 1. It sits alongside
`author_prose`, which continues to require an explicitly named species or genus
and a direction in running text.

`author_table_grouping` is a stronger provenance class than the
`table_derived` label it replaces. The previous label implied a mapping we had
performed and could not visually confirm. The reality is an author-assigned
categorical grouping printed in the source.

**Four PRIMARY labels were reclassified** from `table_derived` to
`author_table_grouping`: Hiraea grandifolia, Randia armata, Sorocea affinis and
Trema micrantha. The two PRIMARY `author_prose` labels, Desmopsis panamensis and
Spondias mombin, are unchanged.

**One CONTEXT label was reclassified equivalently**, because the same printed
grouping applies: Miconia argentea. Its rejection direction comes from the
printed `Immediate rejection` heading. Its acceptance direction remains
`author_prose`. A species carrying both now records
`author_table_grouping` at species level.

The four CONTEXT `author_prose` labels, Hymenaea courbaril, Inga goldmanii,
Tetragastris panamensis and Trichilia tuberculata, are unchanged.

**The provenance sentence was rewritten** wherever it described the old class.
The replacement states that directions were checked against Table 1 of the
original, that the groupings are author-assigned, and that what remains
unverified is the semantic support for individual rows and captions.

**Miconia argentea's CONTEXT basis was recorded** in the reference-set
definition, as `MICONIA_CONTEXT_BASIS` in `src/evaluation/recall.py` and as a
`miconia_context_basis` field in the baseline report. Miconia is grouped under
`Immediate rejection` in Table 1 and was accepted in both habitats in the
simultaneous-choice tests. It is held in CONTEXT on that basis and carries both
directions.

## What did not change

**No number moved.** Denominators remain 6 PRIMARY and 5 CONTEXT. The
provenance split remains 2 and 4 for PRIMARY and 4 and 1 for CONTEXT; only the
name of the second class changed. Every recall, detection, survival and
correctness count is untouched, and no analysis was rerun.

**Reference directions are unchanged.** The reclassification describes how a
direction is evidenced, not what the direction is.

**Numerical transcription remains unverified.** The manual check covered the
authors' printed groupings. It did not verify the numeric values in the cells.
Per-record fields recording that state were deliberately left as they are:

- `table_cell.visual_verification: "unverified"`
- `use_as_verified_quantitative_measure: false`
- the limitation `Numeric glyph normalization is provisional until original
  table is visually verified.`
- `docs/targeted_saverschek.md`, which instructs readers not to treat numerical
  table transcription as visually verified
- `results/saverschek_audit/study_report.md`, which reports zero visually
  verified numerical cells

These statements are still accurate and are a different claim from the one that
was corrected.

**Replay and verification records were not edited.** `results/final_checks/replay.json`,
`results/publication_safety/replay_verification.json` and
`results/grounding_development_v4/heldout_frozen_verification.json` embed
`table_derived` inside a hash-bearing attestation of a past run. Rewriting an
attestation would falsify it. The counts they record, 2 and 4, remain correct
under either class name.

**The audit bundle was not edited.** `results/saverschek_audit/saverschek_audit_bundle/`
is covered by `bundle_manifest.json`, which carries a SHA-256 for every file in
it. Editing bundle contents would break those digests.

**Dated amendments were not rewritten.** `docs/amendment_2026-09-13_*.md` record
what was declared before earlier work. They keep their original wording; this
document supersedes them on this point.

`docs/index.html` was not touched.

## Consequence for the pinned baseline integrity check

`src/evaluation/comparison.py` pins an immutable baseline at commit
`aeb5130341a8c41e0373ad51aabd79b7bbbf3a12` through `BASELINE_HASHES`, which
carries a SHA-256 for `results/recall_baseline.json` and
`results/recall_baseline.md`. Applying the reclassification to those two report
files changes their bytes, so `baseline_integrity.all_original_bytes_unchanged`
is now false and dependent comparisons report
`baseline_or_original_input_changed`.

| File | Pinned | At HEAD | Current |
| --- | --- | --- | --- |
| results/recall_baseline.md | matches | matched | differs |
| results/recall_baseline.json | matches | already differed | differs |

The Markdown file matched its pin as recently as HEAD, so the provenance
rewrite is what moved it. The JSON file had already diverged before this work.

`BASELINE_HASHES` was deliberately **not** updated. The pin exists to detect
exactly this kind of change, and rewriting it to match the new bytes would
remove the check rather than satisfy it. Reverting the two files was also
rejected, because the reclassification is the requested correction and is
substantively right.

This is left as an open decision. Either the baseline is re-pinned at a new
commit as a recorded amendment, with the reason stated, or the two report files
are regenerated and re-pinned together. Both require a decision that is outside
a documentation fix, and neither changes any recall number: the provenance
counts remain 2 and 4 for PRIMARY and 4 and 1 for CONTEXT under the new class
name.

## Trema name check

The paper prints *Trema micrantha*. Our taxonomy resolved *Trema micranthum*.
Both spellings were checked in the cached GBIF responses, and the resolution is
confirmed correct and left unchanged.

| Query | Match type | Confidence | GBIF key | Returned name | Status |
| --- | --- | ---: | --- | --- | --- |
| Trema micrantha | VARIANT | 98 | 582Z4 | Trema micranthum (L.) Blume | ACCEPTED |
| Trema micranthum | EXACT | 100 | 582Z4 | Trema micranthum (L.) Blume | ACCEPTED |

Both spellings resolve to the same taxon, key 582Z4. This is an orthographic
gender-agreement variant of the specific epithet, not a synonym of a different
taxon and not a taxonomic reassignment. GBIF treats *Trema micranthum* as the
accepted name and the paper's spelling as a variant of it. NCBI records the
paper's spelling explicitly as `Trema micrantha, orth. var.`

The behaviour record already carries this resolution as
`reviewed_orthographic_variant_then_exact_query`, with the original name, the
authority statement and the cached request hashes, under the existing
`docs/amendment_2026-09-13_trema_taxonomy.md`. The panel continues to key on the
original spelling *Trema micrantha*, so the denominator is unaffected.

## Scope of the manual check

The verification is one reader checking one printed table in one paper against
one PDF. It confirms that the direction labels come from the authors' own
categorical headings. It does not establish that the rows and captions support
the semantics we read into them, it does not verify any numeric cell, and it
does not make this single-paper development panel a sample of any population.

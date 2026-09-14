# Saverschek 2010: targeted behavioural source

Prepared 2026-09-12 as a separate extension. The frozen 30-paper corpus, its
screening, extraction prompt, and analysis protocol were not changed.

## Ready inputs and provenance

- Source ID: `SAVERSCHEK2010`; DOI `10.1016/j.anbehav.2009.12.021`.
- Corpus: `data/interim/corpus_targeted_saverschek/manifest.jsonl`.
- Source blocks: `data/interim/corpus_targeted_saverschek/texts/SAVERSCHEK2010.json`.
- `make_jobs` succeeds: nine page blocks, three chunks; 20,971 / 21,661 / 9,273 characters.
- Full-source coverage: 1,005 numbered lines (0-1004), no gaps or conflicting
  overlaps. The bibliography remains in the archive but is excluded from model
  blocks, matching the existing corpus parser's policy.
- Four exact web-tool requests/results are archived in `data/raw/web/` by request
  hash, including tool name, arguments, source URL, retrieval time and explicit
  representation `web_extracted_pdf_text`. Their hashes and line mapping are in
  `data/interim/corpus_targeted_saverschek/web_line_coverage.json`.
- Rebuild offline with `PYTHONPATH=. .venv/bin/python
  data/interim/corpus_targeted_saverschek/build_source.py`.

The [author-uploaded published paper](https://www.researchgate.net/profile/Flavio-Roces/publication/248591945_Avoiding_plants_unsuitable_for_the_symbiotic_fungus_learning_and_long-term_memory_in_leaf-cutting_ants/links/5a437795a6fdcce19716aba4/Avoiding-plants-unsuitable-for-the-symbiotic-fungus-learning-and-long-term-memory-in-leaf-cutting-ants.pdf)
was available as complete indexed PDF text. **Original PDF bytes were not
archived.** Direct HTTP returned 403; web screenshot requests also failed.
Mathematical glyphs and some word breaks are imperfect. Do not treat numerical
table transcription as visually verified. Source wording was retained without
silent character repair. The paper carries a copyright notice; public discovery
does not imply an unrestricted reuse licence.

## Behavioural review guide

Natural tests used *Atta colombica* in Panama, November 2002-August 2003:
three colonies per species/habitat, untreated 7-mm discs, 30-minute individual
tests on days 1-3. BCI = plants present; Gamboa = absent. Supplementary
feeding followed day 1. Simultaneous tests used different colonies, two days,
45-minute sessions. (Methods: `b00001`, `b00002`.)

| Plants | Individual-test directions |
| --- | --- |
| Spondias mombin | Accepted both habitats, all days |
| Desmopsis panamensis; Hiraea grandifolia; Miconia argentea; Randia armata; Sorocea affinis; Trema micrantha | Immediate rejection both habitats |
| Hymenaea courbaril; Inga goldmanii; Tetragastris panamensis; Trichilia tuberculata | BCI immediate rejection; Gamboa initial acceptance, subsequent rejection |

Table 1: `b00005`; narrative: `b00003`. Simultaneous tests additionally accepted
Miconia in both habitats on both days. Preserve these conflicts. Author categories
are not a universal sign-of-index threshold.

Earliest direct example, `b00003`:

> [Private source reference r00000]

Separate Stigmaphyllon lindenianum experiments used CHX, sugared leaves, and
follow-up untreated leaves. Their induced rejection is not natural chemical
evidence. Natural delayed-rejection fungal mediation remains unresolved in this
paper. [Source](https://doi.org/10.1016/j.anbehav.2009.12.021).

## Access audit and next run

`access_log.json` retains network failures and successful metadata retrievals.
Institutional bibliography and Smithsonian records identify the paper but supply
no full text. OpenAlex lists no alternate open location. Crossref's advertised
Elsevier text-mining URL returned HTTP200 **metadata only**, not article text.
The German National Library thesis was retrieved and is a separate work; its
contents/publication list do not constitute this field paper. It is not in the
ready manifest. Existing `research/attine_selection_2026-09-12/` files were
inventoried but not modified; the target paper was absent there.

Source preparation made no paid model calls. The next command runs only this
separate targeted source:

```bash
.venv/bin/python -m scripts.extract \
  --provider gemini --model \
  --corpus data/interim/corpus_targeted_saverschek \
  --output data/interim/extraction_saverschek
```

The root subsequently ran this command: all three jobs completed, with 14
candidates, six automatic passes and eight failures. The source review includes
three context-specific natural records, excludes the CHX-conditioned retest,
and leaves two leads pending. The review is saved alongside raw outputs as
`semantic_review.json`. GBIF resolves the three included records. Only Desmopsis
is a consistent rejecter in the current prose-grounded set; Hymenaea remains a
conflict. Full and comparative-choice table recovery remains outstanding.

Review every returned direction against source blocks, especially the initial
acceptance, simultaneous-choice Miconia result, and CHX history. Keep all eligible
directions before the frozen conservative genus aggregation. Neither historical
nonharvesting nor treatment-induced rejection qualifies as a natural rejection.
No chemistry joins or antifungal outcome tables were inspected in this source
task; the paper's own discussion contains incidental chemical claims.

## Full text audit completed — 2026-09-12

The [audited study report](../results/saverschek_audit/study_report.md) and
[artifact index](../results/saverschek_audit/README.md) supersede the provisional
source yield above. They preserve all original model records and the frozen
pilot. Curator recovery accounts for 110 natural contexts (66 individual and
44 simultaneous), with 87 supported directions and 23 explicitly unresolved
Figure 4 cells. These are aggregate contexts, not independent observations.

The source supports one accepted, five rejected and five conflicted genera.
Ten of eleven species pass exact GBIF matching. Trema micrantha returns VARIANT
at confidence 98, with Trema micranthum as the returned name; it remains on hold
under the unchanged exact-match rule. Four source rejecters are therefore ready:
Desmopsis, Hiraea, Randia and Sorocea. The versioned combined snapshot contains
six accepted and four rejected genera, with five conflicts. Its stricter
simultaneous-choice subset still has only one accepted genus.

The audit recovered Figure 7's caption at raw lines 899–906. The historical
parser stopped at References and excluded it from model input. The recovered
caption is an audit-only supplement, not a retrospective change to that input.
It reports N=5 at weeks 14/16 and N=4 at week 18, exposing an additional mismatch
with nearby prose. All seven figures, Table 1, 12 manipulation/context phases,
secondary claims, 71 source anchors, and all 14 candidates are inventoried.

Original PDF graphics remain inaccessible. All 66 numerical Table 1 tokens are
preserved, but their normalized numerical fields remain provisional and do not
determine direction. This is a complete text-based audit with disclosed gaps,
not complete visual verification or a replication of the published statistics.

Rebuild without API calls:

```bash
.venv/bin/python -m scripts.build_saverschek_audit
```

The new combined observations replace, rather than append to, the three old
Saverschek inclusions. No chemistry or antifungal activity data were joined.

## Publication source references

Full text is retained locally and is not redistributed. Source fields are private references; scientific counts and decisions retain their original values. Historical artifact hashes identify the byte-exact private originals.

Full-text locators for this file are in [the publication audit](../results/publication_safety/audit.json).

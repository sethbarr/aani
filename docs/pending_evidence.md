# Pending evidence review — 2026-09-12

All three pending leads can be replaced by separately identified, source-grounded
acceptance observations. These are **proposed Codex-assisted source corrections**,
not Gemini outputs or an independent human audit. Original extraction and review
files remain unchanged. Integration must replace the corresponding pending claim,
not count both versions. None of these proposals supplies primary rejection evidence.

| Pending lead | Verified original/context | Proposed handling |
|---|---|---|
| Tozin 2017; *Ocimum gratissimum* / *Acromyrmex rugosus* | [Original paper](https://europepmc.org/articles/PMC5710599), DOI 10.1093/aobpla/plx057; greenhouse exposure of undosed potted plants, 90% leaf removal in 48 h | Replace secondary claim with the original initial-cutting observation |
| Kost 2011; *Phaseolus lunatus* / *Atta colombica* | [Original paper](https://europepmc.org/articles/PMC3140513), DOI 10.1371/journal.pone.0022340; baseline laboratory harvesting, separately described from induced-plant tests | Replace the secondary repeated-exposure summary with explicitly labelled primary baseline evidence |
| *Acalypha wilkesiana* / *Acromyrmex subterraneus subterraneus* | [Original paper](https://europepmc.org/articles/PMC9965205), DOI 10.3390/pathogens12020330; fresh-leaf cutting by the no-fungus control group | Split to control-only cumulative cutting; do not infer a pre-exposure-only result or numeric leaf area |

For Tozin, the source identifies a naturally infested greenhouse, eight exposed
plants and eight protected controls. The external water/detergent barrier belonged
to protected controls; the attacked plants were not dosed. The observation is
harvesting during the initial attack, not the later biochemical measurements on
regrown leaves. `lab_bioassay` describes the controlled greenhouse exposure and
does not imply a field preference experiment or fungal-garden incorporation.

For Kost, the primary text says the study's laboratory colonies readily harvested
lima bean, and its methods identify the colonies as *Atta colombica*. Experiment 1
reports initial cutting before subsequent plant defence induction. The primary
baseline observation has a different context from the secondary sentence about
repeated damage, so the transformation audit makes that substitution explicit.
Jasmonic-acid-treated plants are ineligible for primary inference. Repeated-damage
and mechanically injured arms are experimentally induced contexts, kept outside
these baseline proposals; their relative avoidance cannot silently become
evidence that untreated *Phaseolus* is a rejected genus.

For Acalypha, source blocks b00011 and b00020 identify fresh leaves; b00018 and
b00019 distinguish the fungus-free control bait; b00031 identifies cutting of
*A. wilkesiana*; b00030 explicitly reports the highest cutting in controls.
The proposed record is control-only across the reported period. The body text
does not provide a separately quantified pre-exposure cutting result. Bait
exposure of colonies must not be represented as fungus dosing of these leaves,
and reduced cutting by fungus-exposed colonies is not plant rejection.

The exact original record IDs, source document hashes, HTTP request hashes,
quoted blocks, changed fields and reasons are saved in
`data/interim/pending_evidence_review/transformation_audit_v1.json`.
The three proposals are in `proposed_observations_v1.jsonl`; abbreviated names have
source-verified expansions in `name_mappings_v1.json`. The two new open-access
originals were retrieved from Europe PMC into the separate `corpus/` directory.
The existing Acalypha document is copied there without altering its block IDs.
This is source-following of pilot citations, not a replacement of the original
fixed pilot selection. All HTTP responses are cached in `data/raw/http/`.

Each proposal passed the existing schema, exact-quote, plant-in-quote,
source/section and confidence checks. Every added context anchor and name mapping
was also checked against the complete cached document. The artifacts can be
rebuilt without network calls:

```bash
PYTHONPATH=. .venv/bin/python data/interim/pending_evidence_review/build_review_v1.py
```

The next integration step is to review these replacements as distinct manual
records, apply the supplied source-specific name mappings, and perform the
unchanged GBIF resolution gate. Until integration, the original three remain
pending in the original run, and these files must not be described as additional
Gemini-validated records. No chemistry join or antifungal activity lookup was
used to decide eligibility; behavioural papers contain incidental chemistry
discussion, which is not an activity outcome analysis.

Root integration is now complete: all three source hashes, main/context anchors,
record identities and supersession links were checked. Separate approved copies
are at `data/interim/evidence_recovered/`; all three matched GBIF under
`data/interim/taxonomy_recovered/`. The original pending file remains historical,
and its three records are not also counted in the current combined snapshot.
These remain manual source corrections, not additional Gemini successes.

# LOTUS occurrence acquisition and replay

The end-to-end run uses the **LOTUS frozen export v4**, published 25 May 2022,
[Zenodo record 6582121](https://zenodo.org/records/6582121). This is a deliberately
pinned release, not a claim to use the newest LOTUS database. The complete bulk
file was downloaded before filtering by the audited behavioural genera. No
taxon API query or antifungal label was used to select occurrence records.

The release's [version-specific metadata](https://zenodo.org/api/records/6582121)
specifies **CC BY 4.0**, the file size, and its MD5 checksum. The official
[licence terms](https://creativecommons.org/licenses/by/4.0/legalcode.en) are
cached with the metadata. Reuse and adaptation require attribution, a licence
link, and an indication of changes; additional restrictions are prohibited.
The broader LOTUS project's statements about CC0 on Wikidata do not replace
this particular export's CC BY 4.0 terms.

Attribution: Rutz, A.; Bisson, J.; Allard, P.-M. (2022). *The LOTUS Initiative
for Open Natural Products Research: frozen dataset*, v4. Zenodo.
[doi:10.5281/zenodo.6582121](https://doi.org/10.5281/zenodo.6582121).

The downloaded file is `validated_referenced_structure_organism_pairs.tsv.gz`:

- Download: <https://zenodo.org/api/records/6582121/files/validated_referenced_structure_organism_pairs.tsv.gz/content>
- Retrieved: `2026-09-13T00:04:50.467719+00:00` (12 September in New York).
- Bytes: `315165362`.
- Published and verified MD5: `41a2c094d99901d6c453f38be4b8d7bb`.
- SHA-256: `ffb310fffb395514e2fec5f42b682812d4f459c8783b884c67a737621ee2b5d2`.
- Download request hash: `6893a0d2b680e5ecbe5b835c82d72aa4001c3ee0aa62e3d58932a03191cb8f31`.

## Import contract and provenance

`src/chemistry/lotus.py` verifies the TSV header before adapting it to the CSV
contract in `src/chemistry/occurrences.py`. Every imported row uses the taxon,
full InChIKey, stereochemical SMILES, and curated DOI/PMCID/PMID from **the same
export row**. References are never crossed with an unrelated organism list.
This follows LOTUS's documented [referenced structure-organism data model](https://elifesciences.org/articles/70780).

`plant_name` uses `organismCleaned`; `original_plant_name` preserves
`organismValue`. The full selected TSV rows preserve every other source field.
The export has no native LOTUS record-ID column: `database_record_id` is an
explicitly labelled locator, `zenodo:6582121:record:<one-based data record>`.
It identifies a record in the archived versioned file and is not presented as
a native LOTUS accession. DOI URL construction lowercases the identifier and
percent-encodes its URL; the unmodified DOI remains in the source row.

The importer requires an aligned taxonomic lineage with exact `kingdom=Plantae`
and an exact requested genus. Alternative representations that omit Plantae,
use different kingdom terminology, or repeat rank labels go to the transform
review file. They are **not asserted to be nonplants**. This conservative
representation filter retains 27,033 records and puts 26,864 candidate rows in
review. Most review rows duplicate other taxonomy representations; a full-key
comparison finds no additional primary-eligible compounds in review and 12
additional Trichilia keys, a conflict genus. No synonym expansion is performed.

An occurrence is labelled `species` only when its cleaned taxon exactly matches
a behavioural accepted name; other taxa of the genus are labelled `genus`.
Distinct occurrence effort uses `(genus, full InChIKey, original reference)`.
All duplicate source provenance remains available. Structures are identified
by their complete InChIKey; stereoisomers and salts are not collapsed. These
are database-supported occurrence claims, not a new manual audit of every
original phytochemistry publication.

## Actual coverage

The complete scan read **6,467,819 export records**. The 15 requested genera
matched 53,897 candidate records; the validated contract imported 27,033 rows,
representing **3,774 distinct occurrences and 2,183 distinct full InChIKeys**.
There were no additional contract-validation rejects after the transform gate.

Chemistry is mapped for 12 of 15 audited genera. In the primary-eligible subset,
8 of 10 genera have chemistry: all six accepted genera and the rejecting genera
Randia and Sorocea. Those eight genera contain **1,851 distinct full InChIKeys**.
Desmopsis and Hiraea have missing chemistry; `mapped_compounds` is null. They
are not represented as zero-compound genera. Four of five behavioural conflicts
have chemistry; Tetragastris is missing.

## Commands and files

```bash
.venv/bin/python -m scripts.chemistry --lotus-export \
  --genera data/processed/behaviour/all_genera.jsonl

.venv/bin/python -m scripts.chemistry --lotus-export \
  --genera data/processed/behaviour/all_genera.jsonl --offline
```

The second command forbids network access and rechecks the complete cached
export SHA-256, its published MD5 metadata, and its size before rescanning.
Outputs use the stable acquisition timestamp so identical inputs replay
byte-for-byte. A missing cache, unverified licence, missing header, or checksum
failure writes explicit blocked metrics and exits unsuccessfully.

The completed verification reproduced **all eight generated chemistry data and
manifest files byte-for-byte**, and the four chemistry raw-cache files were
unchanged. `data/processed/chemistry/offline_replay.json` records the command
and every output hash. Four regression tests cover offline replay, preserved
provenance/effort deduplication, cache corruption/misses, missing references,
and an unverified licence; all pass.

- `data/raw/chemistry_export/http/`: request-hash metadata/licence responses.
- `data/raw/chemistry_export/downloads/`: complete bulk body and request-hash sidecar.
- `data/raw/chemistry_imports/`: SHA-256-addressed adapted CSV copy.
- `data/interim/chemistry/occurrence_contract.csv`: locally filtered CSV contract.
- `data/interim/chemistry/selected_export_records.jsonl`: complete selected source rows.
- `data/interim/chemistry/transform_review.jsonl`: source rows failing taxonomic verification.
- `data/processed/chemistry/occurrences.jsonl`: imported provenance-preserving occurrences.
- `data/processed/chemistry/review.jsonl`: subsequent CSV-contract validation failures.
- `data/processed/chemistry/genus_coverage.jsonl`: explicit mapped/missing coverage.
- `data/processed/chemistry/run_manifest.json`: licence, version, URLs, hashes, transformations.
- `data/processed/chemistry/metrics.json`: stage counts and blocked status.

The processed files represent this labelled genus subset, not import of the
entire LOTUS export. The complete export is nevertheless locally archived for
reproducible re-filtering without further downloads.

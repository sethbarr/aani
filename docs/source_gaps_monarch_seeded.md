# Seeded monarch source gaps — 2026-09-13

## Update: all five source-text gaps resolved by user supply

The user supplied all five requested PDFs later on 2026-09-13. Their first-page
DOIs and titles match the verified bibliography. All 40 pages are cached with
PDF, text and page-coordinate provenance. Lefèvre 2010 and 2012 contain the
two primary focal oviposition experiments and are screened in. The other three
papers have assigned larval-diet experiments and remain mechanistic background.
The extra supplied de Roode virulence-transmission paper is outside the five
declared seeds. Supplying a PDF does not establish an OA licence.

The [current report](/Users/seth/Documents/ChatGPT/hackathon/results/systems/monarch_seeded/summary.md)
records a 25-paper corpus and twelve completed jobs. Five new Gemini jobs cover
the two Lefèvre papers; seven selected discovery jobs reused exact cached
responses. The user approved these payloads before execution. The earlier access audit below
is preserved as retrieval history, including the original source requests.

## Initial public-access audit, before user supply

This access audit belongs to the exploratory seeded rerun. It is excluded from
inference and leaves the original monarch corpus unchanged. The amendment was
committed before retrieval as `a70546497beeb59ba929bccf93bd4c46b19758b4` at
`2026-09-13T13:30:55-04:00`.

All five DOI searches returned verified Europe PMC MED records. None has a
PMCID or an indexed Europe PMC fullTextXML route. The access manifest labels
these `not_open_access` within that service's scope. Four institutional copies
are listed publicly, but their PDF requests returned HTTP 403. Their wider OA
status is unresolved. Gowler's publisher page offers subscription access.
No paywalled text was scraped. At that point, no seed was ready for extraction.

## Verified bibliography and initial access

| Seed | Verified DOI and primary record | Europe PMC full text | Additional public route | Initial gap, now resolved |
| --- | --- | --- | --- | --- |
| Lefèvre, Oliver, Hunter & de Roode (2010), *Evidence for trans-generational medication in nature*, Ecology Letters 13:1485–1493 | [10.1111/j.1461-0248.2010.01537.x](https://doi.org/10.1111/j.1461-0248.2010.01537.x); [PMID 21040353](https://pubmed.ncbi.nlm.nih.gov/21040353/) | Not open access in this service; no PMCID | [Michigan record](https://hdl.handle.net/2027.42/79381); listed PDF request returned 403 | Supply PDF; focal-design priority |
| Lefèvre et al. (2012), *Behavioural resistance against a protozoan parasite in the monarch butterfly*, Journal of Animal Ecology 81:70–79 | [10.1111/j.1365-2656.2011.01901.x](https://doi.org/10.1111/j.1365-2656.2011.01901.x); [PMID 21939438](https://pubmed.ncbi.nlm.nih.gov/21939438/) | Not open access in this service; no PMCID | [Michigan record](https://deepblue.lib.umich.edu/handle/2027.42/89483); listed PDF request returned 403 | Supply PDF; focal-design priority |
| de Roode, Pedersen, Hunter & Altizer (2008), *Host plant species affects virulence in monarch butterfly parasites*, Journal of Animal Ecology 77:120–126 | [10.1111/j.1365-2656.2007.01305.x](https://doi.org/10.1111/j.1365-2656.2007.01305.x); [PMID 18177332](https://pubmed.ncbi.nlm.nih.gov/18177332/) | Not open access in this service; no PMCID | [Michigan record](https://hdl.handle.net/2027.42/72199); listed PDF request returned 403 | Supply PDF for full-text screening |
| Sternberg et al. (2012), *Food plant derived disease tolerance and resistance in a natural butterfly-plant-parasite interactions*, Evolution 66:3367–3376 | [10.1111/j.1558-5646.2012.01693.x](https://doi.org/10.1111/j.1558-5646.2012.01693.x); [PMID 23106703](https://pubmed.ncbi.nlm.nih.gov/23106703/) | Not open access in this service; no PMCID | [Michigan record](https://hdl.handle.net/2027.42/94251); listed PDF request returned 403 | Supply PDF for full-text screening |
| Gowler, Leon, Hunter & de Roode (2015), *Secondary Defense Chemicals in Milkweed Reduce Parasite Infection in Monarch Butterflies, Danaus plexippus*, Journal of Chemical Ecology 41:520–523 | [10.1007/s10886-015-0586-6](https://doi.org/10.1007/s10886-015-0586-6); [PMID 25953502](https://pubmed.ncbi.nlm.nih.gov/25953502/) | Not open access in this service; no PMCID | [Publisher record](https://link.springer.com/article/10.1007/s10886-015-0586-6) requires access; no verified public copy | Supply PDF for full-text screening |

The Sternberg title above preserves the indexed wording, including the plural
“interactions.” It differs from the tentative citation supplied for retrieval.
The Gowler title includes the final species name. Lefèvre 2012's DOI contains
2011, its online publication year; the journal issue year is 2012.

## Provenance and resumption

Verified Europe PMC responses are cached under
`data/interim/systems/monarch_seeded/cache/europepmc/http/`; unsuccessful public
PDF responses are cached under `cache/repository/http/` within the same run.
The bibliographic audit records the observed public URLs, including unusual
encoded suffixes in search-indexed links. A failed HTTP response is an access
failure and contributes no article text.

The initial request for all five PDFs is resolved. The supplied files have
content hashes, article-identity checks, page-linked text and recorded screening
decisions in `corpus_targeted_monarch/`. Complete seed papers have priority
within the 12-job cap. Approval for five new model jobs for Lefèvre 2010 and
2012 was recorded at `2026-09-13T19:42:38+00:00` in
`results/systems/monarch_seeded/payload_approval.json`. All five new jobs and
seven cached discovery jobs completed. The current report records semantic
review, focal-design recovery and downstream coverage separately.

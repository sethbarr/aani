# Local literature leads

The locally supplied Obsidian research folder contains curated notes and
transcribed supplements that can accelerate review. They are leads and audit
context; they do not replace quote-grounded extraction from the cited papers.

## Wirth avoidance complement

`data/wirth2003_bci_plot_vs_harvest.csv` has 85 plant rows from Wirth et al.
(2003): 49 harvested, 33 marked **NEVER HARVESTED**, and 3 ambiguous
genus-level matches. The never-harvested rows are a valuable seed list for
retrieving the underlying Chapter 4/10 evidence, but the CSV has no source
block or verbatim quote. Importing it directly as a primary observation would
violate the extraction grounding rule. Keep the 33 rows in a review or query
seed table. Even with a verified source, absence from a harvest list cannot
become primary `rejected` evidence under the frozen protocol. A separate direct
choice/rejection observation is required; an availability-adjusted nonharvest
analysis would need its own prospective amendment and comparison design.

The notes also document the main confound: many never-harvested plants lack
large canopy stems. The size/abundance filter is useful for candidate
prioritisation, but it must not be used to select the primary enrichment result
after looking at chemistry.

## Crumière acceptance data

`data/crumiere2021_tableS11.csv` contains 87 fragment-level nutrition and
mineral records, and `data/crumiere2021_barcode_identity.csv` contains 44
barcode identities from Crumière et al. (2021). This is an acceptance dataset:
the sampled material was cut and carried, so low mass is not an observed
rejection. It can support a secondary “sampled sparingly” lead list, including
the repeated *Davilla nitida* observations, but it must not be encoded as
`outcome=rejected` in the primary test.

The reading list in the same folder identifies high-value source papers for the
corpus search, including Hubbell et al. (1983, 1984), Waller (1982), Rockwood
(1976, 1977), Herz et al. (2008), and Saverschek et al. (2010). Their titles and
DOIs can seed targeted retrieval; extracted records still need the same source
ID, section, block and verbatim-quote checks as API-discovered papers.

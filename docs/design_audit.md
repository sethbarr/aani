# Behavioural construct audit — 2026-09-12

The user supplied an external critique after the screened extraction. It identifies
a real distinction: documented cutting is not necessarily comparative preference.
This audit preserves the frozen protocol and original records. It does not
silently redefine acceptance, discard inconvenient directions or change the
antifungal endpoint.

## What the original funnel means

The screened pilot produced 47 candidates: 35 passed automatic checks and 12
failed. Source review retained six, excluded 26 from the primary evidence table,
and left three pending. Thus six/47 = 12.8% were initially retained; 29/35 = 82.9%
of grounded candidates were not retained. Post-grounding attrition accounts for
29/41 = 70.7% of all records not retained, not 83% of total attrition.

This is an eligibility funnel, not an accuracy or recall estimate. Some excluded
records correctly describe artificial substrates or secondary reports; other
records genuinely mislabel treatment or mistake offering for acceptance. The
three pending records subsequently received separately audited manual replacements,
all acceptance, with their origin preserved outside the Gemini extraction outputs.

## Cutting, acceptability and preference

The extraction prompt defines `behavioural_choice` as actual collection, feeding
or rejection. It does not require simultaneous alternative plant substrates.
The protocol's phrase "feeding choice" leaves that design distinction implicit.
The six original retained records document cutting of untreated plants, so they
fit the implementation. They should be described as laboratory harvesting under
the reported exposure conditions, not preference for those species or successful
fungal-garden incorporation.

PMC11543716 used ants to induce plant damage for physiological measurements.
Methods b00008 and b00012 do not document alternative plant choices. Discussion
b00026 explicitly identifies Arabidopsis thaliana and Vicia faba as nonhosts.
`substrate_treatment=natural` currently means untreated plant material; it does
not establish that the plant is an ecological host. These are separate dimensions.

The three recovered records likewise report natural-leaf cutting or baseline
harvesting without establishing comparative preference. In Saverschek 2010,
single-species field tests allow voluntary pickup, ignoring and trail clearing.
These measure direct natural acceptability. Separate simultaneous 11-species
tests measure comparative choice. Requiring alternatives would remove useful
single-substrate rejection evidence as well as the laboratory acceptance cases.

Use an explicit design audit (`documented_alternatives`, `single_substrate`,
`exposure_without_documented_alternatives`, or `unspecified`) and retain source,
experiment, colony and host-status evidence. An alternatives-only analysis is a
stricter sensitivity with a dated definition, not a correction to the old record
count. Under that sensitivity, none of the presently retained direct prose
records establishes an alternatives-based comparison; the simultaneous-choice
source results still need dedicated extraction and review.

## Dependence and the threshold for a test

Four records share a sentence because it reports cutting of four different plant
taxa. They are distinct taxon-specific outcomes in a shared experiment, not four
independent studies. Current primary aggregation reduces six records to four
equally weighted genera. It does not resolve shared source, colony, environment
or experimental-design effects. Family clustering alone does not address those
dependencies. Source-level coverage and a leave-source-out diagnostic are needed;
removing the one source eliminates the original pilot's retained evidence.

Two rejection records alone do not make the planned comparison estimable. The
protocol requires at least two consistently rejected and two consistently
accepted genera after the chemistry/activity join. Fewer than 25 joined genera
still triggers a feasibility-failure label, even if exploratory statistics can
be calculated.

## Saverschek result and conservative handling

The targeted run completed three chunks and returned 14 candidates, six automatic
passes and eight failures. Its prose directly supports natural Desmopsis
panamensis rejection and Spondias mombin acceptance. Hymenaea courbaril is rejected
in plant-present habitat but accepted initially in plant-absent habitat. Losing
the latter extraction to a quote mismatch cannot turn the genus into a consistent
rejecter. Source text also identifies mixed contexts for Inga, Tetragastris,
Trichilia and Miconia; hold these conflicts visible before genus aggregation.

The new source improves evidence coverage but does not yet establish two
consistently rejected genera with measured chemistry. Original PDF bytes and
visual verification of its numerical table remain unavailable. The complete
cached text and named prose results are auditable; quantitative table transcription
is not claimed as verified.

## Check-in wording

"The API pipeline completed, but exact quotation was insufficient for analytical
eligibility. The fixed pilot yielded four acceptance genera from one laboratory
study and no rejection genera. A targeted field study now provides direct
natural rejection, while also exposing context-dependent reversals. We are
separating collection, acceptability and comparative preference before chemistry."

The next extraction evaluation should distinguish grounding, treatment accuracy,
behavioural design and primary eligibility against a manually specified reference
set. Include true natural choice, single-substrate pickup/rejection, no-choice
damage induction, husbandry-only provision, manipulated leaves and diet absence.
The present funnel alone does not measure model precision or recall.

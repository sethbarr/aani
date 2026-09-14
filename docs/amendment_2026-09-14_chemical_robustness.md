# Chemical-distance robustness predeclaration

Declared on 14 September 2026 before any robustness draws. The implementer has
seen the original chemical-distance results (observed median 0.320, size-matched
random-reference median 0.400). These are exploratory sensitivity analyses of a
known result. This declaration is separate from the frozen biological protocol
at 98b5e09 and the completed reader experiment.

## Scope and immutable inputs

Use the five existing chemical-distance inputs: chemistry occurrences, bioactivity
labels, measurements, eligible assays, and genus behaviour. Preserve their bytes,
the original labels, and all primary biological results. No external retrieval,
model extraction, activity prediction, imputation, or wet-lab claim is introduced.
The reference flag means an eligible measurement was retrieved for the compound;
absence of that flag does not establish that a compound was never tested.

Archive the previous chemical-distance outputs before correcting report wording.
Keep the original output numbers unchanged by that editorial correction. The new
robustness outputs go only under results/chemical_distance_robustness. Record input
hashes, code hashes, declaration commit/timestamp, RDKit/NumPy versions, and every
specified analysis. Stop on input drift or an error; do not replace a failed result
with another seed or a modified specification.

## Fixed representations and population variants

Use the existing RDKit Morgan radius-2, 2048-bit fingerprints and pairwise Tanimoto
similarity, without molecular standardization or changes to input structures.
Unresolvable structures are counted and excluded consistently.

Evaluate these four populations in this order:

1. Original resolved corpus, one unit per compound identifier.
2. Resolved compounds with at least six heavy atoms, removing small structures
   from both reference and query pools.
3. Population 2 collapsed into exact fingerprint-equivalence classes. Each class
   is one unit, weighted equally. Its representative is the lexicographically
   smallest compound identifier, chosen independently of measurement status. Its
   reference flag is true when any member has an eligible retrieved measurement;
   all members are excluded together from the observed query set. Use the union
   of members' source genera and their median heavy-atom count for matching.
   Fingerprint equivalence can combine stereoisomers or hash collisions; it is a
   sensitivity representation, not a claim of molecular identity. Record class
   membership, multiplicity, and classes mixing measured and unmeasured members.
4. Population 3 after excluding every class whose genus union includes Arabidopsis,
   including classes also reported in another genus. This checks dependence on
   the largest contributing genus; it changes the population being described.

## Fixed random-reference schemes

For each of the four populations, evaluate all four schemes:

- Unrestricted: choose the observed number of reference units uniformly without
  replacement from the population.
- Size matched: sample without replacement within heavy-atom bins, preserving
  the observed reference count in each bin. Fixed bin edges are 0, 6, 11, 21, 31,
  41, 61, and infinity.
- Genus matched: use the exact sorted genus-membership tuple as a stratum,
  preserving the observed reference count in every tuple. An empty tuple has its
  own stratum. This handles compounds reported from multiple genera without
  assigning them an arbitrary single genus.
- Jointly matched: use genus-membership tuple crossed with the fixed size bin.

Sampling within each stratum uses the full population in that stratum, including
observed reference members. Strata with zero observed reference members contribute
zero picks. Strata whose observed reference count equals their population size
have forced membership. Report the number of strata, forced reference units,
reference units with exchangeable membership, and distinct sampled reference sets.
Do not merge sparse strata or change bins after viewing results. Degenerate nulls
remain explicit and cannot support a robust separation claim.

## Draws, statistic, and interpretation

Run 2,000 draws per population/scheme cell (16 cells; 32,000 draws total). Use NumPy
default_rng with seed 20260914 + 100 * population_index + scheme_index, both indices
zero based in the orders above. Each cell starts a fresh generator. No adaptive
stopping or additional draws. Empty reference or complement sets make a cell
unscorable, with the reason retained.

The observed statistic is the median over units outside the observed reference
set of maximum Tanimoto similarity to that set. For every draw, recompute the
complement of that draw's reference set and apply the identical statistic. A unit
can never compare with itself. Compare observed similarity with the median of the
2,000 null statistics. Report their difference (observed minus null median), the
2.5th and 97.5th percentiles of null statistics, and the count of draws at or below
the observed statistic. The percentile range is a randomization reference range,
not a confidence interval for a population effect. Save all null statistics.
No new hypothesis-test p-values or multiple-testing claim will be produced.

Call the within-corpus separation descriptively robust to the specified checks
only if all 16 cells are scorable and nondegenerate, all differences are negative,
and the observed statistic lies below the 2.5th null percentile in the jointly
matched cells for populations 3 and 4. Otherwise report which adjustments attenuate,
reverse, or make the separation unidentifiable, without selecting a favorable
subset. These are exploratory descriptive rules, not causal or population tests.
The size and genus controls can condition on characteristics related to chemical
structure; their purpose is to reveal sensitivity to the conditioning choice.

The analysis cannot establish why assay coverage is uneven. The 98 original
reference compounds belong to this plant corpus, so the result does not measure
distance to all compounds with antifungal assay data. Expanding that reference can
change both the absolute distances and the observed-versus-null comparison.

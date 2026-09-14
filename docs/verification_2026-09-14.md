# Final verification — 14 September 2026

Checked code commit `4965b2911446af6416d14bedc2888c76caaa5b32`, including the
chemical-distance control calculations and the detection-variance experiment.
The final README edit updates the status date, links the eight-draw reader
comparison, and removes the stale statement that implementation files are untracked.

- The full suite against verified private original fixtures passed: **1,057 passed,
  zero failed, one skipped**. The skipped module requires the optional RDKit package,
  which is unavailable in this repository's `.venv`.
- Direct pytest against the public snapshot gave 1,031 passed, 26 failed and one
  skipped. The historical comparison tests require the original baseline hash;
  publication redaction changed `results/recall_baseline.json`. The private-fixture
  run passes the same unchanged test suite. No expectations or frozen inputs were edited.
- Five offline replays passed: the baseline and v6 samples 1–4. All 61 scientific
  artifact comparisons and baseline score comparisons matched. Private originals
  and frozen inputs remained unchanged.
- Independent detection-variance reconciliation passed again: 24 single-attempt
  calls, 24 distinct saved response-byte hashes, and matching baseline scores.
  This verification made zero model calls and preserved the original experiment reports.
- Ruff passed for detection-variance and chemical-distance source and tests.

Run the suite with its required private fixtures using:

```bash
.venv/bin/python -m scripts.publication_safety test
```

Run the scientific replay using:

```bash
.venv/bin/python -m scripts.publication_safety replay
```

These commands require the local private snapshot and prepared caches. A fresh
public clone has insufficient source data for these integration checks. The
chemical-distance RDKit measurement tests still need an environment with RDKit;
the successful suite result includes that explicit skip.

The [count-only verification record](../results/final_checks/summary.json) retains
these outcomes. Detailed verification evidence remains locally under
`results/final_checks/`; source text is excluded from the committed record.

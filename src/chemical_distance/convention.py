"""Thresholds this analysis adopts by convention rather than by derivation."""

DOMAIN_CONVENTION = 0.4
"""Tanimoto similarity below which a query compound is conventionally called
outside the applicability domain of a reference set.

This is a working convention in common use, not a property of chemistry. No
conclusion in this analysis depends on its exact value, and it never converts a
distance into a statement about activity.
"""

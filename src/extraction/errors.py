"""Failures that should halt extraction across all pending jobs."""


class ExtractionServiceUnavailable(RuntimeError):
    """A configuration, access or quota error prevents further model requests."""

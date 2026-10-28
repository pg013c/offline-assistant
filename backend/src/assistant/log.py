"""Structured logging setup (PY-15): one JSON object per event on stdout."""


def configure_logging(level: str = "info") -> None:
    """Configure structlog for the whole process."""
    raise NotImplementedError

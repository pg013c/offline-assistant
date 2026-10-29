from collections.abc import Callable
from typing import Protocol


class IngestionQueue(Protocol):
    """Runs ingestion jobs later, so an upload does not wait for parsing."""

    def submit(self, job: Callable[[], None]) -> None:
        """Queue a job; it runs after the jobs submitted before it."""
        ...

    def close(self) -> None:
        """Stop running jobs; called when the app shuts down."""
        ...

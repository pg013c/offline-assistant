"""Ingestion jobs on one worker thread: one parse holds model memory at a time."""

from collections.abc import Callable


class ThreadIngestionQueue:
    def submit(self, job: Callable[[], None]) -> None:
        raise NotImplementedError

    def close(self) -> None:
        """Finish queued jobs and stop the worker."""
        raise NotImplementedError

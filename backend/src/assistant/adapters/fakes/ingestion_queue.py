"""IngestionQueue fakes: one holds jobs until the test runs them, one runs them at once."""

from collections.abc import Callable


class FakeIngestionQueue:
    """Holds submitted jobs until `run_all`."""

    def __init__(self) -> None:
        self._jobs: list[Callable[[], None]] = []

    @property
    def pending(self) -> int:
        return len(self._jobs)

    def submit(self, job: Callable[[], None]) -> None:
        self._jobs.append(job)

    def run_all(self) -> None:
        while self._jobs:
            self._jobs.pop(0)()


class InlineIngestionQueue:
    """Runs each job as soon as it is submitted."""

    def submit(self, job: Callable[[], None]) -> None:
        job()

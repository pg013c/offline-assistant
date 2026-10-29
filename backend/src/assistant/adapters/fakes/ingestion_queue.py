"""IngestionQueue fakes: one holds jobs until the test runs them, one runs them at once."""

from collections.abc import Callable


class FakeIngestionQueue:
    """Holds submitted jobs until `run_all`."""

    def __init__(self) -> None:
        self._jobs: list[Callable[[], None]] = []

    @property
    def pending(self) -> int:
        raise NotImplementedError

    def submit(self, job: Callable[[], None]) -> None:
        raise NotImplementedError

    def run_all(self) -> None:
        raise NotImplementedError


class InlineIngestionQueue:
    """Runs each job as soon as it is submitted."""

    def submit(self, job: Callable[[], None]) -> None:
        raise NotImplementedError

"""Ingestion jobs on one worker thread: one parse holds model memory at a time."""

import queue
import threading
from collections.abc import Callable

import structlog

log = structlog.get_logger(__name__)


class ThreadIngestionQueue:
    def __init__(self) -> None:
        self._jobs: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._worker = threading.Thread(target=self._run, name="ingestion", daemon=True)
        self._worker.start()

    def submit(self, job: Callable[[], None]) -> None:
        self._jobs.put(job)

    def close(self) -> None:
        """Finish queued jobs and stop the worker."""
        self._jobs.put(None)
        self._worker.join()

    def _run(self) -> None:
        while (job := self._jobs.get()) is not None:
            try:
                job()
            except Exception:
                # A failed job must not stop the ones queued after it.
                log.exception("ingestion_job_failed")

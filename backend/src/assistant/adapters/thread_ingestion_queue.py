"""Ingestion jobs on one worker thread: one parse holds model memory at a time."""

import queue
import threading
from collections.abc import Callable

import structlog

log = structlog.get_logger(__name__)


class ThreadIngestionQueue:
    def __init__(self) -> None:
        self._jobs: queue.Queue[Callable[[], None]] = queue.Queue()
        self._stopping = threading.Event()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    def submit(self, job: Callable[[], None]) -> None:
        self._jobs.put(job)
        with self._lock:
            # The thread starts with the first job, so an app that never ingests has none.
            if self._worker is None and not self._stopping.is_set():
                self._worker = threading.Thread(target=self._run, name="ingestion", daemon=True)
                self._worker.start()

    def close(self) -> None:
        """Stop after the running job; queued jobs are dropped, as restore queues them again."""
        self._stopping.set()
        # Wake the worker if it waits for a job.
        self._jobs.put(lambda: None)
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join()

    def _run(self) -> None:
        while not self._stopping.is_set():
            job = self._jobs.get()
            if self._stopping.is_set():
                return
            try:
                job()
            except Exception:
                # A failed job must not stop the ones queued after it.
                log.exception("ingestion_job_failed")

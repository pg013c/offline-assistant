import threading
from collections.abc import Callable

from assistant.adapters.thread_ingestion_queue import ThreadIngestionQueue

WAIT_SECONDS = 5


def ingestion_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name == "ingestion"]


def test_jobs_run_one_at_a_time_in_order() -> None:
    queue = ThreadIngestionQueue()
    done: list[int] = []
    finished = threading.Event()
    running = 0
    most_at_once = 0
    lock = threading.Lock()

    def job(number: int) -> None:
        nonlocal running, most_at_once
        with lock:
            running += 1
            most_at_once = max(most_at_once, running)
        done.append(number)
        with lock:
            running -= 1
        if number == 4:
            finished.set()

    def job_for(number: int) -> Callable[[], None]:
        return lambda: job(number)

    for number in range(5):
        queue.submit(job_for(number))

    assert finished.wait(WAIT_SECONDS)
    queue.close()
    assert done == [0, 1, 2, 3, 4]
    assert most_at_once == 1


def test_a_failing_job_does_not_stop_the_next_ones() -> None:
    queue = ThreadIngestionQueue()
    finished = threading.Event()

    def fail() -> None:
        raise RuntimeError("boom")

    queue.submit(fail)
    queue.submit(finished.set)

    assert finished.wait(WAIT_SECONDS)
    queue.close()


def test_jobs_run_outside_the_submitting_thread() -> None:
    queue = ThreadIngestionQueue()
    threads: list[threading.Thread] = []
    finished = threading.Event()

    def record() -> None:
        threads.append(threading.current_thread())
        finished.set()

    queue.submit(record)

    assert finished.wait(WAIT_SECONDS)
    queue.close()
    assert threads != [threading.current_thread()]


def test_close_stops_after_the_running_job_and_drops_the_queued_ones() -> None:
    # Restore queues unfinished documents again, so nothing queued is lost.
    queue = ThreadIngestionQueue()
    started, release = threading.Event(), threading.Event()
    later: list[str] = []

    def slow() -> None:
        started.set()
        release.wait(WAIT_SECONDS)

    queue.submit(slow)
    queue.submit(lambda: later.append("ran"))
    assert started.wait(WAIT_SECONDS)
    closing = threading.Thread(target=queue.close)
    closing.start()
    # Let close ask the worker to stop before the running job ends.
    closing.join(0.05)
    release.set()
    closing.join(WAIT_SECONDS)

    assert not closing.is_alive()
    assert later == []


def test_no_worker_thread_starts_before_the_first_job() -> None:
    before = len(ingestion_threads())

    queue = ThreadIngestionQueue()

    assert len(ingestion_threads()) == before
    queue.close()

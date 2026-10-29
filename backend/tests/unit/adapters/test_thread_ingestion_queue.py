import threading
from collections.abc import Callable

from assistant.adapters.thread_ingestion_queue import ThreadIngestionQueue


def test_jobs_run_one_at_a_time_in_order() -> None:
    queue = ThreadIngestionQueue()
    done: list[int] = []
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

    def job_for(number: int) -> Callable[[], None]:
        return lambda: job(number)

    for number in range(5):
        queue.submit(job_for(number))
    queue.close()

    assert done == [0, 1, 2, 3, 4]
    assert most_at_once == 1


def test_a_failing_job_does_not_stop_the_next_ones() -> None:
    queue = ThreadIngestionQueue()
    done: list[str] = []

    def fail() -> None:
        raise RuntimeError("boom")

    queue.submit(fail)
    queue.submit(lambda: done.append("after"))
    queue.close()

    assert done == ["after"]


def test_jobs_run_outside_the_submitting_thread() -> None:
    queue = ThreadIngestionQueue()
    threads: list[threading.Thread] = []

    queue.submit(lambda: threads.append(threading.current_thread()))
    queue.close()

    assert threads != [threading.current_thread()]

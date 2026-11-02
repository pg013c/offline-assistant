"""The model server's peak memory (F-09b): finding the server and sampling it."""

import shutil
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from harness import memory
from harness.answers import AnswerCase, ChatResult, answers_markdown, score_answers
from harness.memory import (
    NotTheModelServer,
    PeakMemory,
    Process,
    find_server,
    footprint_bytes,
    mapped_bytes,
    peak_mib,
    sample,
)

MIB = 1024 * 1024


class FakeTable:
    """One listener on port 8080, whose memory reads come from a list; then it is gone."""

    def __init__(self, listener: Process | None, readings: list[int]) -> None:
        self.listener = listener
        self.readings: Iterator[int] = iter(readings)
        self.read_pids: list[int] = []

    def listening(self, port: int) -> Process | None:
        return self.listener if port == 8080 else None

    def memory_bytes(self, pid: int) -> int | None:
        self.read_pids.append(pid)
        return next(self.readings, None)


class FakeClock:
    """Stops the sampling after `ticks` waits, and records each wait."""

    def __init__(self, ticks: int) -> None:
        self.ticks = ticks
        self.waits: list[float] = []

    def stopped(self) -> bool:
        return len(self.waits) >= self.ticks

    def wait(self, seconds: float) -> None:
        self.waits.append(seconds)


SERVER = Process(4242, "llama-server")


def test_the_server_on_the_port_is_found() -> None:
    assert find_server(FakeTable(SERVER, []), 8080) == SERVER


def test_another_program_on_the_port_is_refused_by_name() -> None:
    with pytest.raises(NotTheModelServer, match=r"8080.*python3 \(pid 7\).*llama-server"):
        find_server(FakeTable(Process(7, "python3"), []), 8080)


def test_a_free_port_is_refused_naming_make_llm() -> None:
    with pytest.raises(NotTheModelServer, match=r"8080.*make llm"):
        find_server(FakeTable(None, []), 8080)


def test_the_server_is_read_once_a_second_until_the_run_stops_it() -> None:
    table = FakeTable(SERVER, [5000 * MIB, 5200 * MIB, 5100 * MIB, 9999 * MIB])
    clock = FakeClock(ticks=3)

    samples = sample(table, SERVER.pid, clock.stopped, clock.wait)

    assert samples == [5000 * MIB, 5200 * MIB, 5100 * MIB]
    assert clock.waits == [1.0, 1.0, 1.0]
    assert set(table.read_pids) == {SERVER.pid}


def test_a_server_that_ends_stops_the_sampling_and_its_samples_still_count() -> None:
    table = FakeTable(SERVER, [5000 * MIB, 6000 * MIB])

    samples = sample(table, SERVER.pid, FakeClock(ticks=10).stopped, FakeClock(ticks=10).wait)

    assert samples == [5000 * MIB, 6000 * MIB]
    assert peak_mib(samples, mapped=0) == 6000.0


def test_the_peak_is_the_largest_sample_plus_the_mapped_model_file_in_mib() -> None:
    samples = [800 * MIB, 1200 * MIB + MIB // 2, 900 * MIB]

    assert peak_mib(samples, mapped=19_000 * MIB) == pytest.approx(20_200.5)


def test_without_samples_there_is_no_peak() -> None:
    assert peak_mib([], mapped=19_000 * MIB) is None


def test_the_footprint_is_read_from_the_tools_byte_output() -> None:
    output = (
        "======================================================================\n"
        "llama-server [22756]: 64-bit    Footprint: 810614576 B (16384 bytes per page)\n"
        "======================================================================\n"
    )

    assert footprint_bytes(output) == 810_614_576


def test_an_ended_process_has_no_footprint() -> None:
    assert footprint_bytes("") is None


def test_the_mapped_bytes_are_the_size_of_the_served_model_file(tmp_path: Path) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"x" * 4096)

    assert mapped_bytes(str(model)) == 4096


@pytest.mark.parametrize("path", [None, "/nowhere/model.gguf"])
def test_an_unknown_model_file_is_refused_naming_props(path: str | None) -> None:
    with pytest.raises(NotTheModelServer, match="/props"):
        mapped_bytes(path)


def test_the_markdown_gives_the_peak_memory_in_whole_mib() -> None:
    answered = ChatResult(
        answer="Logs are kept [1].",
        cited=("d:1",),
        usage={},
        error=None,
        found=True,
        complete=True,
    )
    metrics = score_answers(
        [AnswerCase("en-a", "en", "answer", frozenset({"d:1"}))], {"en-a": answered}
    )
    metrics.performance["peak_memory_mib"] = 5200.6

    assert "| peak_memory_mib | 5201 |" in answers_markdown(metrics, {})


def test_a_tool_that_hangs_is_stopped_and_gives_no_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def hang(arguments: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        calls.append(options)
        raise subprocess.TimeoutExpired(arguments, options.get("timeout") or 0)

    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(subprocess, "run", hang)

    assert memory.SystemProcesses().memory_bytes(4242) is None
    assert calls[0]["timeout"] == memory.COMMAND_SECONDS


class StuckTable(FakeTable):
    """A server whose memory read never returns until released."""

    def __init__(self) -> None:
        super().__init__(SERVER, [])
        self.release = threading.Event()

    def memory_bytes(self, pid: int) -> int | None:
        self.release.wait()
        return None


def test_the_run_goes_on_when_the_sampler_does_not_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(memory, "JOIN_SECONDS", 0.1)
    table = StuckTable()
    peak = PeakMemory(table, 8080, mapped=0)
    peak.__enter__()
    leaving = threading.Thread(target=peak.__exit__, args=(None, None, None))

    leaving.start()
    leaving.join(timeout=2)
    finished = not leaving.is_alive()
    table.release.set()
    leaving.join()

    assert finished, "the run must not wait on a sampler that hangs"

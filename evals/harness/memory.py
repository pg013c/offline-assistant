"""Peak memory of the model server during an answer run (F-09b, FR-44).

The sampler finds the process listening on the model server's port, checks that it is
llama-server, and reads its memory once a second until the run stops it or the process ends.
"""

import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol

SERVER = "llama-server"
INTERVAL_SECONDS = 1.0


@dataclass(frozen=True)
class Process:
    pid: int
    name: str


class ProcessTable(Protocol):
    def listening(self, port: int) -> Process | None:
        """The process listening on the port, if any."""
        ...

    def memory_bytes(self, pid: int) -> int | None:
        """The process's memory in bytes; None once it has ended."""
        ...


class NotTheModelServer(Exception):
    """The port is free, or another program than llama-server listens on it."""


def find_server(table: ProcessTable, port: int) -> Process:
    """The llama-server listening on the port; anything else is not what the run measures."""
    process = table.listening(port)
    if process is None:
        raise NotTheModelServer(f"nothing listens on port {port}; start it with make llm")
    if process.name != SERVER:
        raise NotTheModelServer(
            f"port {port} is used by {process.name} (pid {process.pid}), not {SERVER}"
        )
    return process


def sample(
    table: ProcessTable,
    pid: int,
    stopped: Callable[[], bool],
    wait: Callable[[float], object],
) -> list[int]:
    """The process's memory, read every second until stopped or until the process ends."""
    samples: list[int] = []
    while not stopped():
        memory = table.memory_bytes(pid)
        if memory is None:
            break
        samples.append(memory)
        wait(INTERVAL_SECONDS)
    return samples


def peak_mb(samples: list[int]) -> float | None:
    """The largest sample in MB (1024 x 1024 bytes); None without samples."""
    return max(samples) / (1024 * 1024) if samples else None


class PeakMemory:
    """Samples the model server in a thread while the `with` block runs.

    The server is found when the object is made, so a wrong one fails the run before it starts.
    """

    def __init__(self, table: ProcessTable, port: int) -> None:
        self.table = table
        self.server = find_server(table, port)
        self._stop = threading.Event()
        self._samples: list[int] = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        self._samples = sample(self.table, self.server.pid, self._stop.is_set, self._stop.wait)

    def __enter__(self) -> "PeakMemory":
        self._thread.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._stop.set()
        self._thread.join()

    @property
    def peak_mb(self) -> float | None:
        return peak_mb(self._samples)


class SystemProcesses:
    """The process table of this machine, read with lsof and the system's own tools."""

    def listening(self, port: int) -> Process | None:
        # -F pc: one field per line, "p<pid>" then "c<command>".
        fields = _run("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-F", "pc").splitlines()
        pid = next((int(line[1:]) for line in fields if line.startswith("p")), None)
        name = next((line[1:] for line in fields if line.startswith("c")), None)
        return Process(pid, name) if pid is not None and name is not None else None

    def memory_bytes(self, pid: int) -> int | None:
        # Resident memory in KiB; empty once the process has ended.
        resident = _run("ps", "-o", "rss=", "-p", str(pid)).strip()
        return int(resident) * 1024 if resident else None


def _run(*arguments: str) -> str:
    executable = shutil.which(arguments[0])
    if executable is None:
        raise RuntimeError(f"{arguments[0]} is not installed or not on PATH")
    # Exit status 1 means no match (lsof) or no such process (ps).
    return subprocess.run(  # noqa: S603 (fixed commands)
        [executable, *arguments[1:]], capture_output=True, text=True, check=False
    ).stdout

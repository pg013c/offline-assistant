"""Peak memory of the model server during an answer run (F-09b, FR-44).

The sampler finds the process listening on the model server's port, checks that it is
llama-server, and reads its memory once a second until the run stops it or the process ends.

The memory is the server's physical footprint plus the model file it maps. Resident memory
would count the mapped file only while it stays resident, and macOS evicts its clean pages
under memory pressure: Qwen3.6 35B-A3B measured 10 GB of its 20 GB with the judge loaded.
"""

import re
import shutil
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Protocol

SERVER = "llama-server"
INTERVAL_SECONDS = 1.0
# How long one lsof or footprint call may take, and how long the run waits for the sampler
# to stop (AI-22, F-09b review #4).
COMMAND_SECONDS = 10.0
JOIN_SECONDS = 15.0
FOOTPRINT = re.compile(r"Footprint:\s*(\d+) B")


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


def peak_mib(samples: list[int], mapped: int) -> float | None:
    """The largest sample plus the mapped model file, in MiB (F-09b review #8)."""
    raise NotImplementedError


def peak_mb(samples: list[int], mapped: int) -> float | None:
    """The largest sample plus the mapped model file, in MB (1024 x 1024 bytes); None without
    samples."""
    return (max(samples) + mapped) / (1024 * 1024) if samples else None


class PeakMemory:
    """Samples the model server in a thread while the `with` block runs.

    The server is found when the object is made, so a wrong one fails the run before it starts.
    """

    def __init__(self, table: ProcessTable, port: int, mapped: int) -> None:
        self.table = table
        self.mapped = mapped
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
        # A sampler stuck in a tool call is left behind, and the run reports no peak.
        self._thread.join(timeout=JOIN_SECONDS)

    @property
    def peak_mb(self) -> float | None:
        return peak_mb(self._samples, mapped=self.mapped)


def footprint_bytes(output: str) -> int | None:
    """The physical footprint in the output of `footprint -f bytes`; None when it is empty."""
    match = FOOTPRINT.search(output)
    return int(match.group(1)) if match else None


def mapped_bytes(model_path: str | None) -> int:
    """The size of the model file the server maps, from the path its /props gives."""
    if model_path is None or not Path(model_path).is_file():
        raise NotTheModelServer(
            f"the model server's /props names no model file this machine has: {model_path}"
        )
    return Path(model_path).stat().st_size


class SystemProcesses:
    """The process table of this machine, read with lsof and the system's own tools."""

    def listening(self, port: int) -> Process | None:
        # -F pc: one field per line, "p<pid>" then "c<command>".
        fields = _run("lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-F", "pc").splitlines()
        pid = next((int(line[1:]) for line in fields if line.startswith("p")), None)
        name = next((line[1:] for line in fields if line.startswith("c")), None)
        return Process(pid, name) if pid is not None and name is not None else None

    def memory_bytes(self, pid: int) -> int | None:
        # The physical footprint; no figure once the process has ended.
        return footprint_bytes(_run("footprint", "-p", str(pid), "-f", "bytes", "--noCategories"))


def _run(*arguments: str) -> str:
    executable = shutil.which(arguments[0])
    if executable is None:
        raise RuntimeError(f"{arguments[0]} is not installed or not on PATH")
    # A failing status means no match (lsof) or no such process (footprint); a call that
    # hangs gives no output, as if there were no reading.
    try:
        return subprocess.run(  # noqa: S603 (fixed commands)
            [executable, *arguments[1:]],
            capture_output=True,
            text=True,
            check=False,
            timeout=COMMAND_SECONDS,
        ).stdout
    except subprocess.TimeoutExpired:
        return ""

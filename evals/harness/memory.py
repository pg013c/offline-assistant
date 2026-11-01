"""Peak memory of the model server during an answer run (F-09b, FR-44).

The sampler finds the process listening on the model server's port, checks that it is
llama-server, and reads its memory once a second until the run stops it or the process ends.
"""

from collections.abc import Callable
from dataclasses import dataclass
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
    raise NotImplementedError


def sample(
    table: ProcessTable,
    pid: int,
    stopped: Callable[[], bool],
    wait: Callable[[float], object],
) -> list[int]:
    raise NotImplementedError


def peak_mb(samples: list[int]) -> float | None:
    raise NotImplementedError


class SystemProcesses:
    """The process table of this machine, read with lsof and the system's own tools."""

    def listening(self, port: int) -> Process | None:
        raise NotImplementedError

    def memory_bytes(self, pid: int) -> int | None:
        raise NotImplementedError

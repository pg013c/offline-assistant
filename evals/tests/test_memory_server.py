"""The memory measure against a real llama-server (F-09b). Needs `make llm-models` and
llama.cpp; it starts its own server on a free port and stops it."""

import os
import re
import shutil
import signal
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from harness.memory import SystemProcesses, find_server, peak_mb, sample

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
MODELS_DIR = Path(os.environ.get("ASSISTANT_MODELS_DIR", ROOT / "data" / "models"))
MODEL = MODELS_DIR / "llm" / "Qwen--Qwen3-8B-GGUF" / "Qwen3-8B-Q4_K_M.gguf"
# The buffers llama-server allocates for the model, its cache and its computation.
BUFFER = re.compile(r"buffer size\s*=\s*([\d.]+) MiB")


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


@pytest.fixture
def server(tmp_path: Path) -> Iterator[tuple[int, Path]]:
    executable = shutil.which("llama-server")
    if executable is None or not MODEL.exists():
        pytest.skip("needs llama.cpp and make llm-models")
    port = free_port()
    log = tmp_path / "llama-server.log"
    with log.open("wb") as out:
        process = subprocess.Popen(  # noqa: S603 (fixed command)
            [
                executable,
                "-m",
                str(MODEL),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--n-gpu-layers",
                "99",
                "--ctx-size",
                "16384",
                "--jinja",
                "--reasoning",
                "off",
                # llama.cpp 0.8.0 logs the buffer sizes only from verbosity 4.
                "-lv",
                "4",
            ],
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        yield port, log
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=30)


def test_the_peak_memory_covers_the_buffers_llama_server_allocates(
    server: tuple[int, Path],
) -> None:
    port, log = server
    table = SystemProcesses()
    found = find_server(table, port)
    httpx.post(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "Count to twenty."}], "max_tokens": 64},
        timeout=120,
    ).raise_for_status()
    ticks = iter(range(3))

    peak = peak_mb(sample(table, found.pid, lambda: next(ticks, None) is None, time.sleep))

    buffers = sum(float(size) for size in BUFFER.findall(log.read_text(errors="replace")))
    assert buffers > 4000
    assert peak is not None
    assert peak >= 0.9 * buffers, f"peak {peak:.0f} MB, buffers {buffers:.0f} MiB"

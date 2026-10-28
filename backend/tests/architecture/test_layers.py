"""The layer rules of ADR 0002 are enforced by import-linter, and the enforcement works."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
CONFIG = BACKEND / "pyproject.toml"
PACKAGE = BACKEND / "src" / "assistant"
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


def lint_imports(source_root: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the project's import contracts against the `assistant` package under source_root."""
    environment = {**os.environ, "PYTHONPATH": str(source_root)}
    return subprocess.run(  # noqa: S603 - fixed executable and arguments, no user input
        [str(LINT_IMPORTS), "--config", str(CONFIG), "--no-cache", "--no-logo"],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def copy_package(tmp_path: Path) -> Path:
    source_root = tmp_path / "src"
    shutil.copytree(PACKAGE, source_root / "assistant")
    return source_root


def test_the_package_keeps_its_layer_contracts() -> None:
    result = lint_imports(BACKEND / "src", cwd=BACKEND)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Contracts: 0 kept" not in result.stdout


def test_a_service_importing_an_adapter_breaks_the_contract(tmp_path: Path) -> None:
    source_root = copy_package(tmp_path)
    violation = source_root / "assistant" / "services" / "_violation.py"
    violation.write_text("import assistant.adapters\n")

    result = lint_imports(source_root, cwd=tmp_path)

    assert result.returncode != 0
    assert "assistant.services._violation -> assistant.adapters" in result.stdout


def test_the_domain_importing_a_web_framework_breaks_the_contract(tmp_path: Path) -> None:
    source_root = copy_package(tmp_path)
    violation = source_root / "assistant" / "domain" / "_violation.py"
    violation.write_text("import fastapi\n")

    result = lint_imports(source_root, cwd=tmp_path)

    assert result.returncode != 0
    assert "assistant.domain._violation -> fastapi" in result.stdout


def test_a_service_importing_a_web_framework_breaks_the_contract(tmp_path: Path) -> None:
    source_root = copy_package(tmp_path)
    violation = source_root / "assistant" / "services" / "_violation.py"
    violation.write_text("import fastapi\n")

    result = lint_imports(source_root, cwd=tmp_path)

    assert result.returncode != 0
    assert "assistant.services._violation -> fastapi" in result.stdout


@pytest.mark.parametrize("module", ["settings", "openapi"])
def test_modules_outside_the_layers_may_not_import_adapters(tmp_path: Path, module: str) -> None:
    source_root = copy_package(tmp_path)
    module_file = source_root / "assistant" / f"{module}.py"
    module_file.write_text(module_file.read_text() + "\nimport assistant.adapters\n")

    result = lint_imports(source_root, cwd=tmp_path)

    assert result.returncode != 0
    assert f"assistant.{module} -> assistant.adapters" in result.stdout

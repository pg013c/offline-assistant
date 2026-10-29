"""The regression gate: no metric may get worse by more than 5 points (PRD §9)."""

from collections.abc import Mapping


def check(current: Mapping[str, float | None], baseline: Mapping[str, float | None]) -> list[str]:
    raise NotImplementedError

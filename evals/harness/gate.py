"""The regression gate: no metric may get worse by more than 5 points (PRD §9)."""

from collections.abc import Mapping

TOLERANCE_POINTS = 5
# Metrics where a rise, not a drop, is the regression.
LOWER_IS_BETTER = frozenset({"in_scope_unanswered"})


def check(current: Mapping[str, float | None], baseline: Mapping[str, float | None]) -> list[str]:
    """One message per metric that got worse by more than the tolerance; empty if none.

    Values are shares from 0 to 1; points are percentage points. Metrics without a value in
    either run are skipped.
    """
    failures = [
        f"{name} is in the baseline but missing from this run"
        for name in baseline
        if name not in current
    ]
    for name, now in current.items():
        before = baseline.get(name)
        if now is None or before is None:
            continue
        worse_by = (now - before) if name in LOWER_IS_BETTER else (before - now)
        if worse_by * 100 > TOLERANCE_POINTS + 1e-9:
            verb = "rose" if name in LOWER_IS_BETTER else "dropped"
            failures.append(
                f"{name} {verb} from {before * 100:.1f} to {now * 100:.1f} "
                f"(more than {TOLERANCE_POINTS} points)"
            )
    return failures


# The floors and ceiling of ADR 0020, whatever the baseline says.
FLOORS: dict[str, float] = {}
CEILINGS: dict[str, float] = {}


def below_floors(current: Mapping[str, float | None]) -> list[str]:
    """One message per floored metric below its floor, above its ceiling, or missing."""
    raise NotImplementedError


def gate_failures(
    current: Mapping[str, float | None],
    baseline: Mapping[str, float | None],
    *,
    floors: bool,
) -> list[str]:
    """Everything that fails the run: regressions, and with `floors` the ADR 0020 floors."""
    raise NotImplementedError

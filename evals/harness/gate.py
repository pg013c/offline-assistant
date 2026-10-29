"""The gate: no metric may get worse by more than 5 points (PRD §9) or cross its floor
(ADR 0020)."""

from collections.abc import Mapping

TOLERANCE_POINTS = 5
# Metrics where a rise, not a drop, is the regression.
LOWER_IS_BETTER = frozenset({"in_scope_unanswered", "answer_failed"})


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
FLOORS: dict[str, float] = {
    "answerable@3": 0.85,
    "recall@3": 0.85,
    "recall@10": 0.95,
    "mrr": 0.75,
    "out_of_scope_refused": 0.90,
}
CEILINGS: dict[str, float] = {"in_scope_unanswered": 0.05}


def below_floors(current: Mapping[str, float | None]) -> list[str]:
    """One message per floored metric below its floor, above its ceiling, or missing."""
    failures = []
    for name, limit in {**FLOORS, **CEILINGS}.items():
        now = current.get(name)
        if now is None:
            failures.append(f"{name} has no value, so its floor cannot be checked (ADR 0020)")
        elif name in FLOORS and now < limit - 1e-9:
            failures.append(
                f"{name} is {_value(name, now)}, below its floor of "
                f"{_value(name, limit)} (ADR 0020)"
            )
        elif name in CEILINGS and now > limit + 1e-9:
            failures.append(
                f"{name} is {_value(name, now)}, above its ceiling of "
                f"{_value(name, limit)} (ADR 0020)"
            )
    return failures


def gate_failures(
    current: Mapping[str, float | None],
    baseline: Mapping[str, float | None],
    *,
    floors: bool,
) -> list[str]:
    """Everything that fails the run: regressions, and with `floors` the ADR 0020 floors."""
    return check(current, baseline) + (below_floors(current) if floors else [])


def _value(name: str, value: float) -> str:
    # MRR is a mean of reciprocal ranks, not a share.
    return f"{value:.3f}" if name == "mrr" else f"{value * 100:.1f}"

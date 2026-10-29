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
    failures = []
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

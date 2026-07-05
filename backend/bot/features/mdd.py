"""Maximum drawdown (MDD) metric — a bot-only feature.

Pure computation used by the ``/mdd`` command. The LS data fetching and the
Telegram glue live in ``bot.main`` alongside the other command handlers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass
class MDDResult:
    """Result of a maximum-drawdown computation.

    Attributes:
        mdd_pct: Maximum drawdown as a non-positive percentage (0.0 when the
            series never falls below its running peak).
        peak_idx: Index of the running peak that precedes the worst trough.
        trough_idx: Index of the worst trough (``>= peak_idx``).
    """

    mdd_pct: float
    peak_idx: int
    trough_idx: int


def max_drawdown(closes: Sequence[float]) -> MDDResult:
    """Maximum drawdown over a chronological close series.

    Drawdown at each point is ``(price - running_peak) / running_peak``; MDD is
    the most negative such value. The caller must pass ``closes`` in
    chronological order (oldest first) — drawdown is order-dependent.

    Raises:
        ValueError: if ``closes`` is empty.
    """
    if not closes:
        raise ValueError("closes is empty")

    peak = closes[0]
    peak_idx = 0
    result = MDDResult(0.0, 0, 0)
    for i, price in enumerate(closes):
        if price > peak:
            peak = price
            peak_idx = i
        if peak > 0:
            dd = (price - peak) / peak * 100.0
            if dd < result.mdd_pct:
                result = MDDResult(dd, peak_idx, i)
    return result

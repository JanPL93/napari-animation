"""Lightweight performance logging for animation rendering.

The :class:`PerfLogger` accumulates wall-clock time spent in named phases of
the render/encode pipeline (interpolation, applying viewer state, taking the
screenshot, encoding/writing) so it is easy to see which step is rate
limiting. It is intentionally dependency-free and cheap when disabled.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from contextlib import contextmanager

#: Module logger; configure napari_animation's logger to see perf output.
logger = logging.getLogger("napari_animation")


class PerfLogger:
    """Accumulate and report per-phase timings of a render pipeline."""

    def __init__(self, enabled: bool = True, log: logging.Logger = logger):
        self.enabled = enabled
        self._logger = log
        self._totals: "OrderedDict[str, float]" = OrderedDict()
        self._counts: "OrderedDict[str, int]" = OrderedDict()
        self._wall_start: float = None

    def start(self) -> None:
        """Mark the start of the overall timed region."""
        self._wall_start = time.perf_counter()

    def reset(self) -> None:
        self._totals.clear()
        self._counts.clear()
        self._wall_start = None

    def record(self, name: str, dt: float) -> None:
        """Add ``dt`` seconds to the running total for phase ``name``."""
        self._totals[name] = self._totals.get(name, 0.0) + dt
        self._counts[name] = self._counts.get(name, 0) + 1

    @contextmanager
    def timer(self, name: str):
        """Context manager that records elapsed time under phase ``name``."""
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, time.perf_counter() - start)

    def report(self) -> str:
        """Return a human-readable summary of accumulated timings."""
        lines = ["napari-animation performance summary:"]
        phase_total = sum(self._totals.values()) or 1e-9
        for name, total in self._totals.items():
            count = self._counts[name]
            mean_ms = (total / count) * 1000 if count else 0.0
            pct = 100 * total / phase_total
            lines.append(
                f"  {name:<12} total={total:7.2f}s  "
                f"mean={mean_ms:7.1f}ms  n={count:<5d} {pct:5.1f}%"
            )
        if self._wall_start is not None:
            wall = time.perf_counter() - self._wall_start
            lines.append(f"  {'wall-clock':<12} total={wall:7.2f}s")
        return "\n".join(lines)

    def log_report(self, level: int = logging.INFO) -> str:
        """Log (and return) the timing report; no-op if disabled/empty."""
        text = self.report()
        if self.enabled and self._totals:
            self._logger.log(level, text)
        return text

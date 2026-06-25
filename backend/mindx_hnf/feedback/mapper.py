"""Feedback mapping and sham provider."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from mindx_hnf.contracts import FeedbackMode, FeedbackSample, INSSample


class ShamProvider:
    """Yields prerecorded INS values from another dyad for the same session/task.

    Sham is NOT noise and NOT a constant — it is a real other-dyad trajectory,
    so it has realistic temporal statistics and reward structure. This controls
    for reward and unrelated training effects (WP4). The recording is loaded from
    the artifact store keyed by (session, task); here it is injected as an
    iterable so it is trivially testable and deterministic.
    """

    def __init__(self, recorded_values: list[float]) -> None:
        if not recorded_values:
            raise ValueError("Sham provider requires a non-empty recorded trace.")
        self._values = recorded_values
        self._it: Iterator[float] = iter(self._values)

    def next_value(self) -> float:
        try:
            return next(self._it)
        except StopIteration:
            # Loop the trace if the sham run outlasts the recording.
            self._it = iter(self._values)
            return next(self._it)

    def reset(self) -> None:
        self._it = iter(self._values)


class BaselineSmoothingMapper:
    """Implements the FeedbackMapper protocol.

    1. Baseline-correct against the running mean of the resting block.
    2. Normalize to [0, 1] using a configurable gain.
    3. Exponentially smooth to avoid jittery game feel.
    4. Clamp.

    In sham mode the *raw INS value is swapped for the sham provider's value
    BEFORE this mapping*, so steps 1-4 are byte-for-byte identical across modes.
    """

    def __init__(
        self,
        *,
        sham: ShamProvider | None = None,
        smoothing: float = 0.3,
        gain: float = 1.0,
        baseline_window: int = 64,
    ) -> None:
        self.sham = sham
        self.smoothing = smoothing
        self.gain = gain
        self._baseline = deque(maxlen=baseline_window)
        self._smoothed = 0.0
        self._baseline_locked = False
        self._baseline_value = 0.0

    def lock_baseline(self) -> None:
        """Freeze the baseline at the end of the resting block."""
        if self._baseline:
            self._baseline_value = sum(self._baseline) / len(self._baseline)
        self._baseline_locked = True

    def observe_baseline(self, ins: INSSample) -> None:
        """Feed resting-block INS values to establish the baseline."""
        if not self._baseline_locked:
            self._baseline.append(ins.value)

    def map(self, ins: INSSample, mode: FeedbackMode) -> FeedbackSample:
        if mode is FeedbackMode.SHAM:
            if self.sham is None:
                raise RuntimeError("Sham mode requested but no ShamProvider set.")
            raw = self.sham.next_value()
        else:
            raw = ins.value

        baseline = self._baseline_value if self._baseline_locked else 0.0
        corrected = max(0.0, (raw - baseline)) * self.gain
        self._smoothed = (
            self.smoothing * corrected + (1 - self.smoothing) * self._smoothed
        )
        level = min(1.0, max(0.0, self._smoothed))
        return FeedbackSample(
            t_lsl=ins.t_lsl, level=level, mode=mode, raw_ins=raw
        )

    def reset(self) -> None:
        self._baseline.clear()
        self._smoothed = 0.0
        self._baseline_locked = False
        self._baseline_value = 0.0
        if self.sham is not None:
            self.sham.reset()

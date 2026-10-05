"""Feedback mapping and sham provider.

``BaselineSmoothingMapper`` turns raw INS into the delivered feedback level;
``ShamProvider`` supplies the replayed other-dyad signal for sham sessions (D5).
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from mindx_hnf.contracts import (
    FeedbackMode,
    FeedbackSample,
    INSSample,
    SessionMode,
    SubjectId,
)


class ShamProvider:
    """Yields prerecorded INS values from another dyad for the same session/task.

    Sham is NOT noise and NOT a constant — it is a real other-dyad trajectory,
    so it has realistic temporal statistics and reward structure. This controls
    for reward and unrelated training effects (WP4). The recording is loaded from
    the artifact store keyed by (session, task); here it is injected as an
    iterable so it is trivially testable and deterministic.
    """

    def __init__(self, recorded_values: list[float]) -> None:
        """Create a provider that replays a recorded INS trace.

        Args:
            recorded_values: Another dyad's INS trace for the same
                session/task, in delivery order.

        Raises:
            ValueError: If ``recorded_values`` is empty.
        """
        if not recorded_values:
            raise ValueError("Sham provider requires a non-empty recorded trace.")
        self._values = recorded_values
        self._it: Iterator[float] = iter(self._values)

    def next_value(self) -> float:
        """Return the next recorded value, looping the trace when exhausted.

        Returns:
            The next INS value of the replayed trace.
        """
        try:
            return next(self._it)
        except StopIteration:
            # Loop the trace if the sham run outlasts the recording.
            self._it = iter(self._values)
            return next(self._it)

    def reset(self) -> None:
        """Restart replay from the beginning of the trace."""
        self._it = iter(self._values)


class BaselineSmoothingMapper:
    """Implements the FeedbackMapper protocol.

    1. Baseline-correct against the running mean of the resting block.
    2. Normalize to [0, 1] using a configurable gain.
    3. Exponentially smooth to avoid jittery game feel.
    4. Clamp.

    In sham mode the *raw INS value is swapped for the sham provider's value
    BEFORE this mapping*, so steps 1-4 are byte-for-byte identical across modes.

    A mapper instance belongs to exactly one session mode (D8). In HYPERSCANNING
    a single mapper produces the one shared-car sample (`subject=None`). In
    INDIVIDUAL each subject gets its OWN mapper (own baseline + smoothing state)
    constructed with that subject's id, so the per-subject cars stay independent.
    The mapping math is unchanged either way — `session_mode`/`subject` are only
    stamped onto the output for routing and provenance.

    Attributes:
        sham: Source of the replayed signal in sham mode, if any.
        smoothing: Exponential-smoothing weight of the newest value, in (0, 1].
        gain: Multiplier applied to the baseline-corrected value.
        session_mode: Paradigm stamped onto every output sample (D8).
        subject: Owning subject in Individual mode, None in Hyperscanning.
    """

    def __init__(
        self,
        *,
        sham: ShamProvider | None = None,
        smoothing: float = 0.3,
        gain: float = 1.0,
        baseline_window: int = 64,
        session_mode: SessionMode = SessionMode.HYPERSCANNING,
        subject: SubjectId | None = None,
    ) -> None:
        """Create a mapper for one session mode (and one subject if Individual).

        Args:
            sham: Replayed other-dyad signal; required to map in sham mode.
            smoothing: Exponential-smoothing weight of the newest value.
            gain: Multiplier applied to the baseline-corrected value.
            baseline_window: Number of resting-block INS values averaged into
                the baseline.
            session_mode: Paradigm this mapper serves (D8).
            subject: The car owner in Individual mode; must be None in
                Hyperscanning.

        Raises:
            ValueError: If ``subject`` is set in Hyperscanning mode or missing
                in Individual mode.
        """
        if session_mode is SessionMode.HYPERSCANNING and subject is not None:
            raise ValueError(
                "Hyperscanning mode drives one shared car; subject must be None."
            )
        if session_mode is SessionMode.INDIVIDUAL and subject is None:
            raise ValueError(
                "Individual mode drives a per-subject car; subject is required."
            )
        self.sham = sham
        self.smoothing = smoothing
        self.gain = gain
        self.session_mode = session_mode
        self.subject = subject
        self._baseline: deque[float] = deque(maxlen=baseline_window)
        self._smoothed = 0.0
        self._baseline_locked = False
        self._baseline_value = 0.0

    def lock_baseline(self) -> None:
        """Freeze the baseline at the end of the resting block."""
        if self._baseline:
            self._baseline_value = sum(self._baseline) / len(self._baseline)
        self._baseline_locked = True

    def observe_baseline(self, ins: INSSample) -> None:
        """Feed a resting-block INS value to establish the baseline.

        Ignored once the baseline is locked.

        Args:
            ins: An INS sample observed during the baseline block.
        """
        if not self._baseline_locked:
            self._baseline.append(ins.value)

    def map(self, ins: INSSample, mode: FeedbackMode) -> FeedbackSample:
        """Baseline-correct, scale, smooth and clamp one INS value.

        In sham mode the raw value is replaced by the sham provider's value
        before mapping, so the mapping itself is identical across modes.

        Args:
            ins: The real dyad's INS sample (its timestamp is kept in sham).
            mode: Real or sham.

        Returns:
            The feedback sample with ``level`` in [0, 1].

        Raises:
            RuntimeError: If sham mode is requested without a ``ShamProvider``.
        """
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
            t_lsl=ins.t_lsl,
            level=level,
            mode=mode,
            raw_ins=raw,
            session_mode=self.session_mode,
            subject=self.subject,
        )

    def reset(self) -> None:
        """Clear baseline, smoothing and sham-replay state."""
        self._baseline.clear()
        self._smoothed = 0.0
        self._baseline_locked = False
        self._baseline_value = 0.0
        if self.sham is not None:
            self.sham.reset()

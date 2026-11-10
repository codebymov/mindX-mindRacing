"""Individual-mode DEMO PLACEHOLDER: one feedback signal per player.

This does NOT decide open question O7 (the real per-subject neurofeedback feature,
where it is computed and how it is normalised). It exists so a demo can show two
cars with different speeds, each driven by its own player's synthetic signal.

The placeholder feature is the causal, windowed in-band (0.01-0.1 Hz) power of that
player's own channel-averaged HbO. Each player has their own synthetic activation
profile, so the two signals differ. Each player has their own baseline and mapper
(``SessionMode.INDIVIDUAL``), and one ``FeedbackSample`` per player is published per
feedback tick; the game routes them by subject index.

Run with ``python -m mindx_hnf.scripts.simulate --individual ...``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np

from mindx_hnf.api.sink import FeedbackSink, NullSink
from mindx_hnf.contracts import (
    BlockType,
    FeedbackMode,
    HemoFrame,
    INSSample,
    SessionMode,
    SubjectId,
)
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper
from mindx_hnf.io.sources import SyntheticSource
from mindx_hnf.preprocessing.montage import load_montage
from mindx_hnf.preprocessing.online import OnlineHemoPipeline
from mindx_hnf.scripts.simulate import COHERENCE_LOW, coherence_profile
from mindx_hnf.session.protocol import Block, SessionPlan, SessionScheduler

logger = logging.getLogger(__name__)

#: Demo gain per path. Measured offline (22 s window): the feature rises about 80x
#: from baseline to the first player's task plateau (1e-5 -> 8e-4 generic path,
#: 0.018 -> 0.2 on the MNE montage path), so these gains put that plateau near 0.8-0.9.
INDIVIDUAL_GAIN = 1000.0
INDIVIDUAL_MONTAGE_GAIN = 5.0
#: The second player's activation is this fraction of the first player's.
SECOND_PLAYER_AMPLITUDE = 0.75


class BandPowerFeature:
    """Causal windowed in-band power of each subject's own channel-mean HbO.

    Demo placeholder for the per-subject feature of O7 (open).

    Attributes:
        subjects: The subjects, in output order.
        fs: Sampling rate in Hz.
        band: Frequency band in Hz.
        window_n: Window length in samples.
    """

    def __init__(
        self,
        subjects: tuple[SubjectId, ...],
        fs: float,
        window_s: float = 22.0,
        update_every_s: float = 1.0,
        band: tuple[float, float] = (0.01, 0.1),
    ) -> None:
        """Create the feature extractor.

        Args:
            subjects: The subjects to track.
            fs: Sampling rate in Hz.
            window_s: Window length in seconds.
            update_every_s: Minimum interval between emitted values.
            band: Frequency band in Hz.
        """
        self.subjects = subjects
        self.fs = fs
        self.band = band
        self.window_n = round(window_s * fs)
        self._update_n = max(1, round(update_every_s * fs))
        self._buf = {s: np.zeros(self.window_n) for s in subjects}
        self._filled = 0
        self._since = 0
        self._taper = np.hanning(self.window_n)
        freqs = np.fft.rfftfreq(self.window_n, d=1.0 / fs)
        self._mask = (freqs >= band[0]) & (freqs <= band[1])
        if not self._mask.any():
            self._mask = freqs > 0

    def update(self, frame: HemoFrame) -> dict[SubjectId, INSSample] | None:
        """Push a frame and return one value per subject when an update is due.

        Args:
            frame: Preprocessed hemodynamics.

        Returns:
            One ``INSSample`` per subject, or None until the window is full and an
            update is due.
        """
        for s in self.subjects:
            chunk = np.asarray(frame.hbo[s], dtype=float).mean(axis=0)
            k = chunk.shape[0]
            buf = self._buf[s]
            buf[:-k] = buf[k:]
            buf[-k:] = chunk
        self._filled = min(self.window_n, self._filled + chunk.shape[0])
        self._since += chunk.shape[0]
        if self._filled < self.window_n or self._since < self._update_n:
            return None
        self._since = 0
        out: dict[SubjectId, INSSample] = {}
        for s in self.subjects:
            x = self._buf[s] - self._buf[s].mean()
            spec = np.abs(np.fft.rfft(x * self._taper)) ** 2 / np.sum(self._taper**2)
            out[s] = INSSample(
                t_lsl=frame.t_lsl,
                value=float(spec[self._mask].mean()),
                estimator="demo-band-power",
            )
        return out


def subject_profiles(
    plan: SessionPlan, subjects: tuple[SubjectId, SubjectId]
) -> dict[SubjectId, Callable[[float], float]]:
    """Give each player their own synthetic activation profile.

    The first player follows the plan's ramps. The second starts later, ramps more
    slowly and peaks lower, so the two signals (and cars) clearly differ.

    Args:
        plan: The session plan.
        subjects: The two players.

    Returns:
        Subject id to a function of session time giving that player's activation.
    """
    first = coherence_profile(plan)
    task = max(b.duration_s for b in plan.blocks if b.feedback)
    later = coherence_profile(plan, delay_s=0.1 * task, ramp_fraction=0.8)

    def second(t_s: float) -> float:
        return COHERENCE_LOW + SECOND_PLAYER_AMPLITUDE * (later(t_s) - COHERENCE_LOW)

    return {subjects[0]: first, subjects[1]: second}


class IndividualDemoLoop:
    """Closed loop with one feedback signal per player (demo placeholder).

    Attributes:
        n_frames: Frames processed in the last run.
        n_feedback: Feedback samples published in the last run (both players).
    """

    def __init__(
        self,
        source: SyntheticSource,
        preprocessor: OnlineHemoPipeline,
        feature: BandPowerFeature,
        mappers: dict[SubjectId, BaselineSmoothingMapper],
        sink: FeedbackSink,
        scheduler: SessionScheduler,
    ) -> None:
        """Wire the stages; nothing runs until ``run``.

        Args:
            source: Synthetic frame source.
            preprocessor: Causal per-subject preprocessing.
            feature: Per-subject feature extractor.
            mappers: One mapper per subject.
            sink: Feedback transport; closed when the run ends.
            scheduler: Block schedule.
        """
        self.source = source
        self.preprocessor = preprocessor
        self.feature = feature
        self.mappers = mappers
        self.sink = sink
        self.scheduler = scheduler
        self.n_frames = 0
        self.n_feedback = 0

    def run(self) -> None:
        """Run until the source ends or the session is finished."""
        t0: float | None = None
        locked = False
        try:
            for frame in self.source.frames():
                if t0 is None:
                    t0 = frame.t_lsl
                elapsed = frame.t_lsl - t0
                block = self.scheduler.current_block(elapsed)
                if block is None and self.scheduler.is_finished(elapsed):
                    break
                if not locked and (
                    block is None or block.kind is not BlockType.BASELINE
                ):
                    self.preprocessor.lock_baseline()
                    locked = True
                values = self.feature.update(self.preprocessor.process(frame))
                self.n_frames += 1
                if values is None:
                    continue
                if block is not None and block.kind is BlockType.BASELINE:
                    for s, sample in values.items():
                        self.mappers[s].observe_baseline(sample)
                elif block is not None and block.feedback:
                    for s, sample in values.items():
                        mapper = self.mappers[s]
                        if not mapper._baseline_locked:
                            mapper.lock_baseline()
                        self.sink.publish(mapper.map(sample, FeedbackMode.REAL))
                        self.n_feedback += 1
        finally:
            self.sink.close()


def build_individual_demo(
    fast: bool = True,
    sink: FeedbackSink | None = None,
    montage: str | Path | None = None,
) -> tuple[IndividualDemoLoop, FeedbackSink]:
    """Assemble the Individual-mode demo loop on synthetic data.

    Args:
        fast: Scale block durations to 5% for a quick run.
        sink: Feedback transport; a ``NullSink`` is used if None.
        montage: Optional montage YAML (the MNE preprocessing path).

    Returns:
        The ready-to-run loop and its sink.
    """
    fs = 7.81
    subjects: tuple[SubjectId, SubjectId] = ("sub-01", "sub-02")
    n_channels = 20
    scale = 0.05 if fast else 1.0
    plan = SessionPlan(
        label="individual-demo",
        mode=FeedbackMode.REAL,
        blocks=[
            Block(BlockType.BASELINE, 60 * scale),
            Block(BlockType.TASK, 120 * scale, feedback=True),
            Block(BlockType.REST, 10 * scale),
            Block(BlockType.TASK, 120 * scale, feedback=True),
        ],
    )
    mont = load_montage(montage) if montage is not None else None
    source = SyntheticSource(
        n_channels=n_channels,
        fs=fs,
        subjects=subjects,
        coherence_fn=coherence_profile(plan),
        subject_coherence_fn=subject_profiles(plan, subjects),
        duration_s=plan.total_seconds + 2,
        montage=mont,
    )
    pre = OnlineHemoPipeline(subjects, n_channels, fs, montage=mont)
    feature = BandPowerFeature(
        subjects, fs, window_s=20.0 * scale + 2, update_every_s=1.0
    )
    gain = INDIVIDUAL_MONTAGE_GAIN if mont is not None else INDIVIDUAL_GAIN
    mappers = {
        s: BaselineSmoothingMapper(
            smoothing=0.3,
            gain=gain,
            session_mode=SessionMode.INDIVIDUAL,
            subject=s,
        )
        for s in subjects
    }
    out_sink: FeedbackSink = sink if sink is not None else NullSink()
    loop = IndividualDemoLoop(
        source, pre, feature, mappers, out_sink, SessionScheduler(plan)
    )
    return loop, out_sink

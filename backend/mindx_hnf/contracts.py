"""Core contracts shared across the real-time pipeline.

These are the *typed seams* between stages. Every stage consumes and produces
one of these dataclasses/protocols. New implementations (a new INS estimator, a
new preprocessing step, a new feedback mapping) are validated by conforming to
these protocols — this is the project's equivalent of an IR contract.

Keep this module dependency-light: numpy only. No I/O, no heavy imports.

Attributes:
    SubjectId: Pseudonymized subject identifier, e.g. ``"sub-01"``.
    DyadId: Pseudonymized dyad identifier, e.g. ``"dyad-07"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

import numpy as np

# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #
SubjectId = str  # pseudonymized, e.g. "sub-01"
DyadId = str  # pseudonymized, e.g. "dyad-07"


class Chromophore(str, Enum):
    """Hemoglobin chromophores resolved by the modified Beer-Lambert law."""

    HBO = "hbo"
    HBR = "hbr"


class BlockType(str, Enum):
    """Experiment block types (see session/protocol)."""

    REST = "rest"
    TASK = "task"
    BASELINE = "baseline"  # task-free movie (inscapes)
    TRANSFER = "transfer"  # exchange game, screen-based, no feedback


class FeedbackMode(str, Enum):
    """Source of the delivered feedback signal (D5).

    ``SHAM`` replays another dyad's real signal for the same session/task. The
    value is recorded for analysis only; the participant-facing path is
    identical for both modes.
    """

    REAL = "real"
    SHAM = "sham"  # replays another dyad's signal for the same session/task


class SessionMode(str, Enum):
    """Which neurofeedback paradigm a session runs (see DECISIONS.md D8).

    This is orthogonal to FeedbackMode (real/sham): a session runs in exactly
    ONE SessionMode, and every delivered sample — real or sham — is stamped with
    it. It selects *what signal drives the cars*, not whether the signal is
    genuine.
    """

    #: One joint INS signal drives BOTH cars together (the core science of D7).
    #: FeedbackSample.subject is None — there is one shared dyad signal.
    HYPERSCANNING = "hyperscanning"
    #: Each car is driven by that player's OWN per-subject neurofeedback (NOT
    #: interpersonal synchrony). Each delivered sample carries a `subject`.
    INDIVIDUAL = "individual"


# --------------------------------------------------------------------------- #
# Real-time frames
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class RawFrame:
    """A time-synced chunk of multimodal samples from BOTH subjects.

    Assembled by `io` from the individual LSL streams. Channel axis ordering
    is fixed by the montage in the run config.

    Attributes:
        t_lsl: LSL clock timestamp of the chunk (the single clock of record).
        fnirs: Per subject, raw optical intensities of shape
            ``(n_channels, n_samples)``.
        aux: Per subject, ECG/EDA/accelerometer samples of shape
            ``(n_aux_channels, n_samples)``.
        fs: Sampling rate in Hz.
    """

    t_lsl: float
    fnirs: dict[SubjectId, np.ndarray]
    aux: dict[SubjectId, np.ndarray] = field(default_factory=dict)
    fs: float = 0.0  # sampling rate (Hz)


@dataclass(slots=True)
class HemoFrame:
    """Per-subject preprocessed hemodynamics after the online pipeline.

    Already motion-corrected, bandpassed, short-channel-regressed — all
    causally.

    Attributes:
        t_lsl: LSL clock timestamp of the source chunk.
        hbo: Per subject, Δ[HbO] in micromolar, shape ``(n_channels, n_samples)``.
        hbr: Per subject, Δ[HbR] in micromolar, shape ``(n_channels, n_samples)``.
        fs: Sampling rate in Hz.
    """

    t_lsl: float
    hbo: dict[SubjectId, np.ndarray]
    hbr: dict[SubjectId, np.ndarray]
    fs: float


@dataclass(slots=True)
class INSSample:
    """A single interpersonal-neural-synchrony value at time t.

    Attributes:
        t_lsl: LSL clock timestamp the value refers to.
        value: Raw estimator output (e.g. mean wavelet coherence) in [0, 1].
        per_channel: Optional channel-resolved coherence for logging and
            offline analysis; it must NOT be required by the feedback stage.
        estimator: Name of the estimator that produced the value (provenance).
    """

    t_lsl: float
    value: float
    per_channel: np.ndarray | None = None
    estimator: str = ""


@dataclass(slots=True)
class FeedbackSample:
    """The signal actually delivered to the XR game.

    ``session_mode`` and ``subject`` route the sample to the right car(s) (D8):
    in HYPERSCANNING one joint signal drives both cars and ``subject`` is None;
    in INDIVIDUAL the sample is per-subject neurofeedback and ``subject`` names
    the car's owner. Neither field may be branched on anywhere a participant
    could perceive a difference — the sham hard-rule applies to every session
    mode.

    Attributes:
        t_lsl: LSL clock timestamp of the sample (one clock of record).
        level: Normalized, baseline-corrected, smoothed value in [0, 1] that the
            game maps onto car speed and audio pitch/gain.
        mode: Whether the source was real or sham — for logging only; the
            participant-facing path is identical for both.
        raw_ins: The INS value before mapping, for logging.
        session_mode: Which paradigm produced the sample (D8).
        subject: Owning subject in Individual mode, None in Hyperscanning.
    """

    t_lsl: float
    level: float
    mode: FeedbackMode
    raw_ins: float
    session_mode: SessionMode = SessionMode.HYPERSCANNING
    subject: SubjectId | None = None


# --------------------------------------------------------------------------- #
# Stage protocols (the seams)
# --------------------------------------------------------------------------- #
@runtime_checkable
class OnlinePreprocessor(Protocol):
    """Causal, streaming per-subject fNIRS preprocessing.

    `process` is called once per incoming RawFrame and may keep internal state
    (filter delay lines, baseline buffers). It must use only past/current
    samples — no future lookahead, no zero-phase filtering.
    """

    def process(self, frame: RawFrame) -> HemoFrame:
        """Preprocess one frame causally.

        Args:
            frame: The next time-synced raw chunk from both subjects.

        Returns:
            Per-subject hemodynamics for the same chunk.
        """
        ...

    def reset(self) -> None:
        """Clear all internal state, as if no frame had been processed."""
        ...


@runtime_checkable
class BaselineLockable(Protocol):
    """A stage whose reference is established during the baseline block, then frozen.

    The orchestrator calls `lock_baseline` once, at the first frame after the
    baseline block (or the first frame at all if the protocol has none).
    """

    @property
    def baseline_locked(self) -> bool:
        """Whether the reference has been frozen."""
        ...

    def lock_baseline(self) -> None:
        """Freeze the reference established during the baseline block."""
        ...


@runtime_checkable
class INSEstimator(Protocol):
    """Computes a single joint INS value from both subjects' hemodynamics.

    Implementations live in `ins/`. They are windowed and run-time efficient.

    Attributes:
        name: Stamped into ``INSSample.estimator`` for provenance.
    """

    name: str

    def update(self, frame: HemoFrame) -> INSSample | None:
        """Push a frame and return a new INS value when one is ready.

        Args:
            frame: Preprocessed hemodynamics of both subjects.

        Returns:
            The new INS sample, or None if no update is due yet.
        """
        ...

    def reset(self) -> None:
        """Clear the window and update counters."""
        ...


@runtime_checkable
class FeedbackMapper(Protocol):
    """Maps raw INS to the delivered feedback level.

    Handles baseline correction, smoothing, clamping, and sham substitution.
    The mapping itself is deterministic and unit-tested; it is the part of the
    'game feel' that lives in the (testable) backend rather than in Unity.
    """

    def map(self, ins: INSSample, mode: FeedbackMode) -> FeedbackSample:
        """Map one INS value to the delivered feedback sample.

        Args:
            ins: The raw INS sample of the real dyad.
            mode: Real or sham; selects only the signal source, never the
                participant-facing path.

        Returns:
            The feedback sample to publish to the game.
        """
        ...

    def reset(self) -> None:
        """Clear baseline, smoothing and sham-replay state."""
        ...

"""Core contracts shared across the real-time pipeline.

These are the *typed seams* between stages. Every stage consumes and produces
one of these dataclasses/protocols. New implementations (a new INS estimator, a
new preprocessing step, a new feedback mapping) are validated by conforming to
these protocols — this is the project's equivalent of an IR contract.

Keep this module dependency-light: numpy only. No I/O, no heavy imports.
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
    HBO = "hbo"
    HBR = "hbr"


class BlockType(str, Enum):
    """Experiment block types (see session/protocol)."""

    REST = "rest"
    TASK = "task"
    BASELINE = "baseline"  # task-free movie (inscapes)
    TRANSFER = "transfer"  # exchange game, screen-based, no feedback


class FeedbackMode(str, Enum):
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

    Assembled by `io` from the individual LSL streams. `t_lsl` is the LSL clock
    timestamp of the chunk (the single clock of record). Channel axis ordering
    is fixed by the montage in the run config.

    Shapes:
        fnirs[subject]: (n_channels, n_samples)   raw optical intensities
        aux[subject]:   (n_aux_channels, n_samples) ECG/EDA/accelerometer
    """

    t_lsl: float
    fnirs: dict[SubjectId, np.ndarray]
    aux: dict[SubjectId, np.ndarray] = field(default_factory=dict)
    fs: float = 0.0  # sampling rate (Hz)


@dataclass(slots=True)
class HemoFrame:
    """Per-subject preprocessed hemodynamics after the online pipeline.

    `hbo`/`hbr` shape: (n_channels, n_samples), in micromolar concentration
    change. Already motion-corrected, bandpassed, short-channel-regressed —
    all causally.
    """

    t_lsl: float
    hbo: dict[SubjectId, np.ndarray]
    hbr: dict[SubjectId, np.ndarray]
    fs: float


@dataclass(slots=True)
class INSSample:
    """A single interpersonal-neural-synchrony value at time t.

    `value` is the raw estimator output (e.g. mean wavelet coherence) in [0, 1].
    `per_channel` optionally retains the channel-resolved coherence for logging
    and offline analysis; it must NOT be required by the feedback stage.
    """

    t_lsl: float
    value: float
    per_channel: np.ndarray | None = None
    estimator: str = ""


@dataclass(slots=True)
class FeedbackSample:
    """The signal actually delivered to the XR game.

    `level` is the normalized, baseline-corrected, smoothed value in [0, 1] that
    the game maps onto car speed and audio pitch/gain. `mode` records whether the
    source was real or sham — for logging only; the participant-facing path is
    identical for both.

    `session_mode` and `subject` route the sample to the right car(s) (D8):
      - HYPERSCANNING: one joint signal drives both cars; `subject` is None.
      - INDIVIDUAL:    per-subject neurofeedback; `subject` names the car's owner.
    Neither field may be branched on anywhere a participant could perceive a
    difference — the sham hard-rule applies to every session mode.
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

    def process(self, frame: RawFrame) -> HemoFrame: ...

    def reset(self) -> None: ...


@runtime_checkable
class INSEstimator(Protocol):
    """Computes a single joint INS value from both subjects' hemodynamics.

    Implementations live in `ins/`. They are windowed and run-time efficient.
    `name` is stamped into INSSample.estimator for provenance.
    """

    name: str

    def update(self, frame: HemoFrame) -> INSSample | None:
        """Push a frame; return an INSSample when a new value is ready, else None."""
        ...

    def reset(self) -> None: ...


@runtime_checkable
class FeedbackMapper(Protocol):
    """Maps raw INS to the delivered feedback level.

    Handles baseline correction, smoothing, clamping, and sham substitution.
    The mapping itself is deterministic and unit-tested; it is the part of the
    'game feel' that lives in the (testable) backend rather than in Unity.
    """

    def map(self, ins: INSSample, mode: FeedbackMode) -> FeedbackSample: ...

    def reset(self) -> None: ...

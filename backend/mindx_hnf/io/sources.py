"""Frame sources.

`FrameSource` is the abstract interface the pipeline consumes. Two concrete
implementations:

  - `LSLSource`     : resolves real LSL streams (NIRSport2 + movisens). Requires
                      pylsl + hardware; imported lazily so the package still
                      imports on a machine without LSL.
  - `SyntheticSource`: generates two-subject fNIRS-like signals with a tunable,
                      time-varying *true coherence* so downstream INS estimators
                      can be validated against ground truth. No hardware needed.

Both emit `RawFrame`s at a fixed update interval keyed to the LSL clock.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Protocol

import numpy as np

from mindx_hnf.contracts import RawFrame, SubjectId


def lsl_clock() -> float:
    """The single clock of record. Falls back to a monotonic clock if pylsl is
    absent, so synthetic runs and tests don't require LSL installed."""
    try:
        from pylsl import local_clock

        return float(local_clock())
    except Exception:  # noqa: BLE001 - intentional graceful fallback
        return time.monotonic()


class FrameSource(Protocol):
    fs: float

    def frames(self) -> Iterator[RawFrame]:
        """Yield time-synced RawFrames until the source is exhausted/stopped."""
        ...

    def stop(self) -> None: ...


class SyntheticSource:
    """Synthetic two-subject fNIRS source with controllable ground-truth INS.

    The signal model: each subject's channels are a shared latent oscillation in
    the canonical hemodynamic band (~0.01-0.1 Hz) mixed with independent noise.
    The mixing weight `coherence_fn(t)` sets how strongly the two subjects share
    the latent component, giving a known target for INS estimators.

    This is the backbone of testing and CI: it lets us assert that INS *tracks
    true synchrony* and that the feedback loop closes within latency budget,
    with zero hardware.
    """

    def __init__(
        self,
        *,
        n_channels: int = 20,
        fs: float = 7.81,  # typical NIRSport2 rate
        chunk_samples: int = 8,
        subjects: tuple[SubjectId, SubjectId] = ("sub-01", "sub-02"),
        coherence_fn=None,
        seed: int = 0,
        duration_s: float | None = None,
    ) -> None:
        self.n_channels = n_channels
        self.fs = fs
        self.chunk_samples = chunk_samples
        self.subjects = subjects
        self.coherence_fn = coherence_fn or (lambda t: 0.5)
        self.duration_s = duration_s
        self._rng = np.random.default_rng(seed)
        self._stopped = False
        self._t0 = lsl_clock()

    def _latent(self, t: np.ndarray) -> np.ndarray:
        # Shared slow hemodynamic oscillation around ~0.05 Hz.
        return np.sin(2 * np.pi * 0.05 * t) + 0.3 * np.sin(2 * np.pi * 0.09 * t)

    def frames(self) -> Iterator[RawFrame]:
        dt_chunk = self.chunk_samples / self.fs
        sample_idx = 0
        while not self._stopped:
            t_lsl = lsl_clock()
            elapsed = t_lsl - self._t0
            if self.duration_s is not None and elapsed > self.duration_s:
                return
            n = self.chunk_samples
            t = (np.arange(sample_idx, sample_idx + n)) / self.fs
            c = float(np.clip(self.coherence_fn(elapsed), 0.0, 1.0))
            shared = self._latent(t)
            fnirs: dict[SubjectId, np.ndarray] = {}
            for s in self.subjects:
                indep = self._rng.standard_normal((self.n_channels, n)) * 0.5
                sig = (
                    c * np.tile(shared, (self.n_channels, 1))
                    + (1 - c) * self._rng.standard_normal((self.n_channels, n))
                    + indep * 0.2
                )
                # Convert to intensity-like positive values around a DC level.
                fnirs[s] = 1.0 + 0.01 * sig
            sample_idx += n
            yield RawFrame(t_lsl=t_lsl, fnirs=fnirs, aux={}, fs=self.fs)
            # Pace to roughly real time so latency tests are meaningful.
            time.sleep(max(0.0, dt_chunk))

    def stop(self) -> None:
        self._stopped = True


class LSLSource:
    """Resolves and time-syncs real LSL streams. Lazy-imports pylsl.

    NOTE: implementation intentionally left as a thin, documented stub. The
    resolution + dejitter + chunk-alignment logic is the first hardware task;
    `SyntheticSource` mirrors its output contract exactly so everything
    downstream can be built and tested before hardware arrives.
    """

    def __init__(self, *, fnirs_stream_names: dict[SubjectId, str], fs: float) -> None:
        self.fnirs_stream_names = fnirs_stream_names
        self.fs = fs
        self._stopped = False

    def frames(self) -> Iterator[RawFrame]:  # pragma: no cover - needs hardware
        raise NotImplementedError(
            "LSLSource requires pylsl and live NIRSport2 streams. "
            "Develop and test against SyntheticSource; implement stream "
            "resolution + dejitter here when hardware is available. "
            "Must emit RawFrame on the LSL clock — see contracts.RawFrame."
        )

    def stop(self) -> None:
        self._stopped = True

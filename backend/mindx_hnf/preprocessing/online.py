"""Causal streaming preprocessing pipeline.

This is a *working but deliberately minimal* online pipeline. It establishes the
contract and the causal-filter discipline; the real fNIRS-grade conversions
(MBLL with measured pathlengths, full TDDR, principled short-channel GLM
regression) are flagged with TODOs and validated in tests against the synthetic
source. The point of the scaffold is that the *seams and invariants* are right
so Claude Code can fill in the numerics without redesigning the architecture.
"""

from __future__ import annotations

import numpy as np

from mindx_hnf.contracts import HemoFrame, RawFrame, SubjectId


class _CausalBandpass:
    """Single-section causal IIR-style bandpass via a streaming difference of
    two first-order leaky integrators (low - lower). Cheap, causal, stateful.

    Replace with a properly designed causal Butterworth (scipy.signal.lfilter
    with retained `zi` state) — this placeholder keeps the streaming-state
    pattern explicit. The state lives per channel.
    """

    def __init__(self, n_channels: int, fs: float, low: float, high: float) -> None:
        self.fs = fs
        # leak coefficients from cutoff approximations
        self._a_low = np.exp(-2 * np.pi * high / fs)
        self._a_high = np.exp(-2 * np.pi * low / fs)
        self._y_low = np.zeros((n_channels, 1))
        self._y_high = np.zeros((n_channels, 1))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        out = np.empty_like(x)
        for i in range(x.shape[1]):
            xi = x[:, i : i + 1]
            self._y_low = self._a_low * self._y_low + (1 - self._a_low) * xi
            self._y_high = self._a_high * self._y_high + (1 - self._a_high) * xi
            out[:, i : i + 1] = self._y_low - self._y_high
        return out

    def reset(self) -> None:
        self._y_low[:] = 0.0
        self._y_high[:] = 0.0


class OnlineHemoPipeline:
    """Implements the OnlinePreprocessor protocol.

    Per subject it keeps: a running DC reference for optical-density conversion
    and a causal bandpass with retained state. Converts intensity -> OD ->
    (placeholder) concentration and bandpasses in the hemodynamic band.
    """

    def __init__(
        self,
        subjects: tuple[SubjectId, ...],
        n_channels: int,
        fs: float,
        band: tuple[float, float] = (0.01, 0.1),
    ) -> None:
        self.subjects = subjects
        self.fs = fs
        self.band = band
        self._dc: dict[SubjectId, np.ndarray | None] = {s: None for s in subjects}
        self._bp_hbo = {
            s: _CausalBandpass(n_channels, fs, *band) for s in subjects
        }
        self._bp_hbr = {
            s: _CausalBandpass(n_channels, fs, *band) for s in subjects
        }

    def process(self, frame: RawFrame) -> HemoFrame:
        hbo: dict[SubjectId, np.ndarray] = {}
        hbr: dict[SubjectId, np.ndarray] = {}
        for s in self.subjects:
            intensity = np.asarray(frame.fnirs[s], dtype=float)
            # --- intensity -> optical density (causal running DC reference) ---
            dc = self._dc[s]
            chunk_dc = intensity.mean(axis=1, keepdims=True)
            dc = chunk_dc if dc is None else 0.99 * dc + 0.01 * chunk_dc
            self._dc[s] = dc
            od = -np.log(np.clip(intensity, 1e-6, None) / np.clip(dc, 1e-6, None))
            # --- MBLL placeholder: HbO/HbR as two linear combinations of OD ---
            # TODO(claude-code): replace with extinction-coefficient matrix and
            # measured differential pathlength factor per wavelength pair.
            hbo_raw = od
            hbr_raw = -0.6 * od
            # --- causal bandpass ---
            hbo[s] = self._bp_hbo[s](hbo_raw)
            hbr[s] = self._bp_hbr[s](hbr_raw)
            # TODO(claude-code): TDDR motion correction (causal variant) and
            # short-distance-channel regression go here, before/after bandpass
            # per fNIRS best practice (docs/PROTOCOL.md).
        return HemoFrame(t_lsl=frame.t_lsl, hbo=hbo, hbr=hbr, fs=self.fs)

    def reset(self) -> None:
        for s in self.subjects:
            self._dc[s] = None
            self._bp_hbo[s].reset()
            self._bp_hbr[s].reset()

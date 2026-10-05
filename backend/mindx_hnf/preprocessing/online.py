"""Causal streaming preprocessing pipeline.

Chains the causal stages: OD with a baseline-frozen reference, streaming TDDR,
and wavelength-paired short-channel regression (preprocessing/causal.py), then
MNE's Beer-Lambert operator (preprocessing/montage.py) and a causal bandpass.
Each MNE-derived stage is tested against MNE's batch version as the oracle.

Todo:
    * Replace `_CausalBandpass` with a properly designed causal Butterworth
      (``scipy.signal`` SOS filter with retained state).
"""

from __future__ import annotations

import numpy as np

from mindx_hnf.contracts import HemoFrame, RawFrame, SubjectId
from mindx_hnf.preprocessing.causal import (
    CausalODReference,
    CausalShortChannelRegression,
    CausalTDDR,
    short_channel_partners,
)
from mindx_hnf.preprocessing.montage import BeerLambertOperator, Montage


class _CausalBandpass:
    """Causal placeholder bandpass: difference of two leaky integrators.

    Single-section causal IIR-style bandpass via a streaming difference of two
    first-order leaky integrators (low - lower). Cheap, causal, stateful.

    TODO(claude-code): replace with a properly designed causal Butterworth (scipy.signal.lfilter
    with retained `zi` state) — this placeholder keeps the streaming-state
    pattern explicit. The state lives per channel.

    Attributes:
        fs: Sampling rate in Hz.
    """

    def __init__(self, n_channels: int, fs: float, low: float, high: float) -> None:
        """Create the filter with zero state.

        Args:
            n_channels: Number of channels filtered in parallel.
            fs: Sampling rate in Hz.
            low: Lower cutoff in Hz.
            high: Upper cutoff in Hz.
        """
        self.fs = fs
        # leak coefficients from cutoff approximations
        self._a_low = np.exp(-2 * np.pi * high / fs)
        self._a_high = np.exp(-2 * np.pi * low / fs)
        self._y_low = np.zeros((n_channels, 1))
        self._y_high = np.zeros((n_channels, 1))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """Filter one chunk, carrying state across calls.

        Args:
            x: Input of shape ``(n_channels, n_samples)``.

        Returns:
            The filtered chunk, same shape as ``x``.
        """
        out = np.empty_like(x)
        for i in range(x.shape[1]):
            xi = x[:, i : i + 1]
            self._y_low = self._a_low * self._y_low + (1 - self._a_low) * xi
            self._y_high = self._a_high * self._y_high + (1 - self._a_high) * xi
            out[:, i : i + 1] = self._y_low - self._y_high
        return out

    def reset(self) -> None:
        """Zero the filter state."""
        self._y_low[:] = 0.0
        self._y_high[:] = 0.0


class OnlineHemoPipeline:
    """Implements the OnlinePreprocessor (and BaselineLockable) protocols.

    Per subject, per frame, all causal (D10 Phase 2 — the MNE-NIRS order):

        intensity -> optical density (baseline-frozen reference)
                  -> TDDR motion correction (streaming)
                  -> short-channel regression (wavelength-paired, streaming)
                  -> MBLL -> Δ[HbO]/[HbR]
                  -> drop short channels -> causal bandpass

    MBLL: with a ``montage``, HbO/HbR come from the MNE-NIRS Beer-Lambert
    operator, built ONCE at construction (preprocessing/montage.py) and applied
    as a numpy matmul. Raw intensity must then be wavelength-paired in the
    montage's channel order (``montage.n_raw_channels`` rows). The output holds
    the montage's LONG channels only (``montage.n_long``): short channels are
    nuisance regressors, not brain signal, and must not reach the INS estimator.
    Without a montage the pipeline falls back to the placeholder mapping and has
    no short-channel regression (no geometry), so the montage-free path keeps
    working.

    The OD reference is the running mean intensity until :meth:`lock_baseline`
    (called by the orchestrator when the baseline block ends), then frozen.

    Attributes:
        subjects: Subjects processed per frame.
        fs: Sampling rate in Hz.
        band: Bandpass edges in Hz.
        montage: Optode montage, or None for the placeholder path.
    """

    def __init__(
        self,
        subjects: tuple[SubjectId, ...],
        n_channels: int,
        fs: float,
        band: tuple[float, float] = (0.01, 0.1),
        montage: Montage | None = None,
        motion_correction: bool = True,
        short_channel_regression: bool = True,
        tddr_window_s: float = 60.0,
        scr_tau_s: float | None = 120.0,
    ) -> None:
        """Build per-subject stage state (and the MNE operator, once).

        Args:
            subjects: Subjects processed per frame.
            n_channels: Raw channels per subject; ignored with a montage, which
                fixes it to ``montage.n_raw_channels``.
            fs: Sampling rate in Hz.
            band: Bandpass edges in Hz.
            montage: Optode montage; enables MNE MBLL and short-channel
                regression.
            motion_correction: Run causal TDDR.
            short_channel_regression: Run short-channel regression (needs a
                montage with short channels).
            tddr_window_s: TDDR robust-statistics window in seconds.
            scr_tau_s: Short-channel regression forgetting time constant in
                seconds; None = no forgetting.

        Raises:
            ValueError: If the montage does not have exactly two wavelengths, or
                a channel flagged short is not geometrically short.
        """
        self.subjects = subjects
        self.fs = fs
        self.band = band
        self.montage = montage
        self._op = BeerLambertOperator.from_montage(montage) if montage else None
        raw_channels = montage.n_raw_channels if montage else n_channels
        if montage is not None:
            self._keep: np.ndarray | None = ~montage.short_mask
            out_channels = montage.n_long
            partners = short_channel_partners(montage)
        else:
            self._keep = None
            out_channels = n_channels
            partners = np.full(raw_channels, -1, dtype=int)
        if not short_channel_regression:
            partners = np.full(raw_channels, -1, dtype=int)

        self._od = {s: CausalODReference(raw_channels) for s in subjects}
        self._tddr = (
            {s: CausalTDDR(raw_channels, fs, window_s=tddr_window_s) for s in subjects}
            if motion_correction
            else None
        )
        self._scr = {
            s: CausalShortChannelRegression(partners, fs, tau_s=scr_tau_s)
            for s in subjects
        }
        self._bp_hbo = {s: _CausalBandpass(out_channels, fs, *band) for s in subjects}
        self._bp_hbr = {s: _CausalBandpass(out_channels, fs, *band) for s in subjects}

    @property
    def baseline_locked(self) -> bool:
        """Whether every subject's OD reference is frozen."""
        return all(self._od[s].locked for s in self.subjects)

    def lock_baseline(self) -> None:
        """Freeze every subject's OD reference at the baseline-block mean."""
        for s in self.subjects:
            self._od[s].lock()

    def process(self, frame: RawFrame) -> HemoFrame:
        """Run the causal chain on one frame for every subject.

        Args:
            frame: Raw intensities; with a montage, wavelength-paired in the
                montage's channel order.

        Returns:
            Bandpassed Δ[HbO]/[HbR] in µM, long channels only with a montage.
        """
        hbo: dict[SubjectId, np.ndarray] = {}
        hbr: dict[SubjectId, np.ndarray] = {}
        for s in self.subjects:
            intensity = np.asarray(frame.fnirs[s], dtype=float)
            od = self._od[s](intensity)
            if self._tddr is not None:
                od = self._tddr[s](od)
            od = self._scr[s](od)
            # --- modified Beer-Lambert -> Δ[HbO]/[HbR] ---
            if self._op is not None:
                hbo_raw, hbr_raw = self._op.apply(od)  # MNE operator (D10)
            else:
                # Placeholder mapping for the montage-free path.
                hbo_raw = od
                hbr_raw = -0.6 * od
            if self._keep is not None:
                hbo_raw = hbo_raw[self._keep]
                hbr_raw = hbr_raw[self._keep]
            hbo[s] = self._bp_hbo[s](hbo_raw)
            hbr[s] = self._bp_hbr[s](hbr_raw)
        return HemoFrame(t_lsl=frame.t_lsl, hbo=hbo, hbr=hbr, fs=self.fs)

    def reset(self) -> None:
        """Reset every stage and unlock the OD reference."""
        for s in self.subjects:
            self._od[s].reset()
            if self._tddr is not None:
                self._tddr[s].reset()
            self._scr[s].reset()
            self._bp_hbo[s].reset()
            self._bp_hbr[s].reset()

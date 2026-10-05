"""Causal, streaming versions of MNE-NIRS's batch preprocessing steps (D10, Phase 2).

MNE-NIRS implements optical density, TDDR and short-channel regression for a
WHOLE recording: each uses statistics over all samples (time-mean reference,
global robust derivative distribution, global regression coefficient) and TDDR
additionally splits frequencies with a zero-phase ``filtfilt``. None of that may
run on the real-time track. Each class here keeps the MNE algorithm and replaces
only the non-causal part with a causal estimate built from past/current samples:

=========================  ===========================  ===========================
step                       MNE (batch, offline oracle)  here (causal, online)
=========================  ===========================  ===========================
optical density            ref = whole-recording mean   ref = baseline-block mean,
                                                        frozen at baseline lock
TDDR (Fishburn 2019)       global robust (mu, sigma),   robust (mu, sigma) over a
                           ``filtfilt`` low/high split  sliding window of past
                                                        derivatives, causal SOS
                                                        low/high split
short-channel regression   alpha over whole recording   alpha from exponentially
                           (Scholkmann 2014 eqn 26/27)  weighted running moments
=========================  ===========================  ===========================

The MNE versions stay the test oracles (``tests/test_causal_preprocessing.py``).
All state is pre-allocated at construction; per-frame work is numpy on
``(n_channels, n_samples)`` chunks — no MNE call on the hot path.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

from mindx_hnf.preprocessing.montage import Montage

_EPS = 1e-6


class CausalODReference:
    """Intensity -> optical density, ``OD = -ln(I / I_ref)``, with a causal reference.

    MNE's ``optical_density`` divides by the mean over the whole recording (uses
    the future). Here ``I_ref`` is the running mean of every sample seen so far
    until :meth:`lock` is called at the end of the baseline block; from then on
    it is frozen, so post-baseline OD is relative to the baseline-block mean —
    the same reference the feedback baseline uses. If ``lock`` comes before any
    data (a protocol with no baseline block), the first chunk sets the reference.
    """

    def __init__(self, n_channels: int) -> None:
        """Create an unlocked reference.

        Args:
            n_channels: Raw intensity channels.
        """
        self._sum = np.zeros((n_channels, 1))
        self._count = 0
        self._ref = np.ones((n_channels, 1))
        self._locked = False

    @property
    def locked(self) -> bool:
        """Whether the reference is frozen."""
        return self._locked

    @property
    def reference(self) -> np.ndarray:
        """Current reference intensity ``I_ref``, shape ``(n_channels, 1)``."""
        return self._ref

    def lock(self) -> None:
        """Freeze the reference (call at the end of the baseline block)."""
        self._locked = True

    def __call__(self, intensity: np.ndarray) -> np.ndarray:
        """Convert one chunk to optical density, updating the reference if unlocked.

        Args:
            intensity: Raw intensity, shape ``(n_channels, n_samples)``.

        Returns:
            ``-ln(I / I_ref)``, same shape as ``intensity``.
        """
        if not self._locked or self._count == 0:
            self._sum += intensity.sum(axis=1, keepdims=True)
            self._count += intensity.shape[1]
            np.divide(self._sum, self._count, out=self._ref)
        return -np.log(np.clip(intensity, _EPS, None) / np.clip(self._ref, _EPS, None))

    def reset(self) -> None:
        """Forget all data and unlock the reference."""
        self._sum[:] = 0.0
        self._count = 0
        self._ref[:] = 1.0
        self._locked = False


class CausalTDDR:
    """Streaming Temporal Derivative Distribution Repair (Fishburn et al. 2019).

    Same algorithm as ``mne.preprocessing.nirs.temporal_derivative_distribution_repair``
    with the two non-causal parts replaced:

    1. The low/high split uses a causal Butterworth (same 0.5 Hz / order 3 as
       MNE) with retained filter state, not ``filtfilt``.
    2. The robust derivative statistics (Tukey-biweight mean ``mu`` and scale
       ``sigma``, iterated as in MNE) come from a sliding window of the last
       ``window_s`` seconds of derivatives — including the current chunk — not
       the whole recording. They are re-estimated once per chunk.

    Each low-band derivative is then down-weighted by the biweight, re-centred by
    ``mu`` and integrated causally; the high band passes through untouched. MNE's
    final re-centring of the corrected signal (subtracting its global mean) is
    dropped — a constant offset is removed downstream by the bandpass anyway.
    Until ``min_window_s`` of derivatives exist the step is an identity.
    """

    _TUNE = 4.685  # Tukey biweight tuning constant (as in MNE / Fishburn 2019)
    _MAX_ITER = 50

    def __init__(
        self,
        n_channels: int,
        fs: float,
        window_s: float = 60.0,
        min_window_s: float = 10.0,
        filter_cutoff: float = 0.5,
        filter_order: int = 3,
    ) -> None:
        """Pre-allocate filter state and the derivative window.

        Args:
            n_channels: Channels corrected in parallel.
            fs: Sampling rate in Hz.
            window_s: Length of the robust-statistics window in seconds.
            min_window_s: Warm-up before correction starts; the step is an
                identity until this much derivative history exists.
            filter_cutoff: Low/high split frequency in Hz (as in MNE).
            filter_order: Butterworth order of the split (as in MNE).
        """
        wn = filter_cutoff * 2.0 / fs
        self._sos = butter(filter_order, wn, output="sos") if wn < 1.0 else None
        self._zi_unit: np.ndarray | None = (
            sosfilt_zi(self._sos) if self._sos is not None else None
        )
        self._zi: np.ndarray | None = None
        self._capacity = max(2, int(round(window_s * fs)))
        self._min_fill = max(2, int(round(min_window_s * fs)))
        self._deriv = np.zeros((n_channels, self._capacity))
        self._pos = 0
        self._filled = 0
        self._last_low = np.zeros((n_channels, 1))
        self._integ = np.zeros((n_channels, 1))
        self._started = False

    def _split(self, x: np.ndarray) -> np.ndarray:
        """Return the causal low band of ``x``; state is retained across chunks.

        Args:
            x: Input chunk, shape ``(n_channels, n_samples)``.

        Returns:
            The low-band part of ``x``, same shape.
        """
        if self._sos is None or self._zi_unit is None:
            return x.copy()
        if self._zi is None:
            # Start the filter at steady state on the first sample (no transient).
            self._zi = self._zi_unit[:, None, :] * x[None, :, 0:1]
        low, self._zi = sosfilt(self._sos, x, axis=1, zi=self._zi)
        return low

    def _push(self, d: np.ndarray) -> None:
        """Append derivatives to the ring-buffer window.

        Args:
            d: Derivatives, shape ``(n_channels, n_samples)``.
        """
        n = d.shape[1]
        if n >= self._capacity:
            self._deriv[:] = d[:, -self._capacity :]
            self._pos = 0
        else:
            end = self._pos + n
            if end <= self._capacity:
                self._deriv[:, self._pos : end] = d
            else:
                k = self._capacity - self._pos
                self._deriv[:, self._pos :] = d[:, :k]
                self._deriv[:, : n - k] = d[:, k:]
            self._pos = end % self._capacity
        self._filled = min(self._capacity, self._filled + n)

    def _robust_stats(self) -> tuple[np.ndarray, np.ndarray]:
        """Estimate per-channel robust derivative statistics over the window.

        Uses MNE's iterated Tukey biweight, vectorized over channels.

        Returns:
            ``(mu, sigma)``, each of shape ``(n_channels,)``. ``sigma == 0``
            marks a channel whose derivatives are left unweighted.
        """
        d = self._deriv[:, : self._filled]
        n_ch = d.shape[0]
        w = np.ones_like(d)
        mu = np.full(n_ch, np.inf)
        sigma = np.zeros(n_ch)
        active = np.ones(n_ch, dtype=bool)
        tol = np.sqrt(np.finfo(float).eps)
        for _ in range(self._MAX_ITER):
            mu0 = mu.copy()
            wsum = w.sum(axis=1)
            mu = np.where(
                active, (w * d).sum(axis=1) / np.where(wsum > 0, wsum, 1.0), mu0
            )
            dev = np.abs(d - mu[:, None])
            sig = 1.4826 * np.median(dev, axis=1)
            sigma = np.where(active, sig, sigma)
            # sigma == 0 stops that channel (MNE: break), weights stay as they are.
            active &= sigma > 0
            r = dev / np.where(sigma > 0, sigma * self._TUNE, 1.0)[:, None]
            w_new = ((1.0 - r**2) * (r < 1.0)) ** 2
            w = np.where(active[:, None], w_new, w)
            converged = np.abs(mu - mu0) < tol * np.maximum(np.abs(mu), np.abs(mu0))
            active &= ~converged
            if not active.any():
                break
        return mu, sigma

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """Motion-correct one chunk.

        Args:
            x: Optical density (or concentration), shape
                ``(n_channels, n_samples)``.

        Returns:
            The corrected chunk, same shape as ``x``.
        """
        low = self._split(x)
        high = x - low
        if not self._started:
            # First sample has no predecessor: its derivative is 0 and the
            # integrator starts at the observed low-band value.
            self._last_low[:] = low[:, :1]
            self._integ[:] = low[:, :1]
            self._started = True
        deriv = np.diff(low, axis=1, prepend=self._last_low)
        self._last_low[:] = low[:, -1:]
        self._push(deriv)

        if self._filled >= self._min_fill:
            mu, sigma = self._robust_stats()
            sig = np.where(sigma > 0, sigma * self._TUNE, np.inf)[:, None]
            r = np.abs(deriv - mu[:, None]) / sig
            w = np.where((sigma > 0)[:, None], ((1.0 - r**2) * (r < 1.0)) ** 2, 1.0)
            new_deriv = w * (deriv - mu[:, None])
        else:
            new_deriv = deriv
        low_corrected = self._integ + np.cumsum(new_deriv, axis=1)
        self._integ[:] = low_corrected[:, -1:]
        return low_corrected + high

    def reset(self) -> None:
        """Clear filter state, the derivative window and the integrator."""
        self._zi = None
        self._deriv[:] = 0.0
        self._pos = 0
        self._filled = 0
        self._last_low[:] = 0.0
        self._integ[:] = 0.0
        self._started = False


def short_channel_partners(montage: Montage, max_dist: float = 0.01) -> np.ndarray:
    """Map each raw OD row to the raw row of its regressor short channel.

    A long channel's partner is the nearest short channel (by midpoint distance,
    MNE-NIRS's criterion) **at the same wavelength**. MNE-NIRS 0.7.3 picks the
    first short row at the nearest midpoint, which regresses BOTH wavelengths of
    a long channel on the short channel's first (760 nm) row; pairing by
    wavelength is the physically correct version (Scholkmann 2014 regresses per
    wavelength). Short rows get -1, as does every row of a montage without
    short channels. Shortness follows the montage's ``short`` flag;
    ``max_dist`` is only a consistency check against the geometry.

    Args:
        montage: The montage, in raw-layout order.
        max_dist: Maximum source-detector distance in metres for a short
            channel.

    Returns:
        Integer array of length ``montage.n_raw_channels``: the partner's raw
        row index, or -1.

    Raises:
        ValueError: If a channel flagged short is at least ``max_dist`` long.
    """
    n_wl = len(montage.wavelengths)
    mids = np.array(
        [
            (np.asarray(c.source, float) + np.asarray(c.detector, float)) / 2.0
            for c in montage.channels
        ]
    )
    short_pairs = np.flatnonzero(montage.short_mask)
    for sp_idx in short_pairs:
        if montage.channels[sp_idx].distance_m >= max_dist:
            raise ValueError(
                f"Channel {sp_idx} is flagged short but is "
                f"{montage.channels[sp_idx].distance_m * 100:.1f} cm long."
            )
    partners = np.full(montage.n_raw_channels, -1, dtype=int)
    if short_pairs.size == 0:
        return partners
    for p, ch in enumerate(montage.channels):
        if ch.short:
            continue
        dist = np.linalg.norm(mids[short_pairs] - mids[p], axis=1)
        sp = int(short_pairs[int(np.argmin(dist))])
        for k in range(n_wl):
            partners[p * n_wl + k] = sp * n_wl + k
    return partners


class CausalShortChannelRegression:
    """Streaming short-channel regression (Scholkmann et al. 2014, eqns 26/27).

    MNE-NIRS removes ``alpha * short`` from each long channel with one
    ``alpha = <s, l> / <s, s>`` over the whole recording. Here ``alpha`` is
    recomputed at every sample from exponentially weighted running moments of
    past/current samples (time constant ``tau_s``; ``None`` = no forgetting,
    i.e. all samples so far). The moments are mean-centred so a DC offset in
    optical density (the causal OD reference is not the whole-recording mean)
    does not bias ``alpha``; on zero-mean data with ``tau_s=None`` the final
    ``alpha`` is exactly MNE-NIRS's. Short rows pass through unchanged.

    Attributes:
        alpha: Current regression coefficient per long row.
    """

    def __init__(
        self, partners: np.ndarray, fs: float, tau_s: float | None = 120.0
    ) -> None:
        """Create the regressor with zero running moments.

        Args:
            partners: Output of ``short_channel_partners``; rows with -1 are
                left unchanged.
            fs: Sampling rate in Hz.
            tau_s: Forgetting time constant in seconds; None = no forgetting.
        """
        self._long = np.flatnonzero(partners >= 0)
        self._short = partners[self._long]
        self._lam = 1.0 if tau_s is None else float(np.exp(-1.0 / (tau_s * fs)))
        n = self._long.size
        self._w = 0.0
        self._ms = np.zeros(n)
        self._ml = np.zeros(n)
        self._css = np.zeros(n)
        self._csl = np.zeros(n)
        self.alpha = np.zeros(n)

    @property
    def enabled(self) -> bool:
        """Whether any row has a short-channel partner."""
        return self._long.size > 0

    def __call__(self, od: np.ndarray) -> np.ndarray:
        """Regress the short-channel signal out of each long row, sample by sample.

        Args:
            od: Optical density, shape ``(n_raw_channels, n_samples)``.

        Returns:
            Corrected optical density, same shape; ``od`` itself if disabled.
        """
        if not self.enabled:
            return od
        out = od.copy()
        lam = self._lam
        for i in range(od.shape[1]):
            s = od[self._short, i]
            l_ = od[self._long, i]
            # Exponentially weighted (West) update of means and co-moments.
            self._w = lam * self._w + 1.0
            ds = s - self._ms
            dl = l_ - self._ml
            self._ms += ds / self._w
            self._ml += dl / self._w
            self._css = lam * self._css + ds * (s - self._ms)
            self._csl = lam * self._csl + ds * (l_ - self._ml)
            np.divide(self._csl, self._css, out=self.alpha, where=self._css > 0)
            out[self._long, i] = l_ - self.alpha * s
        return out

    def reset(self) -> None:
        """Clear the running moments and coefficients."""
        self._w = 0.0
        self._ms[:] = 0.0
        self._ml[:] = 0.0
        self._css[:] = 0.0
        self._csl[:] = 0.0
        self.alpha[:] = 0.0

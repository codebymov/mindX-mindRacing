"""INS estimator tests: the values that actually guard the science.

Core assertion: INS must MONOTONICALLY TRACK true coherence. If an estimator
reports high synchrony when subjects are decoupled (or vice versa), the whole
intervention is invalid — so this is a load-bearing test, not a nicety.
"""

from __future__ import annotations

import numpy as np

from mindx_hnf.contracts import HemoFrame
from mindx_hnf.ins.coherence import WaveletCoherenceINS, WindowedCorrelationINS


def _make_frames(coherence: float, *, fs=7.81, n_channels=10, seconds=60, seed=1):
    rng = np.random.default_rng(seed)
    n = int(fs * seconds)
    t = np.arange(n) / fs
    shared = np.sin(2 * np.pi * 0.05 * t)
    frames = []
    chunk = 8
    for start in range(0, n - chunk, chunk):
        sl = slice(start, start + chunk)
        a = coherence * shared[sl] + (1 - coherence) * rng.standard_normal(chunk)
        b = coherence * shared[sl] + (1 - coherence) * rng.standard_normal(chunk)
        hbo = {
            "sub-01": np.tile(a, (n_channels, 1)),
            "sub-02": np.tile(b, (n_channels, 1)),
        }
        hbr = {k: -0.6 * v for k, v in hbo.items()}
        frames.append(HemoFrame(t_lsl=float(start / fs), hbo=hbo, hbr=hbr, fs=fs))
    return frames


def _mean_ins(estimator, frames):
    vals = []
    for f in frames:
        s = estimator.update(f)
        if s is not None:
            vals.append(s.value)
    return float(np.mean(vals[-10:])) if vals else 0.0


def test_correlation_ins_tracks_truth():
    subs = ("sub-01", "sub-02")
    low = _mean_ins(WindowedCorrelationINS(subs, 7.81, window_s=20), _make_frames(0.1))
    high = _mean_ins(WindowedCorrelationINS(subs, 7.81, window_s=20), _make_frames(0.9))
    assert high > low, f"INS should rise with true coherence: {low=} {high=}"


def test_wavelet_coherence_ins_tracks_truth():
    subs = ("sub-01", "sub-02")
    low = _mean_ins(WaveletCoherenceINS(subs, 7.81, window_s=25), _make_frames(0.1))
    high = _mean_ins(WaveletCoherenceINS(subs, 7.81, window_s=25), _make_frames(0.9))
    assert high > low, f"Coherence INS should rise with true coherence: {low=} {high=}"


def test_ins_in_unit_range():
    subs = ("sub-01", "sub-02")
    est = WaveletCoherenceINS(subs, 7.81, window_s=25)
    for f in _make_frames(0.7):
        s = est.update(f)
        if s is not None:
            assert 0.0 <= s.value <= 1.0


def test_ins_returns_none_before_window_filled():
    subs = ("sub-01", "sub-02")
    est = WindowedCorrelationINS(subs, 7.81, window_s=30)
    frames = _make_frames(0.5, seconds=5)  # shorter than the window
    assert all(est.update(f) is None for f in frames)

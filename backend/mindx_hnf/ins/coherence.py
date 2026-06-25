"""INS estimators.

Two estimators are provided:

  - `WindowedCorrelationINS`: a simple, fast, fully-working baseline — windowed
    Pearson correlation of the two subjects' channel-averaged HbO, mapped to
    [0, 1]. Useful as a sanity reference and as the thing tests assert against.

  - `WaveletCoherenceINS`: the intended estimator — windowed magnitude-squared
    coherence in the hemodynamic band. A correct-but-simple Welch-style
    coherence is implemented over the sliding window; swapping in a true
    continuous-wavelet (Morlet) coherence is a localized change behind the same
    protocol. This is the latency/stability trade-off called out in CLAUDE.md §7.

Both keep a per-subject ring buffer of channel-averaged HbO and recompute on a
fixed update cadence (`update_every_s`).
"""

from __future__ import annotations

import numpy as np

from mindx_hnf.contracts import HemoFrame, INSSample, SubjectId


class _RingBuffer:
    """Fixed-capacity 1-D ring buffer (no per-sample allocation in steady state)."""

    def __init__(self, capacity: int) -> None:
        self._buf = np.zeros(capacity, dtype=float)
        self._cap = capacity
        self._n = 0
        self._head = 0

    def push(self, x: np.ndarray) -> None:
        for v in x:
            self._buf[self._head] = v
            self._head = (self._head + 1) % self._cap
            self._n = min(self._n + 1, self._cap)

    @property
    def filled(self) -> bool:
        return self._n >= self._cap

    def view(self) -> np.ndarray:
        if self._n < self._cap:
            return self._buf[: self._n].copy()
        return np.concatenate((self._buf[self._head :], self._buf[: self._head]))


class _BaseSlidingINS:
    name = "base"

    def __init__(
        self,
        subjects: tuple[SubjectId, SubjectId],
        fs: float,
        window_s: float = 30.0,
        update_every_s: float = 1.0,
    ) -> None:
        self.subjects = subjects
        self.fs = fs
        self.window_n = int(round(window_s * fs))
        self._update_n = max(1, int(round(update_every_s * fs)))
        self._since_update = 0
        self._buf = {s: _RingBuffer(self.window_n) for s in subjects}

    def _ingest(self, frame: HemoFrame) -> None:
        for s in self.subjects:
            # channel-averaged HbO over target channels (montage selects PFC/rTPJ
            # upstream; here we average all provided channels).
            chan_mean = np.asarray(frame.hbo[s], dtype=float).mean(axis=0)
            self._buf[s].push(chan_mean)
            self._since_update += chan_mean.shape[0]

    def _ready(self) -> bool:
        a, b = self.subjects
        return (
            self._buf[a].filled
            and self._buf[b].filled
            and self._since_update >= self._update_n
        )

    def _compute(self, x: np.ndarray, y: np.ndarray) -> float:  # pragma: no cover
        raise NotImplementedError

    def update(self, frame: HemoFrame) -> INSSample | None:
        self._ingest(frame)
        if not self._ready():
            return None
        self._since_update = 0
        a, b = self.subjects
        x = self._buf[a].view()
        y = self._buf[b].view()
        n = min(x.shape[0], y.shape[0])
        value = float(np.clip(self._compute(x[-n:], y[-n:]), 0.0, 1.0))
        return INSSample(t_lsl=frame.t_lsl, value=value, estimator=self.name)

    def reset(self) -> None:
        self._buf = {s: _RingBuffer(self.window_n) for s in self.subjects}
        self._since_update = 0


class WindowedCorrelationINS(_BaseSlidingINS):
    """Windowed Pearson correlation, rectified to [0, 1]. Fast baseline."""

    name = "windowed_correlation"

    def _compute(self, x: np.ndarray, y: np.ndarray) -> float:
        if np.std(x) < 1e-9 or np.std(y) < 1e-9:
            return 0.0
        r = float(np.corrcoef(x, y)[0, 1])
        return max(0.0, r)  # negative synchrony -> 0 feedback


class WaveletCoherenceINS(_BaseSlidingINS):
    """Windowed magnitude-squared coherence in the hemodynamic band.

    Implemented here as Welch-averaged coherence (band-limited). TODO for
    Claude Code: replace the Welch coherence with a true Morlet continuous
    wavelet coherence averaged over scales in `band`, keeping this same protocol
    and the [0,1] output. Validate against SyntheticSource ground truth.
    """

    name = "wavelet_coherence"

    def __init__(self, *args, band: tuple[float, float] = (0.01, 0.1), **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.band = band

    def _compute(self, x: np.ndarray, y: np.ndarray) -> float:
        n = x.shape[0]
        if n < 16:
            return 0.0
        seg = max(16, n // 4)
        step = seg // 2
        freqs = np.fft.rfftfreq(seg, d=1.0 / self.fs)
        band_mask = (freqs >= self.band[0]) & (freqs <= self.band[1])
        if not band_mask.any():
            band_mask = freqs > 0
        win = np.hanning(seg)
        sxx = np.zeros(freqs.shape, dtype=complex)
        syy = np.zeros(freqs.shape, dtype=complex)
        sxy = np.zeros(freqs.shape, dtype=complex)
        count = 0
        for start in range(0, n - seg + 1, step):
            xs = (x[start : start + seg] - x[start : start + seg].mean()) * win
            ys = (y[start : start + seg] - y[start : start + seg].mean()) * win
            fx = np.fft.rfft(xs)
            fy = np.fft.rfft(ys)
            sxx += fx * np.conj(fx)
            syy += fy * np.conj(fy)
            sxy += fx * np.conj(fy)
            count += 1
        if count == 0:
            return 0.0
        denom = (np.abs(sxx) * np.abs(syy)) + 1e-12
        coh = (np.abs(sxy) ** 2) / denom
        return float(np.real(coh[band_mask].mean()))

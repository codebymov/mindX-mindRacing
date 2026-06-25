"""Interpersonal Neural Synchrony (INS) estimators.

Each estimator consumes per-subject `HemoFrame`s and emits a single scalar
`INSSample` — the joint feedback feature delivered to both participants. This is
the project's core neuroscientific quantity.

Estimators are windowed and run-time efficient. The reference implementation is
windowed magnitude-squared (wavelet) coherence over the hemodynamic band,
averaged across the target channels (PFC, rTPJ). All estimators conform to the
`INSEstimator` protocol in `contracts` so they are interchangeable and testable
against the synthetic ground-truth source.
"""

from mindx_hnf.ins.coherence import WaveletCoherenceINS, WindowedCorrelationINS

__all__ = ["WaveletCoherenceINS", "WindowedCorrelationINS"]

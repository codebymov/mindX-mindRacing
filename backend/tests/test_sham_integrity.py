"""Sham-integrity tests.

The experimental validity of the whole study rests on sham being
indistinguishable from real at the participant-facing layer. These tests pin
that invariant: identical mapping, sham draws from a real other-dyad trace, and
the delivered level depends only on the source value — not on the mode flag.
"""

from __future__ import annotations

from mindx_hnf.contracts import FeedbackMode, INSSample
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper, ShamProvider


def _ins(v: float, t: float = 0.0) -> INSSample:
    return INSSample(t_lsl=t, value=v, estimator="test")


def test_sham_uses_recorded_trace_not_live_value():
    sham = ShamProvider([0.8, 0.8, 0.8])
    mapper = BaselineSmoothingMapper(sham=sham, smoothing=1.0, gain=1.0)
    # Live INS is 0.0, but sham must deliver based on the 0.8 recorded trace.
    out = mapper.map(_ins(0.0), FeedbackMode.SHAM)
    assert out.raw_ins == 0.8
    assert out.level > 0.0
    assert out.mode is FeedbackMode.SHAM


def test_real_and_sham_share_identical_mapping():
    # Same source value through both modes => same delivered level.
    trace = [0.6]
    real_mapper = BaselineSmoothingMapper(smoothing=1.0, gain=1.0)
    sham_mapper = BaselineSmoothingMapper(
        sham=ShamProvider(trace), smoothing=1.0, gain=1.0
    )
    real_out = real_mapper.map(_ins(0.6), FeedbackMode.REAL)
    sham_out = sham_mapper.map(_ins(0.0), FeedbackMode.SHAM)  # live value irrelevant
    assert abs(real_out.level - sham_out.level) < 1e-12


def test_mode_flag_recorded_but_not_perceptible():
    sham = ShamProvider([0.5])
    mapper = BaselineSmoothingMapper(sham=sham, smoothing=1.0, gain=1.0)
    out = mapper.map(_ins(0.5), FeedbackMode.SHAM)
    # mode is recorded for analysis...
    assert out.mode is FeedbackMode.SHAM
    # ...but level is purely a function of the source value (0.5), same as real.
    real_mapper = BaselineSmoothingMapper(smoothing=1.0, gain=1.0)
    real_out = real_mapper.map(_ins(0.5), FeedbackMode.REAL)
    assert abs(out.level - real_out.level) < 1e-12


def test_baseline_correction_applies_equally():
    mapper = BaselineSmoothingMapper(smoothing=1.0, gain=1.0)
    for _ in range(10):
        mapper.observe_baseline(_ins(0.4))
    mapper.lock_baseline()
    out = mapper.map(_ins(0.4), FeedbackMode.REAL)
    assert out.level == 0.0  # at-baseline synchrony => zero feedback

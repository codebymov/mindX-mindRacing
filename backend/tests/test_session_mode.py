"""Session-mode contract tests (DECISIONS.md D8).

D8 adds a session mode (Hyperscanning vs Individual) and a per-subject channel
to the feedback contract. These tests pin the seam:

  - Hyperscanning is the default and byte-identical to the pre-D8 behaviour
    (one shared signal, subject is None).
  - Individual mode stamps the owning subject onto every delivered sample.
  - session_mode / subject are orthogonal to the real/sham flag — the sham
    hard-rule applies to every session mode.
  - The construction invariant (shared car <=> no subject; per-subject car <=>
    a subject) is enforced, so a misconfigured session fails loudly.
"""

from __future__ import annotations

import pytest

from mindx_hnf.contracts import (
    FeedbackMode,
    FeedbackSample,
    INSSample,
    SessionMode,
)
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper, ShamProvider


def _ins(v: float, t: float = 0.0) -> INSSample:
    return INSSample(t_lsl=t, value=v, estimator="test")


def test_default_is_hyperscanning_shared_car():
    mapper = BaselineSmoothingMapper(smoothing=1.0, gain=1.0)
    out = mapper.map(_ins(0.5), FeedbackMode.REAL)
    assert out.session_mode is SessionMode.HYPERSCANNING
    assert out.subject is None


def test_individual_mode_stamps_subject():
    mapper = BaselineSmoothingMapper(
        smoothing=1.0, gain=1.0, session_mode=SessionMode.INDIVIDUAL, subject="sub-01"
    )
    out = mapper.map(_ins(0.5), FeedbackMode.REAL)
    assert out.session_mode is SessionMode.INDIVIDUAL
    assert out.subject == "sub-01"


def test_session_mode_does_not_change_delivered_level():
    # The routing fields are metadata only; the mapping math is identical.
    hyper = BaselineSmoothingMapper(smoothing=1.0, gain=1.0)
    indiv = BaselineSmoothingMapper(
        smoothing=1.0, gain=1.0, session_mode=SessionMode.INDIVIDUAL, subject="sub-01"
    )
    a = hyper.map(_ins(0.7), FeedbackMode.REAL)
    b = indiv.map(_ins(0.7), FeedbackMode.REAL)
    assert abs(a.level - b.level) < 1e-12


def test_sham_hard_rule_holds_in_individual_mode():
    # Sham must remain indistinguishable from real regardless of session mode.
    trace = [0.6]
    real = BaselineSmoothingMapper(
        smoothing=1.0, gain=1.0, session_mode=SessionMode.INDIVIDUAL, subject="sub-02"
    )
    sham = BaselineSmoothingMapper(
        smoothing=1.0,
        gain=1.0,
        session_mode=SessionMode.INDIVIDUAL,
        subject="sub-02",
        sham=ShamProvider(trace),
    )
    real_out = real.map(_ins(0.6), FeedbackMode.REAL)
    sham_out = sham.map(_ins(0.0), FeedbackMode.SHAM)  # live value irrelevant
    assert abs(real_out.level - sham_out.level) < 1e-12
    assert sham_out.subject == "sub-02"


def test_hyperscanning_rejects_a_subject():
    with pytest.raises(ValueError):
        BaselineSmoothingMapper(session_mode=SessionMode.HYPERSCANNING, subject="sub-01")


def test_individual_requires_a_subject():
    with pytest.raises(ValueError):
        BaselineSmoothingMapper(session_mode=SessionMode.INDIVIDUAL)


def test_feedbacksample_defaults_are_backward_compatible():
    # Pre-D8 call sites that build a FeedbackSample without the new fields still
    # get a valid shared-car Hyperscanning sample.
    s = FeedbackSample(t_lsl=0.0, level=0.5, mode=FeedbackMode.REAL, raw_ins=0.5)
    assert s.session_mode is SessionMode.HYPERSCANNING
    assert s.subject is None

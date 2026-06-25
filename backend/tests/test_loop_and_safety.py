"""Safety, latency, and end-to-end loop tests."""

from __future__ import annotations

import pytest

from mindx_hnf.contracts import BlockType, FeedbackMode
from mindx_hnf.scripts.simulate import build_demo
from mindx_hnf.session.protocol import (
    MAX_SESSION_MINUTES,
    Block,
    SessionPlan,
    SessionScheduler,
    default_training_plan,
)


def test_session_cap_enforced():
    too_long = SessionPlan(
        label="bad",
        blocks=[Block(BlockType.TASK, MAX_SESSION_MINUTES * 60 + 1)],
    )
    with pytest.raises(ValueError, match="safety cap"):
        too_long.validate()


def test_default_plan_within_cap():
    plan = default_training_plan()
    assert plan.total_seconds <= MAX_SESSION_MINUTES * 60


def test_abort_stops_session():
    plan = default_training_plan()
    sched = SessionScheduler(plan)
    assert sched.current_block(1.0) is not None
    sched.abort()
    assert sched.current_block(1.0) is None
    assert sched.is_finished(1.0)


def test_baseline_block_delivers_no_feedback():
    plan = default_training_plan()
    sched = SessionScheduler(plan)
    block = sched.current_block(1.0)  # first block is baseline
    assert block is not None and block.kind is BlockType.BASELINE
    assert block.feedback is False


def test_end_to_end_loop_runs_and_feedback_rises():
    orch, sink = build_demo(mode=FeedbackMode.REAL, fast=True)
    stats = orch.run()
    assert stats.n_frames > 0
    assert stats.n_feedback > 0
    levels = [s.level for s in sink.published]
    # Ground-truth coherence ramps up, so late feedback should exceed early.
    assert levels[-1] >= levels[0]


def test_loop_latency_under_budget():
    # Per-frame processing must be well under the inter-frame interval so the
    # loop is real-time-capable. Budget here is generous for CI machines.
    orch, _ = build_demo(mode=FeedbackMode.REAL, fast=True)
    stats = orch.run()
    assert stats.max_loop_latency_ms < 50.0, (
        f"per-frame processing too slow: {stats.max_loop_latency_ms:.1f}ms"
    )

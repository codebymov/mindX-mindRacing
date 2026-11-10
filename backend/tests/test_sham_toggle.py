"""Live real/sham switching and the sham dyad's trace.

The sham hard rules still apply: the mapping is identical for both sources and
the sham signal is a real trajectory from another dyad on the same INS scale.
"""

from __future__ import annotations

import pytest

from mindx_hnf.api.sink import NullSink
from mindx_hnf.contracts import FeedbackMode, FeedbackSample
from mindx_hnf.io import sources
from mindx_hnf.scripts.simulate import build_demo
from mindx_hnf.session.mode_switch import FeedbackModeSwitch


@pytest.fixture
def virtual_clock(monkeypatch):
    """Run the loop faster than real time with a shared virtual clock."""
    clock = [0.0]

    class _Time:
        @staticmethod
        def sleep(dt: float) -> None:
            clock[0] += dt

    monkeypatch.setattr(sources, "lsl_clock", lambda: clock[0])
    monkeypatch.setattr(sources, "time", _Time)
    monkeypatch.setattr("mindx_hnf.orchestrator.lsl_clock", lambda: clock[0])
    return clock


class _SwitchingSink(NullSink):
    """Records samples and flips the switch at chosen publish counts."""

    def __init__(self, switch: FeedbackModeSwitch, plan: dict[int, FeedbackMode]):
        super().__init__()
        self._switch = switch
        self._plan = plan

    def publish(self, sample: FeedbackSample) -> None:
        super().publish(sample)
        count = len(self.published)
        if count in self._plan:
            self._switch.set(self._plan[count], "test")


def test_switch_toggles_and_records_history() -> None:
    """Each flip is applied and logged in order."""
    switch = FeedbackModeSwitch(FeedbackMode.REAL)
    assert switch.mode is FeedbackMode.REAL
    assert switch.toggle("a") is FeedbackMode.SHAM
    assert switch.toggle("b") is FeedbackMode.REAL
    switch.set(FeedbackMode.REAL, "c")  # no change: not logged
    assert switch.history == [("a", FeedbackMode.SHAM), ("b", FeedbackMode.REAL)]


def test_live_toggle_changes_the_source_mid_session(virtual_clock) -> None:
    """Samples switch to sham and back exactly where the operator flips."""
    switch = FeedbackModeSwitch(FeedbackMode.REAL)
    sink = _SwitchingSink(switch, {60: FeedbackMode.SHAM, 120: FeedbackMode.REAL})
    orch, _ = build_demo(fast=False, sink=sink, mode_switch=switch)
    orch.run()

    modes = [s.mode for s in sink.published]
    assert len(modes) > 150
    assert all(m is FeedbackMode.REAL for m in modes[:60])
    assert all(m is FeedbackMode.SHAM for m in modes[60:120])
    assert all(m is FeedbackMode.REAL for m in modes[120:])
    assert all(0.0 <= s.level <= 1.0 for s in sink.published)


def test_sham_continues_at_task_time_not_from_the_trace_start(virtual_clock) -> None:
    """Switching to sham at tick k delivers the other dyad's value for tick k."""
    switch = FeedbackModeSwitch(FeedbackMode.REAL)
    sink = _SwitchingSink(switch, {60: FeedbackMode.SHAM})
    orch, _ = build_demo(fast=False, sink=sink, mode_switch=switch)
    orch.run()

    trace = orch.mapper.sham.trace
    assert sink.published[60].mode is FeedbackMode.SHAM
    assert sink.published[60].raw_ins == pytest.approx(trace[60])
    assert sink.published[61].raw_ins == pytest.approx(trace[61])
    # The start of the trace is a different value, so this is not a restart.
    assert trace[60] != pytest.approx(trace[0])


def test_sham_trace_is_on_the_real_ins_scale_and_is_another_dyad(
    virtual_clock,
) -> None:
    """The sham values are plausible INS values and differ from the live dyad's."""
    live_sink = NullSink()
    orch, _ = build_demo(fast=False, sink=live_sink)
    orch.run()
    live = [s.raw_ins for s in live_sink.published]
    trace = list(orch.mapper.sham.trace)

    assert len(trace) >= len(live) - 5
    assert all(0.0 <= v <= 0.4 for v in trace), "off the real INS scale"
    assert trace[: len(live)] != live
    # A different dyad: its mean over the first task block is not the live one's.
    n = len(live) // 3
    assert abs(sum(trace[:n]) / n - sum(live[:n]) / n) > 0.005

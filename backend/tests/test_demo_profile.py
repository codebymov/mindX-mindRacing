"""The synthetic demo's ground truth and the level it produces.

Guards two defects found while tuning the feedback: the coherence ramp used to
finish inside the baseline block (so baseline correction removed the signal), and
the mapper gain left the level near 0.05.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mindx_hnf.contracts import BlockType, FeedbackMode
from mindx_hnf.io import sources
from mindx_hnf.scripts.simulate import (
    COHERENCE_HIGH,
    COHERENCE_LOW,
    build_demo,
    coherence_profile,
)
from mindx_hnf.session.protocol import Block, SessionPlan


def _plan() -> SessionPlan:
    return SessionPlan(
        label="t",
        mode=FeedbackMode.REAL,
        blocks=[
            Block(BlockType.BASELINE, 60.0),
            Block(BlockType.TASK, 120.0, feedback=True),
            Block(BlockType.REST, 10.0),
            Block(BlockType.TASK, 120.0, feedback=True),
        ],
    )


def test_coherence_is_low_through_the_whole_baseline() -> None:
    """The baseline must be measured at resting coherence."""
    fn = coherence_profile(_plan())
    assert all(fn(t) == COHERENCE_LOW for t in (0.0, 30.0, 59.9))


def test_coherence_ramps_inside_each_task_block_and_resets_on_rest() -> None:
    """Coherence rises through a task block and drops back during rest."""
    fn = coherence_profile(_plan())
    assert fn(60.0) == pytest.approx(COHERENCE_LOW)
    assert COHERENCE_LOW < fn(100.0) < COHERENCE_HIGH
    assert fn(170.0) == pytest.approx(COHERENCE_HIGH)
    assert fn(185.0) == COHERENCE_LOW  # rest block
    assert fn(190.0) == pytest.approx(COHERENCE_LOW)  # second task starts low again
    assert fn(300.0) == pytest.approx(COHERENCE_HIGH)


def test_montage_demo_level_climbs_to_a_visible_range(monkeypatch) -> None:
    """The MNE-montage path needs its own gain; the level must still be visible.

    Without ``MONTAGE_GAIN`` the generic gain of 10 saturates the level at 1.0 here.
    """
    clock = [0.0]

    class _Time:
        @staticmethod
        def sleep(dt: float) -> None:
            clock[0] += dt

    monkeypatch.setattr(sources, "lsl_clock", lambda: clock[0])
    monkeypatch.setattr(sources, "time", _Time)
    monkeypatch.setattr("mindx_hnf.orchestrator.lsl_clock", lambda: clock[0])

    montage = Path(__file__).resolve().parents[1] / "configs" / "montage_demo.yaml"
    orch, sink = build_demo(mode=FeedbackMode.REAL, fast=False, montage=montage)
    orch.run()
    levels = [s.level for s in sink.published]
    early = levels[: len(levels) // 10]
    plateau = levels[len(levels) // 2 - 20 : len(levels) // 2]
    assert (
        0.4 < max(levels) <= 1.0
    ), f"max level {max(levels):.2f} outside a visible range"
    assert sum(plateau) / len(plateau) < 0.95, "level saturated at 1.0 (gain too high)"
    assert sum(plateau) / len(plateau) > 2 * (sum(early) / len(early))


def test_full_length_demo_level_climbs_to_a_visible_range(monkeypatch) -> None:
    """Over a full session the level must reach a range the game can show.

    Runs faster than real time with a virtual clock; the estimator and the whole
    pipeline are real.
    """
    clock = [0.0]

    class _Time:
        @staticmethod
        def sleep(dt: float) -> None:
            clock[0] += dt

    monkeypatch.setattr(sources, "lsl_clock", lambda: clock[0])
    monkeypatch.setattr(sources, "time", _Time)
    monkeypatch.setattr("mindx_hnf.orchestrator.lsl_clock", lambda: clock[0])

    orch, sink = build_demo(mode=FeedbackMode.REAL, fast=False)
    orch.run()
    levels = [s.level for s in sink.published]
    assert len(levels) > 100
    early = levels[: len(levels) // 10]
    late_task = levels[len(levels) // 3 : len(levels) // 2]
    assert max(levels) > 0.5, f"level never became visible: max={max(levels):.2f}"
    assert sum(late_task) / len(late_task) > 2 * (sum(early) / len(early))

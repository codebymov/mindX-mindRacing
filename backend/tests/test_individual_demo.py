"""Individual-mode DEMO PLACEHOLDER: per-player feature, routing and the CLI guard."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from mindx_hnf.api.sink import NullSink, encode_feedback
from mindx_hnf.contracts import FeedbackMode, HemoFrame, SessionMode
from mindx_hnf.io import sources
from mindx_hnf.scripts import simulate
from mindx_hnf.scripts.individual_demo import (
    BandPowerFeature,
    build_individual_demo,
)

FS = 7.81
SUBJECTS = ("sub-01", "sub-02")


def _frame(t: float, a: float, b: float) -> HemoFrame:
    """A frame whose channel-mean HbO is a 0.05 Hz sine of amplitude a (b) per player."""
    n = 8
    ts = t + np.arange(n) / FS
    one = np.tile(a * np.sin(2 * np.pi * 0.05 * ts), (3, 1))
    two = np.tile(b * np.sin(2 * np.pi * 0.05 * ts), (3, 1))
    return HemoFrame(
        t_lsl=t,
        hbo={"sub-01": one, "sub-02": two},
        hbr={"sub-01": one, "sub-02": two},
        fs=FS,
    )


def test_feature_follows_each_players_own_activation() -> None:
    """A player's value depends on their own signal, not on the other player's."""
    feature = BandPowerFeature(SUBJECTS, FS, window_s=22.0)
    last = None
    for i in range(60):
        out = feature.update(_frame(i * 8 / FS, a=1.0, b=0.1))
        last = out or last
    assert last is not None
    strong, weak = last["sub-01"].value, last["sub-02"].value
    assert strong > 20 * weak  # power scales with amplitude squared (100x here)

    swapped = BandPowerFeature(SUBJECTS, FS, window_s=22.0)
    for i in range(60):
        out = swapped.update(_frame(i * 8 / FS, a=0.1, b=1.0))
        last = out or last
    assert last["sub-02"].value > 20 * last["sub-01"].value


def test_feature_waits_for_a_full_window() -> None:
    """No value is emitted before the window is full."""
    feature = BandPowerFeature(SUBJECTS, FS, window_s=22.0)
    assert feature.update(_frame(0.0, 1.0, 1.0)) is None


@pytest.fixture
def virtual_clock(monkeypatch):
    """Run the loop faster than real time with a virtual clock."""
    clock = [0.0]

    class _Time:
        @staticmethod
        def sleep(dt: float) -> None:
            clock[0] += dt

    monkeypatch.setattr(sources, "lsl_clock", lambda: clock[0])
    monkeypatch.setattr(sources, "time", _Time)
    return clock


def test_full_session_gives_each_player_their_own_signal(virtual_clock) -> None:
    """Two players, two different levels, each sample tagged with its subject."""
    loop, sink = build_individual_demo(fast=False)
    loop.run()
    published = sink.published  # type: ignore[attr-defined]
    by_subject = {s: [x for x in published if x.subject == s] for s in SUBJECTS}
    assert all(len(v) > 100 for v in by_subject.values())
    assert all(x.session_mode is SessionMode.INDIVIDUAL for x in published)
    assert all(x.mode is FeedbackMode.REAL for x in published)

    peak = {s: max(x.level for x in v) for s, v in by_subject.items()}
    assert peak["sub-01"] > 0.5, peak
    assert peak["sub-01"] - peak["sub-02"] > 0.2, peak  # clearly different speeds

    # The wire carries each sample's subject as index 0 / 1 (the game routes on it).
    index = {s: encode_feedback(by_subject[s][0], SUBJECTS)[4] for s in SUBJECTS}
    assert index == {"sub-01": 0.0, "sub-02": 1.0}


def test_hyperscanning_path_is_unchanged() -> None:
    """The default demo still publishes ONE shared sample, not per-subject ones."""
    orch, sink = simulate.build_demo(mode=FeedbackMode.REAL, fast=True)
    orch.run()
    published = sink.published  # type: ignore[attr-defined]
    assert published
    assert all(x.subject is None for x in published)
    assert all(x.session_mode is SessionMode.HYPERSCANNING for x in published)


@pytest.mark.parametrize("flag", ["--sham", "--toggle"])
def test_individual_rejects_sham_and_toggle(monkeypatch, flag: str) -> None:
    """Sham and the operator toggle are not supported in the placeholder."""
    monkeypatch.setattr(sys, "argv", ["simulate", "--individual", flag])
    with pytest.raises(SystemExit) as exc:
        simulate.main()
    assert exc.value.code == 2


def test_null_sink_default_is_returned_and_used(virtual_clock) -> None:
    """With no sink given, the returned sink is the one the loop publishes to."""
    loop, sink = build_individual_demo(fast=True)
    assert isinstance(sink, NullSink)
    assert loop.sink is sink

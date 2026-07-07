"""LSL outlet round-trip test (the backend->Unity seam).

Skipped unless the optional [hardware] extra (pylsl + liblsl) is installed, so
base CI stays hardware-free (D2). Where pylsl IS present, it pins the wire
contract Unity's LslFeedbackTransport depends on: channel order, numeric
encoding of the string fields, the shared-subject sentinel, and — critically —
that the sample keeps its own LSL timestamp (one clock of record, D3).
"""

from __future__ import annotations

import time

import pytest

pytest.importorskip("pylsl")

from pylsl import StreamInlet, resolve_byprop  # noqa: E402

from mindx_hnf.api.sink import (  # noqa: E402
    FEEDBACK_CHANNELS,
    MODE_CODE,
    SESSION_MODE_CODE,
    SHARED_SUBJECT_INDEX,
    LSLOutletSink,
)
from mindx_hnf.contracts import (  # noqa: E402
    FeedbackMode,
    FeedbackSample,
    SessionMode,
)


def _resolve_inlet(name: str = "mindx_feedback") -> StreamInlet:
    streams = resolve_byprop("name", name, minimum=1, timeout=5.0)
    assert streams, f"outlet {name!r} did not resolve on the network"
    inlet = StreamInlet(streams[0])
    inlet.open_stream(timeout=5.0)
    return inlet


def _push_until_received(sink: LSLOutletSink, inlet: StreamInlet, sample):
    """Publish `sample` until the inlet delivers one.

    The outlet<->inlet handshake takes a moment; a single push right after
    connecting is routinely dropped. Retrying is how LSL round-trip tests are
    written — it does not change the delivered values (every push is identical).
    """
    for _ in range(50):
        sink.publish(sample)
        vec, ts = inlet.pull_sample(timeout=0.2)
        if vec is not None:
            return vec, ts
        time.sleep(0.05)
    raise AssertionError("no sample received from the outlet within budget")


def test_hyperscanning_sample_round_trips_with_its_timestamp():
    sink = LSLOutletSink(subjects=("sub-01", "sub-02"))
    inlet = _resolve_inlet()
    sample = FeedbackSample(
        t_lsl=12345.678,
        level=0.42,
        mode=FeedbackMode.REAL,
        raw_ins=0.37,
        session_mode=SessionMode.HYPERSCANNING,
        subject=None,
    )
    vec, ts = _push_until_received(sink, inlet, sample)
    assert len(vec) == len(FEEDBACK_CHANNELS)
    assert vec[0] == pytest.approx(0.42, abs=1e-6)
    assert vec[1] == pytest.approx(0.37, abs=1e-6)
    assert vec[2] == pytest.approx(MODE_CODE[FeedbackMode.REAL])
    assert vec[3] == pytest.approx(SESSION_MODE_CODE[SessionMode.HYPERSCANNING])
    assert vec[4] == pytest.approx(SHARED_SUBJECT_INDEX)  # shared car
    # The pushed timestamp is the sample's LSL time, not a fresh one.
    assert ts == pytest.approx(12345.678, abs=1e-6)
    sink.close()


def test_individual_sample_routes_to_subject_index():
    sink = LSLOutletSink(subjects=("sub-01", "sub-02"))
    inlet = _resolve_inlet()
    sample = FeedbackSample(
        t_lsl=1.0,
        level=0.9,
        mode=FeedbackMode.SHAM,
        raw_ins=0.5,
        session_mode=SessionMode.INDIVIDUAL,
        subject="sub-02",
    )
    vec, _ = _push_until_received(sink, inlet, sample)
    assert vec[2] == pytest.approx(MODE_CODE[FeedbackMode.SHAM])
    assert vec[3] == pytest.approx(SESSION_MODE_CODE[SessionMode.INDIVIDUAL])
    assert vec[4] == pytest.approx(1.0)  # index of sub-02
    sink.close()

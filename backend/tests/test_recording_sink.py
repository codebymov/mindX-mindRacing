"""Tests for ``RecordingSink``: forwarding, CSV content, and file hygiene."""

from __future__ import annotations

import csv
from pathlib import Path

from mindx_hnf.api.sink import NullSink, RecordingSink
from mindx_hnf.contracts import FeedbackMode, FeedbackSample, SessionMode


def _sample(t: float, level: float, raw: float) -> FeedbackSample:
    return FeedbackSample(
        t_lsl=t,
        level=level,
        mode=FeedbackMode.REAL,
        raw_ins=raw,
        session_mode=SessionMode.HYPERSCANNING,
    )


def test_forwards_samples_unchanged_and_records_them() -> None:
    """Every sample reaches the wrapped sink and is also recorded."""
    inner = NullSink()
    sink = RecordingSink(inner)
    samples = [_sample(1.0, 0.2, 0.3), _sample(2.0, 0.4, 0.5)]
    for s in samples:
        sink.publish(s)
    assert inner.published == samples
    assert sink.published == samples


def test_records_without_an_inner_sink() -> None:
    """With no wrapped sink the wrapper only records."""
    sink = RecordingSink()
    sink.publish(_sample(1.0, 0.2, 0.3))
    sink.close()
    assert len(sink.published) == 1


def test_csv_is_written_on_close_not_before(tmp_path: Path) -> None:
    """The file appears only at close, keeping disk I/O off the hot path."""
    target = tmp_path / "nested" / "run.csv"
    sink = RecordingSink(NullSink(), target)
    sink.publish(_sample(1.5, 0.25, 0.75))
    assert not target.exists()
    sink.close()
    assert target.exists()
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0].keys()) == list(RecordingSink.COLUMNS)
    assert float(rows[0]["level"]) == 0.25
    assert float(rows[0]["raw_ins"]) == 0.75
    assert rows[0]["mode"] == "real"


def test_csv_uses_lf_line_endings(tmp_path: Path) -> None:
    """The repo is LF; Windows must not write CRLF."""
    target = tmp_path / "run.csv"
    sink = RecordingSink(None, target)
    sink.publish(_sample(1.0, 0.1, 0.2))
    sink.close()
    assert b"\r" not in target.read_bytes()

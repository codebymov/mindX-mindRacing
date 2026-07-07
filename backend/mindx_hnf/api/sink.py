"""Feedback transport sinks."""

from __future__ import annotations

from typing import Protocol

from mindx_hnf.contracts import FeedbackSample


class FeedbackSink(Protocol):
    def publish(self, sample: FeedbackSample) -> None: ...

    def close(self) -> None: ...


class NullSink:
    """Discards samples. Used in tests/simulation when no game is attached."""

    def __init__(self) -> None:
        self.published: list[FeedbackSample] = []

    def publish(self, sample: FeedbackSample) -> None:
        self.published.append(sample)

    def close(self) -> None:
        pass


class LSLOutletSink:  # pragma: no cover - needs pylsl
    """Publishes feedback as an LSL stream Unity subscribes to.

    Keeps the game on the same clock as acquisition. Implement with pylsl
    StreamOutlet; push (level, raw_ins, mode, session_mode, subject) per sample
    with the LSL timestamp so the game can route the sample to the right car(s).
    """

    def __init__(self, stream_name: str = "mindx_feedback") -> None:
        self.stream_name = stream_name
        raise NotImplementedError(
            "Implement with pylsl StreamOutlet. Mirror NullSink's interface."
        )

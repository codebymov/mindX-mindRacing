"""Feedback transport sinks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from mindx_hnf.contracts import (
    FeedbackMode,
    FeedbackSample,
    SessionMode,
    SubjectId,
)

# Numeric codes for the string-valued fields so the whole sample fits one
# float32 LSL vector. Unity decodes these back to strings for logging only.
# Keep in sync with unity/Assets/Scripts/LslFeedbackTransport.cs.
MODE_CODE: dict[FeedbackMode, float] = {FeedbackMode.REAL: 0.0, FeedbackMode.SHAM: 1.0}
SESSION_MODE_CODE: dict[SessionMode, float] = {
    SessionMode.HYPERSCANNING: 0.0,
    SessionMode.INDIVIDUAL: 1.0,
}
#: subject_index sentinel for the shared dyad signal (Hyperscanning, both cars).
SHARED_SUBJECT_INDEX: float = -1.0

#: Feedback stream channel layout (order is the contract with LslFeedbackTransport).
FEEDBACK_CHANNELS: tuple[str, ...] = (
    "level",
    "raw_ins",
    "mode",
    "session_mode",
    "subject_index",
)


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
    """Publishes feedback as an LSL stream both Unity headsets subscribe to.

    This keeps the game on the *same clock of record* as acquisition (D3): each
    sample is pushed with its own LSL timestamp (``sample.t_lsl``), not a fresh
    one, so provenance is preserved end-to-end and the feedback stream can be
    recorded into the same XDF as the neural streams for reproducibility.

    The sample is encoded as one 5-channel float32 vector — see
    ``FEEDBACK_CHANNELS``. The string fields (mode, session_mode, subject) are
    encoded numerically; Unity decodes them back for logging only and never
    branches on ``mode`` (sham hard-rule).

    ``subjects`` maps the per-subject Individual-mode signal to a stable channel
    index the game routes on. In Hyperscanning ``subject`` is None → the shared
    ``SHARED_SUBJECT_INDEX`` drives both cars.

    pylsl is imported lazily so the package still imports without the optional
    ``[hardware]`` extra installed.
    """

    def __init__(
        self,
        stream_name: str = "mindx_feedback",
        *,
        subjects: Sequence[SubjectId] = (),
        source_id: str = "mindx_feedback_v1",
        fs: float = 0.0,
    ) -> None:
        from pylsl import IRREGULAR_RATE, StreamInfo, StreamOutlet, cf_float32

        self.stream_name = stream_name
        self._subjects = tuple(subjects)
        info = StreamInfo(
            name=stream_name,
            type="mindx_feedback",
            channel_count=len(FEEDBACK_CHANNELS),
            # Feedback ticks are irregular (INS update cadence), so advertise
            # IRREGULAR_RATE and rely on the per-sample LSL timestamp.
            nominal_srate=fs if fs > 0 else IRREGULAR_RATE,
            channel_format=cf_float32,
            source_id=source_id,
        )
        channels = info.desc().append_child("channels")
        for label in FEEDBACK_CHANNELS:
            channels.append_child("channel").append_child_value("label", label)
        # Self-describe the subject index -> id mapping so a recording is
        # reconstructable without the run config.
        subj_desc = info.desc().append_child("subjects")
        for i, sid in enumerate(self._subjects):
            subj_desc.append_child_value(str(i), sid)
        self._outlet: StreamOutlet | None = StreamOutlet(info)

    def _subject_index(self, subject: SubjectId | None) -> float:
        if subject is None:
            return SHARED_SUBJECT_INDEX
        try:
            return float(self._subjects.index(subject))
        except ValueError:
            # Unknown subject is a config error; route nowhere rather than to the
            # wrong car. Kept off the raising path — this is the hot loop.
            return SHARED_SUBJECT_INDEX

    def publish(self, sample: FeedbackSample) -> None:
        if self._outlet is None:
            return
        vector = [
            float(sample.level),
            float(sample.raw_ins),
            MODE_CODE[sample.mode],
            SESSION_MODE_CODE[sample.session_mode],
            self._subject_index(sample.subject),
        ]
        # Push with the sample's own LSL timestamp — one clock of record.
        self._outlet.push_sample(vector, timestamp=sample.t_lsl)

    def close(self) -> None:
        self._outlet = None

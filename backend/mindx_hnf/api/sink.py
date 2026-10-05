"""Feedback transport sinks.

Sinks deliver ``FeedbackSample``s to the game. ``LSLOutletSink`` is the live
transport (D9); ``NullSink`` collects samples for tests and simulation.

Attributes:
    MODE_CODE: Numeric code per ``FeedbackMode``, so the whole sample fits one
        float32 LSL vector.
    SESSION_MODE_CODE: Numeric code per ``SessionMode``.
    SHARED_SUBJECT_INDEX: ``subject_index`` sentinel for the shared dyad signal
        (Hyperscanning, both cars).
    FEEDBACK_CHANNELS: Feedback stream channel layout; the order is the
        contract with ``LslFeedbackTransport.cs``.
"""

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
#: subject_index sentinel for a sample naming a subject this sink doesn't know.
#: Unity drives NO car with it (a config error must never move the wrong car).
UNROUTABLE_SUBJECT_INDEX: float = -2.0

#: Feedback stream channel layout (order is the contract with LslFeedbackTransport).
FEEDBACK_CHANNELS: tuple[str, ...] = (
    "level",
    "raw_ins",
    "mode",
    "session_mode",
    "subject_index",
)


def encode_feedback(
    sample: FeedbackSample, subjects: Sequence[SubjectId]
) -> list[float]:
    """Encodes a feedback sample as the LSL wire vector.

    The wire format is specified once in ``contracts/feedback_wire.json`` and
    decoded by ``FeedbackWire.Decode`` on the Unity side; both are tested
    against that file's golden cases.

    Args:
        sample: The feedback sample to encode.
        subjects: Subject ids in channel-index order; a subject's position is
            the ``subject_index`` Unity routes on.

    Returns:
        One float per entry of ``FEEDBACK_CHANNELS``, in that order.
    """
    if sample.subject is None:
        subject_index = SHARED_SUBJECT_INDEX
    elif sample.subject in subjects:
        subject_index = float(list(subjects).index(sample.subject))
    else:
        # Kept off the raising path — this is the hot loop.
        subject_index = UNROUTABLE_SUBJECT_INDEX
    return [
        float(sample.level),
        float(sample.raw_ins),
        MODE_CODE[sample.mode],
        SESSION_MODE_CODE[sample.session_mode],
        subject_index,
    ]


class FeedbackSink(Protocol):
    """Transport-agnostic destination for delivered feedback samples."""

    def publish(self, sample: FeedbackSample) -> None:
        """Deliver one sample to the game.

        Args:
            sample: The feedback sample to deliver.
        """
        ...

    def close(self) -> None:
        """Release the transport; later ``publish`` calls are no-ops."""
        ...


class NullSink:
    """Collects samples instead of sending them anywhere.

    Used in tests and simulation when no game is attached.

    Attributes:
        published: Every sample passed to ``publish``, in order.
    """

    def __init__(self) -> None:
        """Create an empty sink."""
        self.published: list[FeedbackSample] = []

    def publish(self, sample: FeedbackSample) -> None:
        """Record the sample.

        Args:
            sample: The feedback sample to record.
        """
        self.published.append(sample)

    def close(self) -> None:
        """Do nothing; there is no transport to release."""


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

    Attributes:
        stream_name: Name of the published LSL stream.
    """

    def __init__(
        self,
        stream_name: str = "mindx_feedback",
        *,
        subjects: Sequence[SubjectId] = (),
        source_id: str = "mindx_feedback_v1",
        fs: float = 0.0,
    ) -> None:
        """Create and advertise the LSL outlet.

        Args:
            stream_name: LSL stream name Unity resolves.
            subjects: Subject ids in index order; index ``i`` is sent as
                ``subject_index == i`` and described in the stream metadata.
            source_id: Stable LSL source id, so inlets can recover after a
                restart.
            fs: Nominal rate in Hz; 0 advertises an irregular rate.

        Raises:
            ImportError: If pylsl (the ``[hardware]`` extra) is not installed.
        """
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

    def publish(self, sample: FeedbackSample) -> None:
        """Push the sample with its own LSL timestamp.

        Args:
            sample: The feedback sample to encode and push.
        """
        if self._outlet is None:
            return
        vector = encode_feedback(sample, self._subjects)
        # Push with the sample's own LSL timestamp — one clock of record.
        self._outlet.push_sample(vector, timestamp=sample.t_lsl)

    def close(self) -> None:
        """Drop the outlet; later ``publish`` calls are no-ops."""
        self._outlet = None

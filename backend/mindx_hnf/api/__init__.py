"""Transport bridge to the Unity XR game.

Publishes `FeedbackSample`s to Unity. Two transports are anticipated (CLAUDE.md
§7 open decision): an LSL outlet (keeps everything on one clock, integrates with
the existing LSL fabric) or a websocket (simpler for Unity, needs explicit time
handling). The `FeedbackSink` protocol abstracts the choice.
"""

from mindx_hnf.api.sink import FeedbackSink, NullSink

__all__ = ["FeedbackSink", "NullSink"]

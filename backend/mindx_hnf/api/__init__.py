"""Transport bridge to the Unity XR game.

Publishes `FeedbackSample`s to Unity over LSL (D9): the LSL outlet keeps the game
on the one clock of record and lets the feedback stream be recorded alongside the
neural streams. The `FeedbackSink` protocol abstracts the transport so tests and
simulation use `NullSink` and the live game uses `LSLOutletSink`.
"""

from mindx_hnf.api.sink import FeedbackSink, LSLOutletSink, NullSink

__all__ = ["FeedbackSink", "LSLOutletSink", "NullSink"]

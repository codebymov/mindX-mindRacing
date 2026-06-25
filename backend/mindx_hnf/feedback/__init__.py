"""Feedback stage: INS -> delivered feedback level.

Handles baseline correction (relative to the resting block), temporal smoothing,
clamping to [0, 1], and sham substitution. The output `FeedbackSample.level`
is what the XR game maps onto car speed and audio pitch/gain.

Sham integrity rule (see CLAUDE.md §4): in sham mode the level is computed from a
*replayed real signal of another dyad for the same session/task*, run through the
identical mapping. There is no participant-perceptible difference between real
and sham — `mode` is recorded for analysis only.
"""

from mindx_hnf.feedback.mapper import BaselineSmoothingMapper, ShamProvider

__all__ = ["BaselineSmoothingMapper", "ShamProvider"]

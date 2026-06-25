"""Experiment session scheduling.

Encodes the training protocol from the project outline (Fig. 2): a baseline
resting block followed by alternating task/rest blocks; one of three sessions is
fully sham. Enforces the ~30-minute hard cap and supports immediate abort.
"""

from mindx_hnf.session.protocol import Block, SessionPlan, SessionScheduler

__all__ = ["Block", "SessionPlan", "SessionScheduler"]

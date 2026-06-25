"""Persistence track (OFF the real-time hot path).

Writes BIDS-compliant neural data, versions artifacts with DataLad, and stores
experiment metadata + pseudonymized survey/sensor data in Postgres. Every
artifact is stamped with the git SHA and config hash for reproducibility.

CRITICAL: nothing in this package may block the feedback loop. The orchestrator
hands frames to storage via a non-blocking queue; if persistence falls behind or
fails, the real-time loop continues and storage degrades gracefully.
"""

from mindx_hnf.storage.recorder import ArtifactRecorder

__all__ = ["ArtifactRecorder"]

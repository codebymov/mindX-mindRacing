"""Operator-controlled switch between real and sham feedback.

The switch is an operator tool (a presenter or experimenter console). Nothing
participant-facing reads it: the feedback path is identical for both modes and
only the signal source changes, so the sham hard rule is kept.
"""

from __future__ import annotations

import logging
import threading

from mindx_hnf.contracts import FeedbackMode

logger = logging.getLogger(__name__)


class FeedbackModeSwitch:
    """Thread-safe holder of the current feedback mode.

    The orchestrator reads ``mode`` once per frame; an operator thread flips it.

    Attributes:
        history: ``(label, mode)`` pairs of every change, oldest first.
    """

    def __init__(self, initial: FeedbackMode = FeedbackMode.REAL) -> None:
        """Create the switch.

        Args:
            initial: Mode the session starts in.
        """
        self._mode = initial
        self._lock = threading.Lock()
        self.history: list[tuple[str, FeedbackMode]] = []

    @property
    def mode(self) -> FeedbackMode:
        """Gets the current feedback mode."""
        with self._lock:
            return self._mode

    def set(self, mode: FeedbackMode, label: str = "operator") -> None:
        """Set the mode and record the change.

        Args:
            mode: The mode to switch to.
            label: Who or what requested the change, for the log.
        """
        with self._lock:
            if mode is self._mode:
                return
            self._mode = mode
            self.history.append((label, mode))
        logger.info("Feedback source switched to %s by %s", mode.value, label)

    def toggle(self, label: str = "operator") -> FeedbackMode:
        """Flip between real and sham.

        Args:
            label: Who or what requested the change, for the log.

        Returns:
            The mode after the flip.
        """
        new = FeedbackMode.SHAM if self.mode is FeedbackMode.REAL else FeedbackMode.REAL
        self.set(new, label)
        return new

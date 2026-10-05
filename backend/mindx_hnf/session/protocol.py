"""Training protocol: blocks, plan, and a safety-aware scheduler.

Attributes:
    MAX_SESSION_MINUTES: Hard safety cap on a single training session, in
        minutes. Per the ethics section of the project outline, sessions are
        restricted to ~30 min to limit fNIRS-cap and XR-exposure discomfort.
"""

from __future__ import annotations

from dataclasses import dataclass

from mindx_hnf.contracts import BlockType, FeedbackMode

# Hard safety cap on a single training session (minutes). See ethics section of
# the project outline: sessions restricted to ~30 min to limit fNIRS-cap and
# XR-exposure discomfort.
MAX_SESSION_MINUTES = 30.0


@dataclass(slots=True)
class Block:
    """One protocol block.

    Attributes:
        kind: What the block is (baseline, task, rest, transfer).
        duration_s: Block length in seconds.
        feedback: Whether feedback is delivered during this block.
    """

    kind: BlockType
    duration_s: float
    feedback: bool = False  # whether feedback is delivered during this block


@dataclass(slots=True)
class SessionPlan:
    """An ordered list of blocks plus the session-level feedback mode.

    Attributes:
        blocks: The blocks in run order.
        mode: REAL for two of three sessions and SHAM for one (randomized across
            participants, decided at enrollment, not here).
        label: Human-readable session label used in messages.
    """

    blocks: list[Block]
    mode: FeedbackMode = FeedbackMode.REAL
    label: str = ""

    @property
    def total_seconds(self) -> float:
        """Total planned duration of all blocks, in seconds."""
        return sum(b.duration_s for b in self.blocks)

    def validate(self) -> None:
        """Check the plan against the safety cap.

        Raises:
            ValueError: If the plan exceeds ``MAX_SESSION_MINUTES`` or has no
                blocks.
        """
        if self.total_seconds > MAX_SESSION_MINUTES * 60.0:
            raise ValueError(
                f"Session '{self.label}' is {self.total_seconds/60:.1f} min, "
                f"exceeds the {MAX_SESSION_MINUTES:.0f} min safety cap."
            )
        if not self.blocks:
            raise ValueError("Session plan has no blocks.")


def default_training_plan(mode: FeedbackMode = FeedbackMode.REAL) -> SessionPlan:
    """Build a representative training session.

    Baseline movie -> [task / rest] x N. Mirrors Fig. 2 of the outline;
    durations are illustrative, tune them in config.

    Args:
        mode: Real or sham feedback for the whole session.

    Returns:
        A validated session plan.
    """
    plan = SessionPlan(
        label="training",
        mode=mode,
        blocks=[
            Block(BlockType.BASELINE, 5 * 60),
            Block(BlockType.TASK, 5 * 60, feedback=True),
            Block(BlockType.REST, 30),
            Block(BlockType.TASK, 5 * 60, feedback=True),
            Block(BlockType.REST, 2 * 60),
            Block(BlockType.TASK, 5 * 60, feedback=True),
            Block(BlockType.REST, 30),
        ],
    )
    plan.validate()
    return plan


class SessionScheduler:
    """Drives a SessionPlan over wall/LSL time and exposes the current block.

    The scheduler is the safety boundary: it never lets a session exceed the cap
    (plans are validated up front) and `abort()` stops everything immediately.
    The real-time loop queries `current_block(t)` each tick to decide whether to
    deliver feedback and (in sham sessions) which source to use.

    Attributes:
        plan: The validated plan being driven.
    """

    def __init__(self, plan: SessionPlan) -> None:
        """Validate the plan and precompute block boundaries.

        Args:
            plan: The session plan to drive.

        Raises:
            ValueError: If the plan fails ``SessionPlan.validate``.
        """
        plan.validate()
        self.plan = plan
        self._aborted = False
        self._boundaries: list[tuple[float, float, Block]] = []
        t = 0.0
        for b in plan.blocks:
            self._boundaries.append((t, t + b.duration_s, b))
            t += b.duration_s
        self._end = t

    def current_block(self, elapsed_s: float) -> Block | None:
        """Return the block active at ``elapsed_s``.

        Args:
            elapsed_s: Seconds since session start (LSL clock).

        Returns:
            The active block, or None if aborted or past the end.
        """
        if self._aborted or elapsed_s >= self._end:
            return None
        for start, end, block in self._boundaries:
            if start <= elapsed_s < end:
                return block
        return None

    def feedback_mode(self) -> FeedbackMode:
        """Return the session-level feedback mode (real or sham).

        Returns:
            The plan's feedback mode.
        """
        return self.plan.mode

    def is_finished(self, elapsed_s: float) -> bool:
        """Whether the session is over.

        Args:
            elapsed_s: Seconds since session start (LSL clock).

        Returns:
            True if aborted or ``elapsed_s`` is past the last block.
        """
        return self._aborted or elapsed_s >= self._end

    def abort(self) -> None:
        """Stop the session immediately; no further block is returned."""
        self._aborted = True

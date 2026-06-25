"""Training protocol: blocks, plan, and a safety-aware scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field

from mindx_hnf.contracts import BlockType, FeedbackMode

# Hard safety cap on a single training session (minutes). See ethics section of
# the project outline: sessions restricted to ~30 min to limit fNIRS-cap and
# XR-exposure discomfort.
MAX_SESSION_MINUTES = 30.0


@dataclass(slots=True)
class Block:
    kind: BlockType
    duration_s: float
    feedback: bool = False  # whether feedback is delivered during this block


@dataclass(slots=True)
class SessionPlan:
    """An ordered list of blocks plus the session-level feedback mode.

    `mode` is REAL for two of three sessions and SHAM for one (randomized across
    participants, decided at enrollment, not here).
    """

    blocks: list[Block]
    mode: FeedbackMode = FeedbackMode.REAL
    label: str = ""

    @property
    def total_seconds(self) -> float:
        return sum(b.duration_s for b in self.blocks)

    def validate(self) -> None:
        if self.total_seconds > MAX_SESSION_MINUTES * 60.0:
            raise ValueError(
                f"Session '{self.label}' is {self.total_seconds/60:.1f} min, "
                f"exceeds the {MAX_SESSION_MINUTES:.0f} min safety cap."
            )
        if not self.blocks:
            raise ValueError("Session plan has no blocks.")


def default_training_plan(mode: FeedbackMode = FeedbackMode.REAL) -> SessionPlan:
    """A representative training session (durations illustrative, tune in config).

    baseline movie -> [task / rest] x N. Mirrors Fig. 2 of the outline.
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
    """

    def __init__(self, plan: SessionPlan) -> None:
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
        if self._aborted or elapsed_s >= self._end:
            return None
        for start, end, block in self._boundaries:
            if start <= elapsed_s < end:
                return block
        return None

    def feedback_mode(self) -> FeedbackMode:
        return self.plan.mode

    def is_finished(self, elapsed_s: float) -> bool:
        return self._aborted or elapsed_s >= self._end

    def abort(self) -> None:
        self._aborted = True

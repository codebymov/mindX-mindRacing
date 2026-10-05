r"""The closed-loop orchestrator.

Wires the real-time track together:

    source -> preprocessor -> ins -> (baseline | feedback) -> sink
                                          \-> recorder (non-blocking)

It is transport- and hardware-agnostic: pass any `FrameSource`, `INSEstimator`,
`FeedbackMapper`, `FeedbackSink`, and a `SessionScheduler`. This is the single
place the pipeline is assembled, so it is also where latency is measured.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from mindx_hnf.api.sink import FeedbackSink
from mindx_hnf.contracts import (
    BaselineLockable,
    BlockType,
    FeedbackMapper,
    INSEstimator,
    OnlinePreprocessor,
)
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper
from mindx_hnf.io.sources import FrameSource, lsl_clock
from mindx_hnf.session.protocol import SessionScheduler
from mindx_hnf.storage.recorder import ArtifactRecorder

logger = logging.getLogger(__name__)


@dataclass
class LoopStats:
    """Counters and latency figures of one orchestrator run.

    Attributes:
        n_frames: Raw frames processed.
        n_ins: INS values produced.
        n_feedback: Feedback samples published.
        max_loop_latency_ms: Worst per-frame processing time.
        mean_loop_latency_ms: Mean per-frame processing time.
    """

    n_frames: int = 0
    n_ins: int = 0
    n_feedback: int = 0
    max_loop_latency_ms: float = 0.0
    mean_loop_latency_ms: float = 0.0


class Orchestrator:
    """Runs the closed loop: source -> preprocess -> INS -> feedback -> sink.

    Attributes:
        source: Frame source (synthetic or LSL).
        preprocessor: Causal per-subject preprocessing.
        ins: Joint INS estimator.
        mapper: INS -> feedback mapping (incl. sham substitution).
        sink: Feedback transport to the game.
        scheduler: Block schedule and safety boundary.
        recorder: Optional non-blocking persistence.
        stats: Counters of the current/last run.
    """

    def __init__(
        self,
        *,
        source: FrameSource,
        preprocessor: OnlinePreprocessor,
        ins: INSEstimator,
        mapper: FeedbackMapper,
        sink: FeedbackSink,
        scheduler: SessionScheduler,
        recorder: ArtifactRecorder | None = None,
    ) -> None:
        """Wire the stages; nothing runs until ``run``.

        Args:
            source: Frame source (synthetic or LSL).
            preprocessor: Causal per-subject preprocessing.
            ins: Joint INS estimator.
            mapper: INS -> feedback mapping (incl. sham substitution).
            sink: Feedback transport to the game; closed when the run ends.
            scheduler: Block schedule and safety boundary.
            recorder: Optional non-blocking persistence.
        """
        self.source = source
        self.preprocessor = preprocessor
        self.ins = ins
        self.mapper = mapper
        self.sink = sink
        self.scheduler = scheduler
        self.recorder = recorder
        self.stats = LoopStats()

    def run(self) -> LoopStats:
        """Run the loop until the source ends or the session is finished.

        Baseline-block INS establishes the feedback baseline; the preprocessor's
        references are locked on the first frame after the baseline block.

        Returns:
            Frame/INS/feedback counts and per-frame latency.
        """
        if self.recorder is not None:
            self.recorder.start()
        t_start = lsl_clock()
        latency_acc = 0.0
        mode = self.scheduler.feedback_mode()
        try:
            for frame in self.source.frames():
                tick = time.perf_counter()
                elapsed = frame.t_lsl - t_start
                block = self.scheduler.current_block(elapsed)
                if block is None and self.scheduler.is_finished(elapsed):
                    break

                # Freeze preprocessing references (OD) once the baseline block is
                # over, BEFORE processing the first post-baseline frame.
                if (
                    isinstance(self.preprocessor, BaselineLockable)
                    and not self.preprocessor.baseline_locked
                    and (block is None or block.kind is not BlockType.BASELINE)
                ):
                    self.preprocessor.lock_baseline()
                hemo = self.preprocessor.process(frame)
                self.stats.n_frames += 1
                if self.recorder is not None:
                    self.recorder.offer("raw", frame)

                ins_sample = self.ins.update(hemo)
                if ins_sample is not None:
                    self.stats.n_ins += 1
                    if self.recorder is not None:
                        self.recorder.offer("ins", ins_sample)

                    if block is not None and block.kind is BlockType.BASELINE:
                        # Establish baseline; no feedback delivered.
                        if isinstance(self.mapper, BaselineSmoothingMapper):
                            self.mapper.observe_baseline(ins_sample)
                    elif block is not None and block.feedback:
                        if (
                            isinstance(self.mapper, BaselineSmoothingMapper)
                            and not self.mapper._baseline_locked  # noqa: SLF001
                        ):
                            self.mapper.lock_baseline()
                        fb = self.mapper.map(ins_sample, mode)
                        self.sink.publish(fb)
                        self.stats.n_feedback += 1
                        if self.recorder is not None:
                            self.recorder.offer("feedback", fb)

                loop_ms = (time.perf_counter() - tick) * 1000.0
                latency_acc += loop_ms
                self.stats.max_loop_latency_ms = max(
                    self.stats.max_loop_latency_ms, loop_ms
                )
        finally:
            self.sink.close()
            if self.recorder is not None:
                self.recorder.stop()
        if self.stats.n_frames:
            self.stats.mean_loop_latency_ms = latency_acc / self.stats.n_frames
        logger.info(
            "Loop done: frames=%d ins=%d fb=%d max_loop=%.2fms mean_loop=%.2fms",
            self.stats.n_frames,
            self.stats.n_ins,
            self.stats.n_feedback,
            self.stats.max_loop_latency_ms,
            self.stats.mean_loop_latency_ms,
        )
        return self.stats

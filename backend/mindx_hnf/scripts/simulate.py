"""Run the entire closed loop on synthetic data — no hardware required.

This is the development and CI workhorse. It exercises every stage of the
real-time track against a synthetic source whose true coherence ramps up over
time, so you can watch INS (and therefore feedback level) rise.

    python -m mindx_hnf.scripts.simulate
"""

from __future__ import annotations

import argparse
import logging

import numpy as np

from mindx_hnf.api.sink import FeedbackSink, NullSink
from mindx_hnf.contracts import FeedbackMode
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper, ShamProvider
from mindx_hnf.ins.coherence import WaveletCoherenceINS
from mindx_hnf.io.sources import SyntheticSource
from mindx_hnf.orchestrator import Orchestrator
from mindx_hnf.preprocessing.online import OnlineHemoPipeline
from mindx_hnf.session.protocol import Block, SessionPlan, SessionScheduler
from mindx_hnf.contracts import BlockType


def build_demo(
    mode: FeedbackMode = FeedbackMode.REAL,
    fast: bool = True,
    sink: FeedbackSink | None = None,
):
    fs = 7.81
    subjects = ("sub-01", "sub-02")
    n_channels = 20

    # Ground-truth coherence ramps 0.1 -> 0.9 so feedback should climb.
    def coherence_fn(t: float) -> float:
        return float(np.clip(0.1 + 0.02 * t, 0.1, 0.9))

    # Short blocks for a quick demo; real durations live in configs/.
    scale = 1.0 if not fast else 0.05
    plan = SessionPlan(
        label="demo",
        mode=mode,
        blocks=[
            Block(BlockType.BASELINE, 60 * scale),
            Block(BlockType.TASK, 120 * scale, feedback=True),
            Block(BlockType.REST, 10 * scale),
            Block(BlockType.TASK, 120 * scale, feedback=True),
        ],
    )
    duration = plan.total_seconds + 2

    source = SyntheticSource(
        n_channels=n_channels,
        fs=fs,
        subjects=subjects,
        coherence_fn=coherence_fn,
        duration_s=duration,
    )
    pre = OnlineHemoPipeline(subjects, n_channels, fs)
    ins = WaveletCoherenceINS(subjects, fs, window_s=20.0 * scale + 2, update_every_s=1.0)
    sham = ShamProvider([0.3, 0.32, 0.35, 0.31, 0.34] * 50)
    mapper = BaselineSmoothingMapper(sham=sham, smoothing=0.3, gain=2.0)
    if sink is None:
        sink = NullSink()
    scheduler = SessionScheduler(plan)

    orch = Orchestrator(
        source=source,
        preprocessor=pre,
        ins=ins,
        mapper=mapper,
        sink=sink,
        scheduler=scheduler,
    )
    return orch, sink


def main() -> None:
    parser = argparse.ArgumentParser(description="mindX Hyper-NF loop simulator")
    parser.add_argument("--sham", action="store_true", help="run in sham mode")
    parser.add_argument("--full", action="store_true", help="use full-length blocks")
    parser.add_argument(
        "--lsl",
        action="store_true",
        help="publish feedback over LSL (stream 'mindx_feedback') for Unity to "
        "subscribe to, instead of discarding it. Requires the [hardware] extra.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    mode = FeedbackMode.SHAM if args.sham else FeedbackMode.REAL
    sink: FeedbackSink | None = None
    if args.lsl:
        from mindx_hnf.api.sink import LSLOutletSink

        sink = LSLOutletSink(subjects=("sub-01", "sub-02"))
        print("Publishing feedback on LSL stream 'mindx_feedback' — "
              "connect Unity (LslFeedbackTransport) now.")
    orch, sink = build_demo(mode=mode, fast=not args.full, sink=sink)
    stats = orch.run()

    levels = [s.level for s in getattr(sink, "published", [])]
    print(f"\nmode={mode.value}")
    print(f"frames={stats.n_frames} ins={stats.n_ins} feedback={stats.n_feedback}")
    print(f"loop latency: mean={stats.mean_loop_latency_ms:.2f}ms "
          f"max={stats.max_loop_latency_ms:.2f}ms")
    if levels:
        print(f"feedback level: first={levels[0]:.3f} last={levels[-1]:.3f} "
              f"min={min(levels):.3f} max={max(levels):.3f}")


if __name__ == "__main__":
    main()

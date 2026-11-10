"""Run the entire closed loop on synthetic data — no hardware required.

This is the development and CI workhorse. It exercises every stage of the
real-time track against a synthetic source whose true coherence ramps up over
time, so you can watch INS (and therefore feedback level) rise.

    python -m mindx_hnf.scripts.simulate
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from pathlib import Path

from mindx_hnf.api.sink import FeedbackSink, NullSink, RecordingSink
from mindx_hnf.contracts import BlockType, FeedbackMode
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper, ShamProvider
from mindx_hnf.ins.coherence import WaveletCoherenceINS
from mindx_hnf.io.sources import SyntheticSource
from mindx_hnf.orchestrator import Orchestrator
from mindx_hnf.preprocessing.montage import load_montage
from mindx_hnf.preprocessing.online import OnlineHemoPipeline
from mindx_hnf.session.protocol import Block, SessionPlan, SessionScheduler

#: Ground-truth coherence while the dyad is not synchronising (baseline, rest).
COHERENCE_LOW = 0.1
#: Ground-truth coherence once a task block's ramp has finished.
COHERENCE_HIGH = 0.9
#: Fraction of a feedback block over which the coherence ramps up.
RAMP_FRACTION = 0.6
#: Demo mapper gain. Measured through the full pipeline with a 22 s window, the
#: INS rises only from about 0.08 (coherence 0.1) to 0.17 (coherence 0.9), so a
#: gain near 1 / 0.09 spreads that span over the game's [0, 1] range. The default
#: of 2.0 capped the level near 0.17. Real data needs its own calibration.
DEMO_GAIN = 10.0


def coherence_profile(plan: SessionPlan) -> Callable[[float], float]:
    """Build the synthetic ground-truth coherence over the session timeline.

    Coherence stays low during the baseline and rest blocks, so the mapper
    measures a genuine resting baseline, and ramps linearly from
    ``COHERENCE_LOW`` to ``COHERENCE_HIGH`` over the first ``RAMP_FRACTION`` of
    each feedback block, then holds.

    Args:
        plan: The session plan whose block timing defines the ramps.

    Returns:
        A function mapping session time in seconds to coherence in [0, 1].
    """
    starts: list[tuple[float, Block]] = []
    t = 0.0
    for block in plan.blocks:
        starts.append((t, block))
        t += block.duration_s

    def coherence_fn(t_s: float) -> float:
        for start, block in starts:
            if start <= t_s < start + block.duration_s:
                if not block.feedback:
                    return COHERENCE_LOW
                ramp_s = max(block.duration_s * RAMP_FRACTION, 1e-9)
                frac = min(1.0, (t_s - start) / ramp_s)
                return COHERENCE_LOW + frac * (COHERENCE_HIGH - COHERENCE_LOW)
        return COHERENCE_LOW

    return coherence_fn


def build_demo(
    mode: FeedbackMode = FeedbackMode.REAL,
    fast: bool = True,
    sink: FeedbackSink | None = None,
    montage: str | Path | None = None,
):
    """Assemble the synthetic closed loop.

    The ground-truth coherence is low in the baseline and ramps up during each
    task block (``coherence_profile``), so feedback should climb after the
    baseline.

    Args:
        mode: Real or sham feedback for the session.
        fast: Scale block durations to 5% for a quick run.
        sink: Feedback transport; a ``NullSink`` is used if None.
        montage: Path to a montage YAML. With it, the source emits
            wavelength-paired intensities with systemic physiology and the
            pipeline runs the full MNE path (OD -> TDDR -> short-channel
            regression -> MNE MBLL, D10).

    Returns:
        The ready-to-run orchestrator and the sink it publishes to.
    """
    fs = 7.81
    subjects = ("sub-01", "sub-02")
    n_channels = 20

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

    mont = load_montage(montage) if montage is not None else None
    source = SyntheticSource(
        n_channels=n_channels,
        fs=fs,
        subjects=subjects,
        coherence_fn=coherence_profile(plan),
        duration_s=duration,
        montage=mont,
    )
    pre = OnlineHemoPipeline(subjects, n_channels, fs, montage=mont)
    ins = WaveletCoherenceINS(
        subjects, fs, window_s=20.0 * scale + 2, update_every_s=1.0
    )
    sham = ShamProvider([0.3, 0.32, 0.35, 0.31, 0.34] * 50)
    mapper = BaselineSmoothingMapper(sham=sham, smoothing=0.3, gain=DEMO_GAIN)
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
    """Parse CLI flags, run the synthetic loop, and print a summary."""
    parser = argparse.ArgumentParser(description="mindX Hyper-NF loop simulator")
    parser.add_argument("--sham", action="store_true", help="run in sham mode")
    parser.add_argument("--full", action="store_true", help="use full-length blocks")
    parser.add_argument(
        "--lsl",
        action="store_true",
        help="publish feedback over LSL (stream 'mindx_feedback') for Unity to "
        "subscribe to, instead of discarding it. Requires the [hardware] extra.",
    )
    parser.add_argument(
        "--montage",
        type=Path,
        default=None,
        help="optode montage YAML (e.g. configs/montage_demo.yaml): run the full "
        "MNE preprocessing path on wavelength-paired synthetic data (D10).",
    )
    parser.add_argument(
        "--log-csv",
        type=Path,
        default=None,
        help="write every feedback sample (t_lsl, level, raw_ins, ...) to this CSV "
        "when the run ends; works with or without --lsl.",
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
        print(
            "Publishing feedback on LSL stream 'mindx_feedback' — "
            "connect Unity (LslFeedbackTransport) now."
        )
    if args.log_csv is not None:
        sink = RecordingSink(sink, args.log_csv)
    orch, sink = build_demo(
        mode=mode, fast=not args.full, sink=sink, montage=args.montage
    )
    stats = orch.run()
    if args.log_csv is not None:
        print(f"feedback samples written to {args.log_csv}")

    levels = [s.level for s in getattr(sink, "published", [])]
    print(f"\nmode={mode.value}")
    print(f"frames={stats.n_frames} ins={stats.n_ins} feedback={stats.n_feedback}")
    print(
        f"loop latency: mean={stats.mean_loop_latency_ms:.2f}ms "
        f"max={stats.max_loop_latency_ms:.2f}ms"
    )
    if levels:
        print(
            f"feedback level: first={levels[0]:.3f} last={levels[-1]:.3f} "
            f"min={min(levels):.3f} max={max(levels):.3f}"
        )


if __name__ == "__main__":
    main()

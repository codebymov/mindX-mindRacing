"""Run the entire closed loop on synthetic data — no hardware required.

This is the development and CI workhorse. It exercises every stage of the
real-time track against a synthetic source whose true coherence ramps up over
time, so you can watch INS (and therefore feedback level) rise.

    python -m mindx_hnf.scripts.simulate
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
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
from mindx_hnf.session.mode_switch import FeedbackModeSwitch
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
#: Demo gain on the MNE montage path (``--montage``). There the INS runs higher and
#: spans about 0.15 (baseline) to 0.22-0.25 (task plateaus), so a smaller gain gives
#: the same [0, 1] level range. Measured offline, 22 s window; real data needs its own.
MONTAGE_GAIN = 8.0


def coherence_profile(
    plan: SessionPlan,
    *,
    delay_s: float = 0.0,
    ramp_fraction: float = RAMP_FRACTION,
) -> Callable[[float], float]:
    """Build the synthetic ground-truth coherence over the session timeline.

    Coherence stays low during the baseline and rest blocks, so the mapper
    measures a genuine resting baseline, and ramps linearly from
    ``COHERENCE_LOW`` to ``COHERENCE_HIGH`` over the first ``ramp_fraction`` of
    each feedback block, then holds.

    Args:
        plan: The session plan whose block timing defines the ramps.
        delay_s: Shifts the whole profile later, giving a dyad that synchronises
            later than the plan's schedule (used for the sham dyad).
        ramp_fraction: Fraction of a feedback block over which coherence ramps.

    Returns:
        A function mapping session time in seconds to coherence in [0, 1].
    """
    starts: list[tuple[float, Block]] = []
    t = 0.0
    for block in plan.blocks:
        starts.append((t, block))
        t += block.duration_s

    def coherence_fn(t_s: float) -> float:
        t_s -= delay_s
        for start, block in starts:
            if start <= t_s < start + block.duration_s:
                if not block.feedback:
                    return COHERENCE_LOW
                ramp_s = max(block.duration_s * ramp_fraction, 1e-9)
                frac = min(1.0, (t_s - start) / ramp_s)
                return COHERENCE_LOW + frac * (COHERENCE_HIGH - COHERENCE_LOW)
        return COHERENCE_LOW

    return coherence_fn


#: RNG seed of the sham dyad (a different dyad from the live one, seed 0).
SHAM_SEED = 7


def build_sham_trace(
    plan: SessionPlan,
    *,
    fs: float,
    subjects: tuple[str, str],
    n_channels: int,
    window_s: float,
    montage=None,
    seed: int = SHAM_SEED,
) -> list[float]:
    """Record another synthetic dyad's INS trace for the same session plan.

    Sham feedback replays a real trajectory from a different dyad doing the same
    task. The other dyad runs through the identical pipeline and estimator (so the
    values are on the same INS scale) but has its own noise (a different seed) and
    synchronises later and more slowly than the live dyad, so its course is
    independent of the live dyad's.

    Args:
        plan: The session plan; only feedback-block INS values are returned.
        fs: Sampling rate in Hz.
        subjects: The two subjects of the sham dyad.
        n_channels: Raw channels per subject.
        window_s: INS window length in seconds (same as the live estimator).
        montage: Optional montage, so the trace uses the same preprocessing path.
        seed: RNG seed of the sham dyad.

    Returns:
        The INS values emitted during feedback blocks, in delivery order.
    """
    feedback_blocks = [b for b in plan.blocks if b.feedback]
    delay_s = 0.25 * max(b.duration_s for b in feedback_blocks)
    source = SyntheticSource(
        n_channels=n_channels,
        fs=fs,
        subjects=subjects,
        coherence_fn=coherence_profile(plan, delay_s=delay_s, ramp_fraction=0.8),
        seed=seed,
        duration_s=plan.total_seconds + 2,
        montage=montage,
        realtime=False,
    )
    pre = OnlineHemoPipeline(subjects, n_channels, fs, montage=montage)
    ins = WaveletCoherenceINS(subjects, fs, window_s=window_s, update_every_s=1.0)
    scheduler = SessionScheduler(plan)

    trace: list[float] = []
    t_first: float | None = None
    locked = False
    for frame in source.frames():
        if t_first is None:
            t_first = frame.t_lsl
        block = scheduler.current_block(frame.t_lsl - t_first)
        if not locked and (block is None or block.kind is not BlockType.BASELINE):
            pre.lock_baseline()
            locked = True
        sample = ins.update(pre.process(frame))
        if sample is not None and block is not None and block.feedback:
            trace.append(sample.value)
    return trace


def build_demo(
    mode: FeedbackMode = FeedbackMode.REAL,
    fast: bool = True,
    sink: FeedbackSink | None = None,
    montage: str | Path | None = None,
    mode_switch: FeedbackModeSwitch | None = None,
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
        mode_switch: Optional operator switch to flip between real and sham
            while the loop runs.

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
    window_s = 20.0 * scale + 2
    ins = WaveletCoherenceINS(subjects, fs, window_s=window_s, update_every_s=1.0)
    sham = ShamProvider(
        build_sham_trace(
            plan,
            fs=fs,
            subjects=subjects,
            n_channels=n_channels,
            window_s=window_s,
            montage=mont,
        )
    )
    gain = MONTAGE_GAIN if mont is not None else DEMO_GAIN
    mapper = BaselineSmoothingMapper(sham=sham, smoothing=0.3, gain=gain)
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
        mode_switch=mode_switch,
    )
    return orch, sink


def _operator_console(switch: FeedbackModeSwitch) -> None:
    """Flip real/sham each time the operator presses Enter (or types ``s``).

    This is an operator tool on the backend terminal. Nothing participant-facing
    shows or reads it.

    Args:
        switch: The switch the running orchestrator reads every frame.
    """
    for line in sys.stdin:
        command = line.strip().lower()
        if command in ("", "s"):
            new = switch.toggle("console")
            print(f"[operator] feedback source -> {new.value.upper()}", flush=True)
        elif command == "q":
            break


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
    parser.add_argument(
        "--toggle",
        action="store_true",
        help="operator console: press Enter (or type s) in this terminal to switch "
        "feedback between REAL and SHAM while the session runs.",
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
    switch = FeedbackModeSwitch(mode)
    orch, sink = build_demo(
        mode=mode,
        fast=not args.full,
        sink=sink,
        montage=args.montage,
        mode_switch=switch,
    )
    if args.toggle:
        threading.Thread(target=_operator_console, args=(switch,), daemon=True).start()
        print(
            "Operator console: press Enter (or type s) to switch REAL <-> SHAM. "
            f"Starting in {mode.value.upper()}.",
            flush=True,
        )
    stats = orch.run()
    for who, new_mode in switch.history:
        print(f"[operator] switched to {new_mode.value} ({who})")
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

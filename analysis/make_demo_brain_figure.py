"""Render the demo's "brain" figure from SYNTHETIC data.

Runs the project's own pipeline offline (faster than real time) on generated
fNIRS data and draws three panels: the optode montage (PFC + right TPJ), the
preprocessed haemoglobin signal of both players, and the joint synchrony (INS) with
the feedback level. Nothing here is recorded from people; the figure says so.

Usage (from the repository root, with the backend venv)::

    python analysis/make_demo_brain_figure.py [output.png]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle  # noqa: E402

from mindx_hnf.contracts import BlockType, FeedbackMode  # noqa: E402
from mindx_hnf.feedback.mapper import BaselineSmoothingMapper  # noqa: E402
from mindx_hnf.ins.coherence import WaveletCoherenceINS  # noqa: E402
from mindx_hnf.io.sources import SyntheticSource  # noqa: E402
from mindx_hnf.preprocessing.montage import load_montage  # noqa: E402
from mindx_hnf.preprocessing.online import OnlineHemoPipeline  # noqa: E402
from mindx_hnf.scripts.simulate import MONTAGE_GAIN, coherence_profile  # noqa: E402
from mindx_hnf.session.protocol import Block, SessionPlan, SessionScheduler  # noqa: E402

FS = 7.81
SUBJECTS = ("sub-01", "sub-02")
HEAD_RADIUS = 0.095  # metres, the sphere MNE uses for 2-D head plots


def run_session() -> dict[str, np.ndarray]:
    """Run the synthetic closed loop offline and collect what the figure plots.

    Returns:
        Arrays: frame times, channel-mean HbO per player, INS times and values,
        feedback times and levels, and the block boundaries.
    """
    montage = load_montage(ROOT / "backend" / "configs" / "montage_demo.yaml")
    plan = SessionPlan(
        label="figure",
        mode=FeedbackMode.REAL,
        blocks=[
            Block(BlockType.BASELINE, 60.0),
            Block(BlockType.TASK, 120.0, feedback=True),
            Block(BlockType.REST, 10.0),
            Block(BlockType.TASK, 120.0, feedback=True),
        ],
    )
    source = SyntheticSource(
        fs=FS,
        subjects=SUBJECTS,
        coherence_fn=coherence_profile(plan),
        duration_s=plan.total_seconds + 2,
        montage=montage,
        realtime=False,
    )
    pre = OnlineHemoPipeline(SUBJECTS, montage.n_raw_channels, FS, montage=montage)
    ins = WaveletCoherenceINS(SUBJECTS, FS, window_s=22.0, update_every_s=1.0)
    mapper = BaselineSmoothingMapper(smoothing=0.3, gain=MONTAGE_GAIN)
    scheduler = SessionScheduler(plan)

    t_frames: list[float] = []
    hbo: dict[str, list[float]] = {s: [] for s in SUBJECTS}
    t_ins: list[float] = []
    v_ins: list[float] = []
    t_fb: list[float] = []
    level: list[float] = []
    t0: float | None = None
    locked = False
    for frame in source.frames():
        if t0 is None:
            t0 = frame.t_lsl
        elapsed = frame.t_lsl - t0
        block = scheduler.current_block(elapsed)
        if not locked and (block is None or block.kind is not BlockType.BASELINE):
            pre.lock_baseline()
            locked = True
        hemo = pre.process(frame)
        t_frames.append(elapsed)
        for s in SUBJECTS:
            hbo[s].append(float(np.mean(hemo.hbo[s])))
        sample = ins.update(hemo)
        if sample is None:
            continue
        t_ins.append(elapsed)
        v_ins.append(sample.value)
        if block is not None and block.kind is BlockType.BASELINE:
            mapper.observe_baseline(sample)
        elif block is not None and block.feedback:
            if not mapper._baseline_locked:  # noqa: SLF001 - mirrors the orchestrator
                mapper.lock_baseline()
            t_fb.append(elapsed)
            level.append(mapper.map(sample, FeedbackMode.REAL).level)

    return {
        "t": np.array(t_frames),
        "hbo_a": np.array(hbo[SUBJECTS[0]]),
        "hbo_b": np.array(hbo[SUBJECTS[1]]),
        "t_ins": np.array(t_ins),
        "ins": np.array(v_ins),
        "t_fb": np.array(t_fb),
        "level": np.array(level),
        "bounds": np.cumsum([0.0] + [b.duration_s for b in plan.blocks]),
        "montage": montage,  # type: ignore[dict-item]
    }


def draw_montage(ax, montage) -> None:
    """Draw the optode layout seen from above, nose up, with MNE's head sphere.

    Args:
        ax: Matplotlib axes to draw on.
        montage: The project montage (positions in metres, head frame).
    """
    ax.add_patch(Circle((0, 0), HEAD_RADIUS, fill=False, lw=2, color="#444"))
    ax.plot([-0.012, 0, 0.012], [HEAD_RADIUS, HEAD_RADIUS + 0.014, HEAD_RADIUS], color="#444", lw=2)
    for sx in (-1, 1):
        ax.plot([sx * HEAD_RADIUS, sx * (HEAD_RADIUS + 0.008)], [0.012, 0.012], color="#444", lw=2)
        ax.plot([sx * (HEAD_RADIUS + 0.008)] * 2, [0.012, -0.012], color="#444", lw=2)
    for ch in montage.channels:
        s, d = np.array(ch.source), np.array(ch.detector)
        color = "#999" if ch.short else ("#1f77b4" if ch.region == "pfc" else "#d62728")
        ax.plot([s[0], d[0]], [s[1], d[1]], color=color, lw=3 if not ch.short else 1.5, ls="-" if not ch.short else "--")
        ax.scatter(*s[:2], marker="o", s=70, color="#111", zorder=3)
        ax.scatter(*d[:2], marker="s", s=70, color="#ffb000", edgecolor="#111", zorder=3)
    ax.text(0.005, 0.058, "PFC", ha="center", va="center", color="#1f77b4", fontsize=13, weight="bold")
    ax.text(0.052, -0.002, "right TPJ", ha="right", va="center", color="#d62728", fontsize=13, weight="bold")
    ax.scatter([], [], marker="o", color="#111", label="source")
    ax.scatter([], [], marker="s", color="#ffb000", edgecolor="#111", label="detector")
    ax.plot([], [], color="#999", ls="--", label="short channel")
    ax.legend(loc="lower left", fontsize=9, frameon=False)
    ax.set_xlim(-0.125, 0.14)
    ax.set_ylim(-0.12, 0.125)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("fNIRS montage (top view)", fontsize=12)


def shade_blocks(ax, bounds: np.ndarray) -> None:
    """Shade the baseline/task/rest blocks behind a time-series panel.

    Args:
        ax: Matplotlib axes.
        bounds: Block boundaries in seconds, starting at 0.
    """
    colors = ["#e8e8e8", "#fff3cd", "#e8e8e8", "#fff3cd"]
    labels = ["baseline", "task", "rest", "task"]
    for i in range(len(bounds) - 1):
        ax.axvspan(bounds[i], bounds[i + 1], color=colors[i], zorder=0)
        top = ax.get_ylim()[1]
        ax.text((bounds[i] + bounds[i + 1]) / 2, top * 0.97, labels[i], ha="center", va="top", fontsize=10, color="#555")


def main() -> None:
    """Build the figure and write it to the path given on the command line."""
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "demo" / "brain_synthetic.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = run_session()

    fig = plt.figure(figsize=(16, 6.2), dpi=130)
    grid = fig.add_gridspec(2, 2, width_ratios=[0.8, 2.2], height_ratios=[1, 1], hspace=0.42, wspace=0.12)
    ax_m = fig.add_subplot(grid[:, 0])
    ax_h = fig.add_subplot(grid[0, 1])
    ax_i = fig.add_subplot(grid[1, 1], sharex=ax_h)
    draw_montage(ax_m, data["montage"])

    for key, color, label in (("hbo_a", "#1f77b4", "Player 1"), ("hbo_b", "#ff7f0e", "Player 2")):
        y = data[key]
        ax_h.plot(data["t"], (y - y.mean()) / (y.std() + 1e-12), color=color, lw=1.2, label=label)
    ax_h.set_ylim(-3.2, 3.2)
    shade_blocks(ax_h, data["bounds"])
    ax_h.set_ylabel("ΔHbO (z-scored)")
    ax_h.legend(loc="lower left", ncol=2, fontsize=9, frameon=False)
    ax_h.set_title("Preprocessed haemoglobin signal of both players (causal MNE-NIRS pipeline)", fontsize=12)
    plt.setp(ax_h.get_xticklabels(), visible=False)

    ax_i.plot(data["t_ins"], data["ins"], color="#888", lw=1.2, label="joint INS (coherence 0.01–0.1 Hz)")
    ax_i.set_ylabel("INS", color="#555")
    ax_l = ax_i.twinx()
    ax_l.plot(data["t_fb"], data["level"], color="#2ca02c", lw=2.6, label="feedback level (drives car speed)")
    ax_l.set_ylim(0, 1)
    ax_l.set_ylabel("level 0–1", color="#2ca02c")
    ax_i.set_ylim(0, max(0.25, float(data["ins"].max()) * 1.15))
    shade_blocks(ax_i, data["bounds"])
    ax_i.set_xlabel("session time (s)")
    ax_i.set_title("Interpersonal synchrony → feedback", fontsize=12)
    lines = ax_i.get_lines() + ax_l.get_lines()
    ax_i.legend(
        lines,
        [ln.get_label() for ln in lines],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.30),
        ncol=2,
        fontsize=10,
        frameon=False,
    )
    ax_i.set_xlim(0, data["bounds"][-1])

    fig.suptitle(
        "SYNTHETIC DATA — generated by the project's simulator, not recorded from people",
        color="#b00020",
        fontsize=15,
        weight="bold",
        y=0.995,
    )
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

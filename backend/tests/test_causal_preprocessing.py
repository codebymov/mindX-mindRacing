"""Causal preprocessing stages vs their MNE / MNE-NIRS batch oracles (D10 Phase 2).

Each online stage keeps MNE's algorithm and replaces only the non-causal part.
These tests pin both halves of that claim:

  - **oracle**: where the causal estimate has seen the same data MNE sees, it
    reproduces MNE exactly (OD reference, short-channel alpha); where it cannot
    (TDDR's windowed statistics vs. global ones), it repairs artifacts nearly as
    well as MNE's batch TDDR on the same data;
  - **causality**: perturbing future samples never changes past outputs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mne")

import mne  # noqa: E402
from scipy.signal import detrend  # noqa: E402

from mindx_hnf.preprocessing.causal import (  # noqa: E402
    CausalODReference,
    CausalShortChannelRegression,
    CausalTDDR,
    short_channel_partners,
)
from mindx_hnf.preprocessing.montage import build_od_info, load_montage  # noqa: E402

_MONTAGE = Path(__file__).resolve().parents[1] / "configs" / "montage_demo.yaml"
FS = 7.81
CHUNK = 8


def _stream(stage, x: np.ndarray, chunk: int = CHUNK) -> np.ndarray:
    return np.hstack([stage(x[:, i : i + chunk]) for i in range(0, x.shape[1], chunk)])


def _raw(montage, data: np.ndarray, ch_type: str, rows=None) -> mne.io.RawArray:
    """RawArray with the montage's channel geometry (optionally a row subset)."""
    od_info = build_od_info(montage)
    rows = list(range(len(od_info["ch_names"]))) if rows is None else list(rows)
    info = mne.create_info([od_info["ch_names"][r] for r in rows], FS, ch_type)
    for ch, r in zip(info["chs"], rows, strict=True):
        ch["loc"] = od_info["chs"][r]["loc"]
    return mne.io.RawArray(data.copy(), info, verbose="ERROR")


# --------------------------------------------------------------------------- #
# Optical density
# --------------------------------------------------------------------------- #
def test_od_reference_frozen_at_baseline_matches_mne():
    # After the baseline block is locked, OD is relative to the baseline mean —
    # exactly MNE's optical_density applied to the baseline segment.
    montage = load_montage(_MONTAGE)
    rng = np.random.default_rng(0)
    n = montage.n_raw_channels
    baseline = 1.0 + 0.05 * rng.random((n, 160))
    task = 1.3 + 0.05 * rng.random((n, 80))  # DC shift: must NOT move the ref

    od = CausalODReference(n)
    _stream(od, baseline)
    od.lock()
    ref_before = od.reference.copy()
    _stream(od, task)
    np.testing.assert_array_equal(od.reference, ref_before)

    ours = od(baseline)
    oracle = mne.preprocessing.nirs.optical_density(
        _raw(montage, baseline, "fnirs_cw_amplitude"), verbose="ERROR"
    ).get_data()
    assert np.max(np.abs(ours - oracle)) < 1e-12


def test_od_lock_before_any_data_uses_first_chunk():
    od = CausalODReference(3)
    od.lock()
    first = np.full((3, CHUNK), 2.0)
    assert np.allclose(od(first), 0.0)
    assert np.allclose(od(np.full((3, CHUNK), 4.0)), -np.log(2.0))


# --------------------------------------------------------------------------- #
# TDDR
# --------------------------------------------------------------------------- #
def _hemo_like(rng, n_ch: int, n: int) -> np.ndarray:
    t = np.arange(n) / FS
    return np.vstack(
        [
            0.02 * np.sin(2 * np.pi * 0.05 * t + k)
            + 0.01 * np.sin(2 * np.pi * 0.09 * t)
            + 0.003 * rng.standard_normal(n)
            for k in range(n_ch)
        ]
    )


def _with_motion(rng, clean: np.ndarray) -> np.ndarray:
    x = clean.copy()
    n = x.shape[1]
    for ch in range(x.shape[0]):
        for at in rng.choice(np.arange(200, n - 50), 4, replace=False):
            x[ch, at:] += rng.choice([-1, 1]) * 0.08  # baseline shift
        for at in rng.choice(np.arange(200, n - 50), 3, replace=False):
            x[ch, at : at + 5] += 0.15  # spike
    return x


def _err(y: np.ndarray, clean: np.ndarray) -> float:
    return float(np.sqrt(np.mean(detrend(y - clean, axis=1) ** 2)))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_tddr_repairs_motion_nearly_as_well_as_mne(seed):
    from mne.preprocessing.nirs import temporal_derivative_distribution_repair

    montage = load_montage(_MONTAGE)
    rng = np.random.default_rng(seed)
    n_ch = montage.n_raw_channels
    clean = _hemo_like(rng, n_ch, int(300 * FS))
    corrupted = _with_motion(rng, clean)

    ours = _stream(CausalTDDR(n_ch, FS), corrupted)
    oracle = temporal_derivative_distribution_repair(
        _raw(montage, corrupted, "fnirs_od"), verbose="ERROR"
    ).get_data()

    e_raw, e_ours, e_mne = (_err(y, clean) for y in (corrupted, ours, oracle))
    assert e_mne < e_raw  # sanity: the oracle itself repairs the artifacts
    assert (
        e_ours < 0.6 * e_raw
    ), f"causal TDDR barely helps: {e_ours:.4f} vs {e_raw:.4f}"
    assert (
        e_ours < 1.6 * e_mne
    ), f"causal TDDR far worse than MNE: {e_ours:.4f} vs {e_mne:.4f}"


def test_tddr_is_identity_during_warmup():
    rng = np.random.default_rng(3)
    x = _hemo_like(rng, 4, int(5 * FS))  # shorter than min_window_s
    assert np.allclose(_stream(CausalTDDR(4, FS), x), x, atol=1e-12)


def test_tddr_is_causal():
    rng = np.random.default_rng(4)
    x = _with_motion(rng, _hemo_like(rng, 4, int(120 * FS)))
    cut = 64 * CHUNK
    y = x.copy()
    y[:, cut:] += 5.0 * rng.standard_normal((4, x.shape[1] - cut))  # rewrite the future
    a = _stream(CausalTDDR(4, FS), x)
    b = _stream(CausalTDDR(4, FS), y)
    np.testing.assert_array_equal(a[:, :cut], b[:, :cut])


# --------------------------------------------------------------------------- #
# Short-channel regression
# --------------------------------------------------------------------------- #
def test_short_partners_pair_by_wavelength():
    montage = load_montage(_MONTAGE)
    partners = short_channel_partners(montage)
    # Demo montage: pairs 0-3 long, pair 4 short -> raw rows 8 (760), 9 (850).
    np.testing.assert_array_equal(partners, [8, 9, 8, 9, 8, 9, 8, 9, -1, -1])


def test_short_flag_inconsistent_with_geometry_raises():
    from dataclasses import replace

    montage = load_montage(_MONTAGE)
    chans = list(montage.channels)
    chans[0] = replace(chans[0], short=True)  # a 3 cm channel flagged short
    with pytest.raises(ValueError, match="flagged short"):
        short_channel_partners(replace(montage, channels=tuple(chans)))


def _systemic_od(rng, montage, n: int) -> np.ndarray:
    """Zero-mean OD where every long row carries its wavelength's short signal."""
    x = 0.1 * rng.standard_normal((montage.n_raw_channels, n))
    x[8], x[9] = rng.standard_normal(n), rng.standard_normal(n)
    for row in range(8):
        x[row] += 0.7 * x[8 + row % 2]
    return x - x.mean(axis=1, keepdims=True)


def test_scr_matches_mne_nirs_once_all_data_seen():
    # With no forgetting, alpha after the last sample is MNE-NIRS's whole-
    # recording alpha, so the final output sample is identical. 760 nm rows are
    # checked against MNE-NIRS directly; 850 nm rows against MNE-NIRS run on the
    # 850 nm channels alone (MNE-NIRS 0.7.3 regresses BOTH wavelengths on the
    # 760 nm short channel — see short_channel_partners).
    from mne_nirs.signal_enhancement import short_channel_regression

    montage = load_montage(_MONTAGE)
    rng = np.random.default_rng(5)
    x = _systemic_od(rng, montage, 400)

    scr = CausalShortChannelRegression(short_channel_partners(montage), FS, tau_s=None)
    ours = _stream(scr, x)

    rows760 = np.arange(0, montage.n_raw_channels, 2)
    rows850 = rows760 + 1
    mne_all = short_channel_regression(_raw(montage, x, "fnirs_od")).get_data()
    mne_850 = short_channel_regression(
        _raw(montage, x[rows850], "fnirs_od", rows=rows850)
    ).get_data()

    np.testing.assert_allclose(ours[rows760, -1], mne_all[rows760, -1], atol=1e-10)
    np.testing.assert_allclose(ours[rows850, -1], mne_850[:, -1], atol=1e-10)
    # Short rows are regressors and pass through unchanged.
    np.testing.assert_array_equal(ours[8:], x[8:])


def test_scr_removes_systemic_and_ignores_dc_offset():
    montage = load_montage(_MONTAGE)
    rng = np.random.default_rng(6)
    x = _systemic_od(rng, montage, int(300 * FS))
    x[:8] += 0.5  # OD offset (causal reference != whole-recording mean)
    out = _stream(CausalShortChannelRegression(short_channel_partners(montage), FS), x)
    late = slice(int(60 * FS), None)
    for row in range(8):
        short = x[8 + row % 2, late]
        before = abs(np.corrcoef(x[row, late], short)[0, 1])
        after = abs(np.corrcoef(out[row, late], short)[0, 1])
        assert before > 0.9 and after < 0.1, (row, before, after)


def test_scr_is_causal():
    montage = load_montage(_MONTAGE)
    rng = np.random.default_rng(7)
    x = _systemic_od(rng, montage, 400)
    y = x.copy()
    y[:, 200:] = 10 * rng.standard_normal((x.shape[0], 200))
    partners = short_channel_partners(montage)
    a = _stream(CausalShortChannelRegression(partners, FS), x)
    b = _stream(CausalShortChannelRegression(partners, FS), y)
    np.testing.assert_array_equal(a[:, :200], b[:, :200])


# --------------------------------------------------------------------------- #
# Full pipeline + orchestrator wiring
# --------------------------------------------------------------------------- #
def test_orchestrator_locks_od_reference_after_baseline():
    from mindx_hnf.contracts import FeedbackMode

    from mindx_hnf.scripts.simulate import build_demo

    orch, sink = build_demo(mode=FeedbackMode.REAL, fast=True, montage=_MONTAGE)
    stats = orch.run()
    assert orch.preprocessor.baseline_locked
    assert stats.n_feedback > 0
    assert all(np.isfinite(s.level) for s in sink.published)
    assert stats.max_loop_latency_ms < 50.0


def _ins_tracking(monkeypatch, seed: int, **pipeline_kw) -> float:
    """corr(INS, ground-truth coherence) on the montage path, run faster than real time."""
    import mindx_hnf.io.sources as sources
    from mindx_hnf.ins.coherence import WaveletCoherenceINS
    from mindx_hnf.preprocessing.online import OnlineHemoPipeline

    clock = [0.0]

    def fake_clock() -> float:
        clock[0] += CHUNK / FS
        return clock[0]

    monkeypatch.setattr(sources.time, "sleep", lambda _s: None)
    monkeypatch.setattr(sources, "lsl_clock", fake_clock)

    montage = load_montage(_MONTAGE)
    subjects = ("sub-01", "sub-02")

    def truth(t: float) -> float:
        return 0.5 + 0.4 * np.sin(2 * np.pi * t / 240)

    src = sources.SyntheticSource(
        subjects=subjects,
        montage=montage,
        duration_s=480,
        coherence_fn=truth,
        seed=seed,
    )
    pipe = OnlineHemoPipeline(
        subjects, montage.n_raw_channels, FS, montage=montage, **pipeline_kw
    )
    ins = WaveletCoherenceINS(subjects, FS, window_s=30, update_every_s=1.0)
    est, ref = [], []
    for i, frame in enumerate(src.frames()):
        if i == int(60 * FS / CHUNK):
            pipe.lock_baseline()
        out = ins.update(pipe.process(frame))
        if out is not None:
            est.append(out.value)
            ref.append(truth(frame.t_lsl - src._t0))  # noqa: SLF001
    return float(np.corrcoef(est[60:], ref[60:])[0, 1])


def test_short_channel_regression_recovers_ins_under_systemic_noise(monkeypatch):
    # Systemic physiology (independent per subject) masks the shared neural
    # component; regressing it out via the short channel must restore INS tracking.
    with_scr = np.mean([_ins_tracking(monkeypatch, s) for s in (0, 1)])
    without = np.mean(
        [_ins_tracking(monkeypatch, s, short_channel_regression=False) for s in (0, 1)]
    )
    assert with_scr > 0.4, with_scr
    assert with_scr > without + 0.2, (with_scr, without)

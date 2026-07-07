"""MBLL operator tests — MNE is the oracle (D10).

These pin the load-bearing claim of D10: the online Beer-Lambert operator IS
MNE's map, so it can run causally per frame without drift from the reference
implementation. Skipped unless the [analysis] extra (mne) is installed, so base
CI stays light; where mne is present these must pass to protect the science.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("mne")

from mne.preprocessing.nirs import beer_lambert_law  # noqa: E402

from mindx_hnf.preprocessing.montage import (  # noqa: E402
    BeerLambertOperator,
    build_od_info,
    load_montage,
)

_MONTAGE = Path(__file__).resolve().parents[1] / "configs" / "montage_demo.yaml"


def _mne_reference(montage, od):
    """Run MNE's own beer_lambert_law on the same OD (in µM) as the oracle."""
    import mne

    info = build_od_info(montage)
    raw = mne.io.RawArray(od.copy(), info, verbose="ERROR")
    hb = beer_lambert_law(raw, ppf=montage.ppf)
    names = hb.info["ch_names"]
    data = hb.get_data() * 1e6  # molar -> micromolar
    hbo = data[[i for i, n in enumerate(names) if "hbo" in n.lower()]]
    hbr = data[[i for i, n in enumerate(names) if "hbr" in n.lower()]]
    return hbo, hbr


def test_operator_matches_mne_beer_lambert():
    montage = load_montage(_MONTAGE)
    op = BeerLambertOperator.from_montage(montage)

    rng = np.random.default_rng(0)
    od = rng.standard_normal((montage.n_raw_channels, 200)) * 0.1

    hbo, hbr = op.apply(od)
    ref_hbo, ref_hbr = _mne_reference(montage, od)

    assert hbo.shape == (montage.n_pairs, 200)
    assert np.max(np.abs(hbo - ref_hbo)) < 1e-9
    assert np.max(np.abs(hbr - ref_hbr)) < 1e-9


def test_operator_is_causal_linear():
    # A fixed linear per-sample map: processing a prefix == prefix of processing
    # the whole. This is what lets MBLL run online with no future samples.
    montage = load_montage(_MONTAGE)
    op = BeerLambertOperator.from_montage(montage)

    rng = np.random.default_rng(1)
    od = rng.standard_normal((montage.n_raw_channels, 100)) * 0.1

    hbo_full, hbr_full = op.apply(od)
    hbo_prefix, hbr_prefix = op.apply(od[:, :40])
    assert np.allclose(hbo_full[:, :40], hbo_prefix, atol=1e-12)
    assert np.allclose(hbr_full[:, :40], hbr_prefix, atol=1e-12)


def test_montage_shapes():
    montage = load_montage(_MONTAGE)
    assert montage.n_pairs == 5
    assert montage.n_raw_channels == 10  # 5 pairs * 2 wavelengths
    assert montage.short_mask.sum() == 1  # one short channel


def test_montage_pipeline_end_to_end():
    # Paired synthetic source -> montage pipeline -> finite HbO/HbR of the right
    # shape. Proves the MNE MBLL path runs end-to-end with no hardware (D10).
    from mindx_hnf.io.sources import SyntheticSource
    from mindx_hnf.preprocessing.online import OnlineHemoPipeline

    montage = load_montage(_MONTAGE)
    subjects = ("sub-01", "sub-02")
    source = SyntheticSource(subjects=subjects, montage=montage, duration_s=2.0)
    pipe = OnlineHemoPipeline(
        subjects, montage.n_raw_channels, source.fs, montage=montage
    )

    frames = 0
    for frame in source.frames():
        assert frame.fnirs["sub-01"].shape[0] == montage.n_raw_channels
        hemo = pipe.process(frame)
        for s in subjects:
            assert hemo.hbo[s].shape[0] == montage.n_pairs
            assert hemo.hbr[s].shape[0] == montage.n_pairs
            assert np.all(np.isfinite(hemo.hbo[s]))
            assert np.all(np.isfinite(hemo.hbr[s]))
        frames += 1
        if frames >= 2:
            break
    assert frames >= 1

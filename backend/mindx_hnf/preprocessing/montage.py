"""Optode montage + Beer-Lambert operator (D10).

This is how MNE-NIRS becomes part of the ONLINE pipeline without breaking the
hot-path or causality rules: MNE builds the modified-Beer-Lambert map ONCE here
(at construction), and the online pipeline applies it per frame as a plain numpy
matmul. The extracted operator is MNE's own map — captured by probing
``mne.preprocessing.nirs.beer_lambert_law`` with optical-density basis vectors —
so it matches MNE to numerical precision by construction (see tests).

Only the source-detector distance and the wavelengths drive MBLL, so this module
depends on MNE + numpy only and never constructs an ``mne.io.Raw`` per frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import yaml

# Concentrations come out of MNE in molar; the HemoFrame contract is micromolar.
_MOLAR_TO_MICROMOLAR = 1e6


@dataclass(frozen=True)
class OptodeChannel:
    """One source-detector pair (a measurement channel) of the montage.

    Attributes:
        source: Source optode position (x, y, z) in metres.
        detector: Detector optode position (x, y, z) in metres.
        short: Whether this is a short (systemic-regressor) channel.
        region: Target region label, e.g. ``"pfc"`` or ``"rtpj"``.
    """

    source: tuple[float, float, float]
    detector: tuple[float, float, float]
    short: bool = False
    region: str = ""

    @property
    def distance_m(self) -> float:
        """Source-detector distance in metres."""
        s = np.asarray(self.source, dtype=float)
        d = np.asarray(self.detector, dtype=float)
        return float(np.linalg.norm(s - d))


@dataclass(frozen=True)
class Montage:
    """A source-detector layout with wavelengths and pathlength factor.

    Attributes:
        name: Montage name.
        channels: Channels in raw-layout order.
        wavelengths: Wavelengths in nm, in the raw per-pair row order.
        ppf: Partial pathlength factor passed to MNE's Beer-Lambert law.
    """

    name: str
    channels: tuple[OptodeChannel, ...]
    wavelengths: tuple[float, ...] = (760.0, 850.0)
    ppf: float = 6.0

    @property
    def n_pairs(self) -> int:
        """Number of source-detector pairs, long and short."""
        return len(self.channels)

    @property
    def n_raw_channels(self) -> int:
        """Raw intensity channels the source must emit (one per wavelength/pair)."""
        return len(self.channels) * len(self.wavelengths)

    @property
    def n_long(self) -> int:
        """Long (brain-signal) channels — what the online pipeline outputs."""
        return sum(1 for c in self.channels if not c.short)

    @property
    def short_mask(self) -> np.ndarray:
        """Boolean mask over pairs marking the short (regressor) channels."""
        return np.array([c.short for c in self.channels], dtype=bool)


def _xyz(seq) -> tuple[float, float, float]:
    """Convert a 3-element sequence to a float tuple.

    Args:
        seq: Three numbers.

    Returns:
        The values as an ``(x, y, z)`` float tuple.

    Raises:
        ValueError: If ``seq`` does not have exactly three elements.
    """
    x, y, z = (float(v) for v in seq)
    return (x, y, z)


def load_montage(path: str | Path) -> Montage:
    """Load a montage from a YAML config (see ``configs/montage_demo.yaml``).

    Args:
        path: Path to the montage YAML.

    Returns:
        The parsed montage; missing ``wavelengths``/``ppf`` take the defaults.

    Raises:
        OSError: If the file cannot be read.
        KeyError: If a required key (``channels``, ``source``, ``detector``)
            is missing.
    """
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    channels = tuple(
        OptodeChannel(
            source=_xyz(c["source"]),
            detector=_xyz(c["detector"]),
            short=bool(c.get("short", False)),
            region=str(c.get("region", "")),
        )
        for c in raw["channels"]
    )
    return Montage(
        name=str(raw.get("name", "montage")),
        channels=channels,
        wavelengths=tuple(float(w) for w in raw.get("wavelengths", (760.0, 850.0))),
        ppf=float(raw.get("ppf", 6.0)),
    )


def build_od_info(montage: Montage):
    """Build an MNE Info of fNIRS optical-density channels for this montage.

    Channel order matches the raw layout: for pair *i*, one channel per wavelength
    in order, named ``S{i}_D{i} {wavelength}``. Lazily imports MNE so importing
    this module doesn't pull MNE in unless a montage path is actually used.

    Args:
        montage: The montage to describe.

    Returns:
        An ``mne.Info`` with one ``fnirs_od`` channel per raw row, whose
        ``loc`` carries the midpoint, source, detector and wavelength.

    Raises:
        ValueError: If the montage does not have exactly two wavelengths.
    """
    import mne

    if len(montage.wavelengths) != 2:
        raise ValueError("Beer-Lambert MBLL needs exactly two wavelengths.")

    ch_names: list[str] = []
    locs: list[np.ndarray] = []
    for i, ch in enumerate(montage.channels):
        src = np.asarray(ch.source, dtype=float)
        det = np.asarray(ch.detector, dtype=float)
        mid = (src + det) / 2.0
        for wl in montage.wavelengths:
            ch_names.append(f"S{i + 1}_D{i + 1} {int(wl)}")
            loc = np.zeros(12)
            loc[:3] = mid
            loc[3:6] = src
            loc[6:9] = det
            loc[9] = wl
            locs.append(loc)

    info = mne.create_info(ch_names, sfreq=1.0, ch_types="fnirs_od")
    for ch, loc in zip(info["chs"], locs, strict=True):
        ch["loc"] = loc
    return info


@dataclass
class BeerLambertOperator:
    """The modified-Beer-Lambert map as a fixed linear operator (µM per unit OD).

    ``apply`` turns paired optical density into HbO/HbR concentration change with
    a single numpy matmul — no MNE call, no allocation of an ``mne.io.Raw`` on the
    hot path. The operator is MNE's own map (extracted by probing), scaled to
    micromolar to match the HemoFrame contract.

    Attributes:
        matrix: ``(2*n_pairs, 2*n_pairs)`` map from the OD vector to the
            interleaved [hbo, hbr] output per pair.
    """

    #: (2*n_pairs, 2*n_pairs) map from OD vector -> interleaved [hbo, hbr] per pair
    matrix: np.ndarray
    #: row indices producing HbO / HbR in the interleaved output
    _hbo_rows: np.ndarray = field(repr=False)
    _hbr_rows: np.ndarray = field(repr=False)

    @classmethod
    def from_montage(cls, montage: Montage) -> BeerLambertOperator:
        """Extract MNE's Beer-Lambert map for a montage (once, at construction).

        Probes ``mne.preprocessing.nirs.beer_lambert_law`` with the OD identity
        basis, so the operator reproduces MNE exactly.

        Args:
            montage: The montage whose distances and wavelengths drive MBLL.

        Returns:
            The operator, in µM per unit OD.

        Raises:
            ValueError: If the montage does not have exactly two wavelengths.
        """
        from mne.preprocessing.nirs import beer_lambert_law

        info = build_od_info(montage)
        import mne

        n = len(info["ch_names"])
        # Probe MNE with the OD identity basis: column j of the response IS the
        # operator's action on OD basis vector j. Because MBLL is linear and
        # per-pair, this reproduces MNE exactly and is block-diagonal per pair.
        probe = mne.io.RawArray(np.eye(n), info, verbose="ERROR")
        hb = beer_lambert_law(probe, ppf=montage.ppf)
        matrix = hb.get_data() * _MOLAR_TO_MICROMOLAR

        # Map output rows to HbO vs HbR by channel name (don't assume ordering).
        names = hb.info["ch_names"]
        hbo_rows = np.array([i for i, nm in enumerate(names) if "hbo" in nm.lower()])
        hbr_rows = np.array([i for i, nm in enumerate(names) if "hbr" in nm.lower()])
        return cls(matrix=matrix, _hbo_rows=hbo_rows, _hbr_rows=hbr_rows)

    def apply(self, od: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Convert paired optical density to concentration change.

        Args:
            od: Optical density, shape ``(2*n_pairs, n_samples)`` in raw-layout
                order.

        Returns:
            ``(hbo, hbr)`` in µM, each of shape ``(n_pairs, n_samples)``.
        """
        hb = self.matrix @ od
        return hb[self._hbo_rows], hb[self._hbr_rows]

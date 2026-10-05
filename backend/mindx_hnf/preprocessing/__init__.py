"""Online, causal fNIRS preprocessing.

Per-subject pipeline run on every RawFrame (MNE-NIRS order, D10):
    raw intensity -> optical density (baseline-frozen reference)
    -> causal motion correction (TDDR) -> short-channel regression
    -> MBLL -> Δ[HbO]/[HbR] -> causal bandpass.

Everything here uses ONLY past/current samples. Zero-phase filtering and any
future-lookahead belong in the offline `analysis/` track, not here.
"""

from mindx_hnf.preprocessing.online import OnlineHemoPipeline

__all__ = ["OnlineHemoPipeline"]

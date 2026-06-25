"""Online, causal fNIRS preprocessing.

Per-subject pipeline run on every RawFrame:
    raw intensity -> optical density -> MBLL -> Δ[HbO]/[HbR]
    -> causal motion correction (TDDR) -> causal bandpass -> short-channel reg.

Everything here uses ONLY past/current samples. Zero-phase filtering and any
future-lookahead belong in the offline `analysis/` track, not here.
"""

from mindx_hnf.preprocessing.online import OnlineHemoPipeline

__all__ = ["OnlineHemoPipeline"]

"""Input layer: LSL stream resolution, time-sync, and frame assembly.

Resolves the per-device LabStreamingLayer streams (two NIRSport2 fNIRS systems
plus ECG/EDA/accelerometer), aligns them on the LSL clock, and emits unified
`RawFrame`s for the pipeline. A synthetic source is provided so the entire loop
runs without hardware (use it for development and CI).
"""

from mindx_hnf.io.sources import FrameSource, SyntheticSource

__all__ = ["FrameSource", "SyntheticSource"]

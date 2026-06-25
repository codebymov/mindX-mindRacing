"""mindX Hyper-NF real-time backend.

fNIRS-based Hyperscanning-Neurofeedback platform for the START-program project
"Technical foundations for multiuser XR-enhanced neuromodulation".

The package is organized along the real-time data flow:

    io -> preprocessing -> ins -> feedback -> (Unity XR)

with an off-the-hot-path persistence track in `storage` and an experiment
scheduler in `session`. See the repository CLAUDE.md for the architecture.
"""

__version__ = "0.1.0"

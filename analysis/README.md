# Offline analysis (WP5)

This directory is the OFFLINE track. It addresses the main analyses in the
project outline §2.1:

- early-vs-late session comparison (do dyads learn to synchronize?), stratified
  by baseline;
- effect of sham feedback on the learning trajectory;
- transfer success (pre/post exchange-game comparison);
- acceptability and behavioral effects.

Approach: Bayesian modelling for individual- and population-level probability
statements (as specified in the proposal).

## Hard separation from the real-time backend

Nothing here is imported by `backend/mindx_hnf` on the real-time path. Offline
code may use whatever it wants — zero-phase filtering (`filtfilt`), full Morlet
wavelet coherence, MNE, scipy, PyMC/Stan, slow I/O. It reads the BIDS/DataLad
artifacts the backend wrote. The dependency arrow points one way: analysis
depends on recorded data, never the live loop.

Install with `pip install -e "../backend[analysis]"` to get mne/scipy.

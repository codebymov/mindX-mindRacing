# mindX Hyper-NF Backend

Real-time fNIRS Hyperscanning-Neurofeedback backend. Python 3.11+.

## Quick start (no hardware)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the whole closed loop on synthetic data:
python -m mindx_hnf.scripts.simulate            # real feedback
python -m mindx_hnf.scripts.simulate --sham     # sham feedback
python -m mindx_hnf.scripts.simulate --full -v  # full-length blocks, verbose

# Tests (the INS / sham / latency tests are the ones that guard the science):
pytest
```

## What runs where

The pipeline is a closed loop assembled in `mindx_hnf/orchestrator.py`:

```
source -> preprocessing -> ins -> feedback -> sink (Unity)
                                       \-> recorder (non-blocking)
```

- **Develop against `SyntheticSource`.** It produces two-subject signals with a
  known, time-varying true coherence, so you can assert that INS tracks reality.
- **`LSLSource` / `LSLOutletSink`** are the hardware seams — documented stubs
  with the exact output contract of their synthetic counterparts.

## Invariants you must not break

See the repository `CLAUDE.md` §4. The short version:

1. Real-time track is causal and non-blocking. No disk/DB/network on the hot path.
2. One clock of record: the LSL clock.
3. Sham must be indistinguishable from real at the participant-facing layer.
4. Every run is reproducible from config + raw recording + git SHA.
5. Session time is hard-capped (~30 min) and abortable at any moment.

## Layout

| Path | Responsibility |
|------|----------------|
| `mindx_hnf/contracts.py` | typed seams between stages (the IR) |
| `mindx_hnf/io/` | LSL resolution, time-sync, synthetic source |
| `mindx_hnf/preprocessing/` | online causal fNIRS preprocessing |
| `mindx_hnf/ins/` | interpersonal neural synchrony estimators |
| `mindx_hnf/feedback/` | INS → game level, sham, smoothing |
| `mindx_hnf/session/` | training protocol scheduler + safety cap |
| `mindx_hnf/storage/` | BIDS/DataLad/Postgres, off the hot path |
| `mindx_hnf/api/` | transport bridge to Unity |
| `mindx_hnf/orchestrator.py` | wires the loop, measures latency |
| `tests/` | INS correctness, sham integrity, latency, safety |

## The TODOs that matter

Grep for `TODO(claude-code)`. The big numeric gaps to fill, all behind stable
contracts so they don't require redesign:
- ~~proper MBLL with extinction coefficients + DPF~~ — done (D10 Phase 1, MNE operator)
- ~~causal TDDR + short-channel regression~~ — done (D10 Phase 2, `preprocessing/causal.py`)
- a properly designed causal Butterworth bandpass (`preprocessing/online.py` `_CausalBandpass`)
- true Morlet wavelet coherence (`ins/coherence.py`)
- real BIDS/DataLad/Postgres writers (`storage/recorder.py`)
- pylsl `LSLSource` (`LSLOutletSink` is done, D9)

The MNE oracle tests (`test_montage_mbll.py`, `test_causal_preprocessing.py`)
SKIP if `mne`/`mne-nirs` are missing — install `.[dev]` so they actually run.

# Scope: MNE-NIRS in the real-time pipeline (not just offline)

**Direction (2026-07-07, PI):** MNE is a crucial, meaningful part of the *online*
processing pipeline — not confined to offline analysis. This supersedes the
earlier "MNE offline-only" stance. This doc scopes HOW to do that **without
breaking causality or the real-time hot-path rules**, grounded in empirical
checks against MNE 1.12 / MNE-NIRS 0.7.3.

## The core tension, and how we resolve it

MNE-NIRS has the *correct, validated* fNIRS numerics (extinction coefficients,
Beer-Lambert, TDDR, short-channel regression). But most MNE functions are written
for **batch, whole-recording** data and some are **non-causal**. The real-time
track forbids future samples, zero-phase filtering, and per-sample allocation.

Resolution: **use MNE for the algorithms and coefficients, applied causally.**
Concretely, three tiers:

1. **Causal & linear → run online directly** (via a precomputed operator).
2. **Non-causal reference → keep the algorithm, swap the reference to a causal
   baseline** (established during the resting block, then frozen).
3. **Inherently batch → keep MNE as the OFFLINE ORACLE**, and run a causal/
   windowed approximation online, unit-tested to match MNE within tolerance.

This keeps MNE first-class in the online pipeline while causality stays inviolable.

## What we verified empirically (see the checks in this session)

- `mne.preprocessing.nirs.beer_lambert_law` on optical density is a **fixed
  linear map** (confirmed: 2× OD in → 2× concentration out). ⇒ **MBLL is causal
  and can be applied per-frame.** This is the single most valuable piece — it is
  currently a TODO *placeholder* in `preprocessing/online.py` (no real extinction
  matrix / DPF). MNE gives us the validated version.
- `optical_density` uses the **time-mean over the recording** as its reference —
  non-causal by construction. Online fix: reference = mean intensity over the
  **baseline block** (causal; frozen at baseline lock, exactly like the feedback
  baseline already works).
- `source_detector_distances`, extinction tables, and PPF handling all come from
  the channel **montage** — which means the montage/optode geometry must be a
  first-class config input (see "New dependency: a real montage" below).

## Per-step plan (maps onto the existing TODOs in `preprocessing/online.py`)

| Step | MNE-NIRS source | Causality | Online strategy |
|---|---|---|---|
| **Optical density** | `optical_density` | non-causal ref (time-mean) | Keep formula `OD = -ln(I / I_base)`; `I_base` = baseline-block mean (causal, frozen). |
| **MBLL → Δ[HbO]/[HbR]** | `beer_lambert_law` (+ extinction tables) | **causal linear** | Extract the per-channel operator `M = (E·L)^-1` once from the montage at construction; apply `conc = M @ od` per frame with numpy. **No MNE call on the hot path.** |
| **Motion (TDDR)** | `temporal_derivative_distribution_repair` | batch/iterative | Online = causal sliding-window TDDR (approx). MNE batch TDDR is the **test oracle**. Ship a simple causal motion step first; upgrade later (ties to O4-style tuning). |
| **Short-channel regression** | `mne_nirs.signal_enhancement.short_channel_regression` | windowable | Running/rolling regression of short onto long channels over the buffer. MNE batch = oracle. |
| **Bandpass** | (MNE uses zero-phase `filtfilt` — FORBIDDEN online) | non-causal | Keep our existing **causal** IIR (`_CausalBandpass`). MNE's is offline-only. |

### Hot-path rule, preserved
The pattern is **"MNE builds the operator; numpy applies it."** MNE constructs the
`Info`/montage and the extinction/distance operators **once** at pipeline
construction; steady-state per-frame processing is numpy matmuls on the
pre-allocated ring buffers. We never build an `mne.io.Raw` per 8-sample chunk.

## New dependency: a real montage (the actual work item)

MNE's fNIRS functions need optode geometry (source/detector positions →
distances, wavelength pairing). The synthetic source today emits 20 anonymous
"channels" with no wavelength pairs or geometry. To put MBLL online we need:

1. **`configs/montage_*.yaml`** — the PFC + rTPJ probe (per `docs/PROTOCOL.md`):
   source/detector layout, wavelength pairs (760/850), short channels, distances.
2. **`SyntheticSource` upgrade** — emit **wavelength-paired** raw intensities with
   a matching montage, so ground-truth INS still works but the data is now
   MBLL-shaped (paired channels), letting the online MBLL run end-to-end with no
   hardware.
3. **`OnlineHemoPipeline` rewrite** — construct the MNE montage + Beer-Lambert
   operator from the config; apply OD(causal baseline) → MBLL(operator) → causal
   bandpass → (TDDR/short-channel) per frame.
4. **Tests** — `test_preprocessing.py`: assert the online MBLL output matches
   `mne` batch `beer_lambert_law` on the same data within tolerance (MNE as
   oracle); assert causality (processing prefix == processing whole on the prefix,
   for the linear steps).

## Dependency & rule changes this implies

- Move `mne` + `scipy` from the `[analysis]` extra into **core runtime deps**
  (they become real-time dependencies). Note the weight: `mne` pulls scipy and is
  ~heavy; acceptable given it's now load-bearing, but pin versions for repro.
- **Update CLAUDE.md**: the "MNE offline-only / analysis must never import into
  real-time" rule is refined to: *MNE-NIRS's causal-safe numerics (extinction
  tables, Beer-Lambert operator) are used online; MNE's batch/zero-phase
  functions remain offline oracles. Causality is still inviolable.*
- Record as decision **D10** in DECISIONS.md.

## Related: MNE on the acquisition side (io/)

`mne-realtime`'s `LSLClient` can back the real-hardware `LSLSource` (still a stub).
Optional — pylsl alone also works — but worth noting since it keeps one library
family across acquisition + preprocessing.

## Suggested phasing

- **Phase 1 — DONE (2026-07-07).** `configs/montage_demo.yaml` (PFC + rTPJ + a
  short channel), `preprocessing/montage.py` (MNE Info + `BeerLambertOperator`
  extracted by probing MNE, scaled to µM), `OnlineHemoPipeline(montage=...)`
  applying MBLL per frame as a numpy matmul with causal OD, and a paired
  `SyntheticSource(montage=...)`. Tests (`tests/test_montage_mbll.py`) pin the
  operator == MNE batch to <1e-9 µM, causality, and an end-to-end synthetic run.
  `mne`+`scipy` are now core deps. The montage-free path is unchanged.
- **Phase 2 (next):** causal TDDR (windowed) + short-channel regression (the
  montage already flags the short channel), each vs the MNE batch oracle. Also:
  freeze the OD reference at baseline-block lock (currently a causal EMA).
- **Phase 3:** MNE `LSLClient` option for `io/LSLSource` when hardware arrives.

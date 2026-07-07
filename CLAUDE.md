# CLAUDE.md — mindX: Multiuser XR-Enhanced Neuromodulation

This file orients Claude Code to the project. Read it fully before making changes.
It is the single source of truth for *what the system is*, *how data flows*, and
*the rules you must not break*. When you change architecture, update this file in
the same commit.

---

## 1. What this project is (one paragraph)

mindX is the technical platform for the START-program project *"Technical
foundations for multiuser XR-enhanced neuromodulation in digital healthcare."*
It implements **fNIRS-based Hyperscanning-Neurofeedback (Hyper-NF)**: two
participants (a *dyad*) wear fNIRS caps and an XR headset, their brain activity
is recorded simultaneously, an **interpersonal neural synchrony (INS)** signal is
computed in near-real-time, and that single joint signal is fed back to both
participants inside a cooperative mixed-reality game ("mind racing"). The
scientific goal is to test whether dyads can learn to *increase their neural
synchrony*, and whether that transfers to cooperative behavior measured by a
neuroeconomic exchange game.

The defining engineering constraint: **this is a soft-real-time closed loop with
a human in it.** Latency, determinism, and reproducibility matter more than raw
throughput. A feedback signal that is correct but 3 seconds late is a wrong
feedback signal.

---

## 2. The data flow (memorize this)

```
 Participant A                         Participant B
 ┌──────────────┐                      ┌──────────────┐
 │ NIRSport2 (A)│                      │ NIRSport2 (B)│
 │ Ecg/EdaMove4 │                      │ Ecg/EdaMove4 │
 └──────┬───────┘                      └──────┬───────┘
        │  LSL streams (one per device)        │
        └───────────────┬──────────────────────┘
                        ▼
              ┌─────────────────────┐
              │  io/ : LSL inlets    │  resolve + time-sync all streams
              │  → unified frames    │  (LSL clock, dejittered)
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │ preprocessing/      │  per-subject, ONLINE, causal only:
              │ optical density →   │  - OD conversion
              │ MBLL → Δ[HbO]/[HbR] │  - motion correction (TDDR)
              │ + short-channel reg │  - bandpass, short-distance regression
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │ ins/                │  joint feature across BOTH subjects:
              │ wavelet coherence   │  windowed, run-time-efficient estimator
              │ → scalar INS(t)     │  → one number in [0,1] per update tick
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │ feedback/           │  map INS(t) → game parameter
              │ smoothing, baseline │  (car speed, audio pitch/gain)
              │ correction, SHAM    │  sham = replay another dyad's signal
              └──────────┬──────────┘
                         ▼ (LSL outlet or websocket)
              ┌─────────────────────┐
              │  Unity XR game      │  "mind racing": speed/pitch ∝ INS
              │  (separate repo dir)│  leaderboard, scoring, scene sync
              └─────────────────────┘

 Everything also forks to:  storage/ (BIDS + DataLad versioned artifacts,
 Postgres for metadata) and session/ (block scheduler: rest/task/sham).
```

**The two-track rule.** There are two tracks that must stay decoupled:
1. **Real-time track** (`io` → `preprocessing` → `ins` → `feedback`): causal,
   bounded-latency, no future samples, no blocking I/O on the hot path.
2. **Persistence track** (`storage`): may be slower, runs off the hot path,
   never blocks feedback. If storage is down, the loop keeps running.

If you ever find yourself awaiting a database write inside the feedback loop,
stop — that is a bug, not a feature.

---

## 3. Repository layout

```
backend/                    Python real-time backend (primary codebase)
  mindx_hnf/
    io/                     LSL stream resolution, time-sync, frame assembly
    preprocessing/          online causal fNIRS preprocessing (per subject)
    ins/                    interpersonal neural synchrony estimators
    feedback/               INS → game-parameter mapping, sham, smoothing
    session/               block/run scheduler (rest/task), training protocol
    storage/                BIDS writer, DataLad, Postgres metadata
    api/                    websocket / LSL bridge to Unity, control endpoints
  tests/                    pytest; the INS + sham + latency tests are load-bearing
  configs/                  YAML run configs (montage, bands, protocol timings)
  scripts/                  CLI entry points (run_session, replay, simulate)
unity/                      Unity XR project (mind racing game) — C#
  Assets/Scripts/           game logic, LSL inlet, feedback → car/audio mapping
analysis/                   OFFLINE analysis (Bayesian models, WP5). NOT real-time.
docs/                       architecture, glossary, protocol, hardware notes
.claude/                    Claude Code config: this dir + commands
```

The Python package is `mindx_hnf`. Import as `from mindx_hnf.ins import coherence`.

---

## 4. Conventions and hard rules

- **Python**: 3.11+, type hints everywhere, `ruff` + `black`, `mypy` clean.
  No bare `except`. Numpy for signal math; do NOT pull in pandas on the hot path.
- **Real-time hot path** (`io`/`preprocessing`/`ins`/`feedback`): no allocation
  in steady state where avoidable, no logging above DEBUG per-sample, no network
  or disk calls. Pre-allocate ring buffers.
- **Time**: there is exactly one clock of record — the **LSL clock**. Never mix
  `time.time()` into sample timestamps. All cross-subject alignment uses LSL
  timestamps, dejittered.
- **Causality**: online preprocessing and INS use only past/current samples.
  Any filter must be causal (no `filtfilt`, no zero-phase) on the real-time track.
  The offline track (`analysis/`) may use whatever it wants.
- **Sham must be indistinguishable**: sham feedback replays a real other-dyad
  signal for the *same session/task*. The participant-facing code path for sham
  and real feedback must be identical except for the signal source. Never branch
  on "is this sham?" anywhere a participant could perceive a difference.
- **Reproducibility**: every run is fully reconstructable from (config YAML +
  raw LSL recording + git SHA). Stamp the git SHA and config hash into every
  artifact. This is a research instrument; "it worked on my machine" is a failure.
- **Standards compliance**: neural data is written **BIDS**-compliant; follow the
  fNIRS best-practice and CRED-nf checklists referenced in docs/PROTOCOL.md.
- **Safety**: a training session is capped at ~30 min. The session scheduler
  enforces hard time limits and must support immediate abort at any time.
- **No participant PII in code or logs.** Use pseudonymized dyad/subject IDs only.

---

## 5. Where to start depending on the task

- Adding/optimizing an INS estimator → `backend/mindx_hnf/ins/`, mirror the
  `INSEstimator` protocol, add a test in `tests/test_ins.py`.
- Touching preprocessing → keep it causal; add it to the online pipeline only if
  it has a streaming-capable implementation. Otherwise it belongs in `analysis/`.
  **MNE-NIRS is used online** (D10) for its *causal-safe* numerics — the
  Beer-Lambert MBLL operator and extinction tables — built once at construction
  and applied per-frame with numpy; MNE's batch/zero-phase functions stay as
  offline oracles the causal versions are tested against. See
  `docs/MNE_ONLINE_SCOPE.md`.
- Game/feedback feel → the *mapping* lives in `feedback/` (backend, testable);
  the *rendering* lives in `unity/`. Keep them separated by a thin contract.
- New experiment block / protocol change → `session/` + `configs/`.
- Offline statistics for the paper → `analysis/`, never import from there into
  the real-time backend.

## 6. How to run things

See `backend/README.md`. Key entry points:
- `python -m mindx_hnf.scripts.simulate` — run the whole loop on synthetic data
  (no hardware). **Use this for development and CI.**
- `python -m mindx_hnf.scripts.run_session --config configs/default.yaml` — live.
- `pytest` in `backend/` — the latency, INS-correctness, and sham-integrity
  tests are the ones that actually guard the science. Don't let them rot.

## 7. Open questions / decisions not yet made

Tracked in `docs/DECISIONS.md`. When you resolve one, move it there with the
rationale. Recently decided: **OpenXR baseline for HTC Vive / Quest Pro / Varjo
XR-4 (D6)**; **one dyadic INS signal → one shared cooperative car (D7)**, refined
to **two cars + two switchable session modes (D8)**; **transport to Unity = LSL
(D9)** — see `docs/LSL_UNITY_SETUP.md`; and **MNE-NIRS used online for its causal
numerics (D10)** — see `docs/MNE_ONLINE_SCOPE.md`. Still open: the INS windowing
trade-off (latency vs. coherence stability, O3/O4), and **multiplayer scene sync
for the shared per-player MR view (O5)** — see `docs/O5_MULTIPLAYER_SCOPE.md`.
See `unity/XR_SETUP.md` for the build recipe.

# LSL feedback: backend → Unity setup recipe

How to run the synthetic INS → Unity car loop over LSL (decision **D9**). This is
the transport seam: the Python backend publishes feedback on an LSL stream and
the Unity game subscribes to it. It works with **zero neural hardware** — the
synthetic source stands in for the fNIRS caps.

```
simulate --lsl  ──►  LSL stream "mindx_feedback"  ──►  LslFeedbackTransport  ──►  FeedbackReceiver ──► car speed / engine audio
(Python backend)        (liblsl on the LAN)              (Unity, LSL4Unity)         (per car, routed by subject)
```

## 1. Backend (already done, no hardware)

```bash
cd backend
pip install -e ".[hardware]"          # installs pylsl + liblsl
python -m mindx_hnf.scripts.simulate --lsl
```

You should see: `Publishing feedback on LSL stream 'mindx_feedback' — connect Unity now.`
The stream carries one 5-channel float32 vector per feedback tick:
`level, raw_ins, mode, session_mode, subject_index` (see
`backend/mindx_hnf/api/sink.py::FEEDBACK_CHANNELS`). Each sample keeps its backend
LSL timestamp — one clock of record.

Verified round-trip: `pytest backend/tests/test_lsl_outlet.py` (auto-skips if
pylsl isn't installed).

## 2. Unity: install LSL4Unity (one-time, manual)

This is the one step that must be done in the Unity Editor (it is not committed,
because a bad package URL breaks project resolution for everyone):

1. **Window ▸ Package Manager ▸ + ▸ Add package from git URL…**
   Add the LSL4Unity UPM package, e.g.
   `https://github.com/labstreaminglayer/LSL4Unity.git#upm`
   (confirm the current URL/branch — forks move; the package must expose the
   `LSL` C# namespace with `StreamInlet`/`StreamInfo`).
2. **Place the native `liblsl` binary** for each target platform under
   `unity/Assets/Plugins/` (or wherever the package expects it):
   - Windows editor/standalone: `lsl.dll` (x86_64)
   - Android / Quest (if building to headset): `liblsl.so` (arm64-v8a)
   The managed C# wrapper needs the matching native lib or `resolve_stream`
   throws at runtime.
3. If you get a namespace compile error in `LslFeedbackTransport.cs`, swap
   `LSL.LSL.resolve_stream` → `LSL.liblsl.resolve_stream` (older fork layout).
   The logic is identical; only the namespace differs.

## 3. Unity: wire the scene

On the car GameObject (the one with the car body Transform):
- Add **FeedbackReceiver**.
  - `Stream Name` = `mindx_feedback`
  - `Auto Connect` = ✓
  - `Car Subject Index` = `0` for car A, `1` for car B (ignored for the shared
    Hyperscanning signal — a shared sample drives every car).
  - `Car` = the car Transform, `Engine` = an AudioSource (optional).

Press Play **while `simulate --lsl` is running**. The car speed and engine
pitch/gain should track the rising synthetic INS level.

## What this does and does NOT give you

- ✅ The feedback signal reaches Unity on the LSL clock; both headsets can each
  run an inlet and receive the identical joint signal.
- ✅ Sham is indistinguishable: `mode` is decoded for logging only, never
  branched on.
- ❌ It does **not** make both headsets see the *same car at the same physical
  place*. That is multiplayer scene sync — **O5**, still open (owner: VCI). LSL
  is a signal transport, not a game-state netcode.
- ❌ It is still **synthetic**: real fNIRS ingestion (`io/LSLSource`) is a
  separate unbuilt seam. See `docs/DECISIONS.md` and the project status.

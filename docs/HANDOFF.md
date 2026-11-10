# Session handoff — start here

Read this first in a new Claude Code session (any device), right after
`CLAUDE.md`. It records where the project stands and what to do next. Update it
at the end of every session, in the same commit as the work.

**Last updated:** 2026-10-05 (commits `4ad6f55` … `HEAD` on `main`).

## Where we are

| Area | State |
|---|---|
| Backend real-time loop | Works end-to-end on synthetic data (`simulate`, `simulate --montage configs/montage_demo.yaml`, `simulate --lsl`). |
| MNE online (D10) | Phase 1 (MBLL) + Phase 2 (baseline-frozen OD, causal TDDR, wavelength-paired short-channel regression) **done**, each tested against MNE/MNE-NIRS. See `docs/MNE_ONLINE_SCOPE.md`. |
| Backend → Unity transport (D9) | LSL. Wire format = `contracts/feedback_wire.json`, tested from both languages. |
| Unity (branch `unity6-mcp`, worktree `MindX-unity6`, Unity 6000.5.1f1) | Unity MCP works (`Unity_RunCommand`, `Unity_GetConsoleLogs`). **LSL4Unity v1.16.0 is embedded** in `unity/Packages/com.labstreaminglayer.lsl4unity` with a one-line Unity 6.5 patch (`BaseOutlet.cs`: `GetInstanceID` → `GetEntityId`); `MindX.Lsl` compiles. **Level A on desktop works**: `Assets/Scenes/TwoCarTest.unity` (WASD/arrows steer, speed = base + bonus × LSL level) verified against `simulate --lsl --full`: both cars connected, level rose from 0 after the baseline block. Ubiq not installed. |
| Multiplayer O5 (Ubiq, D11/D12) | Scaffolded only; Ubiq scripts never compiled against Ubiq. |
| Tests | Python: 48 pass, 0 skipped. C# EditMode: 11 tests, written + compiled, not executed. See `docs/TESTING.md`. |
| CI | `.github/workflows/backend.yml` (Linux + Windows, Py 3.11/3.13). No Unity CI. |
| Style | Python: Google style + Google docstrings, enforced by ruff `D`. C#: Microsoft + Unity (`unity/.editorconfig`). |

## Next tasks, in order

1. **Activate a Unity licence** (sign in to Unity Hub, Personal is fine) on the
   machine with Unity 2022.3.5f1, then run the EditMode suite (command in
   `docs/TESTING.md`) and fix anything it finds. Blocked on the user.
2. **Unity Editor pass → "Level A" demo** (synthetic signal driving the car in a
   headset): install LSL4Unity (`docs/LSL_UNITY_SETUP.md`, URL verified), open
   the scene, `simulate --lsl`, confirm the car responds; build to headset.
3. **Automated E2E test**: PlayMode test subscribing to `simulate --lsl`,
   asserting car speed follows the level (`docs/TESTING.md` gaps).
4. **Golden-output regression test**: freeze a fixed-seed synthetic run's
   HbO/INS output.
5. **Remaining MNE items** (small, before first real recording): causal
   signal-quality check (MNE scalp coupling index, during baseline → drop bad
   channels); replace placeholder `_CausalBandpass` with a causal SOS
   Butterworth. **Phase 3** (live NIRSport2 via LSL, `io/sources.py::LSLSource`)
   needs hardware — it is the critical path to a live-brain demo.
6. Ubiq install + first compile of `Assets/Scripts/Ubiq/`, then O5 integration.
7. Open decisions: O7 (per-subject NF feature for Individual mode), O3/O4 (INS
   window / estimator, need pilot data), O6 (second car). See `docs/DECISIONS.md`.

## Demo roadmap (agreed framing)

- **Level A** — synthetic signal → car in VR: ~1 week after the Unity licence.
- **Level B** — one person, live fNIRS, Individual mode: + `LSLSource`, signal
  quality, O7 feature: ~2–4 weeks, hardware-dependent.
- **Level C** — two people, live hyperscanning, co-located: 1–2+ months.
- fNIRS is slow (5–7 s hemodynamic lag, 30 s INS window): set audience
  expectations. EEG is not in the pipeline at all.

## Environment pitfalls (read before running anything)

- The backend venv is a **Windows** venv: from WSL use
  `backend/.venv/Scripts/python.exe` (plain `python` doesn't exist there).
  New device: `pip install -r backend/requirements.lock && pip install -e backend --no-deps`.
- **Never let oracle tests skip silently.** If `mne`/`mne-nirs` are missing they
  skip; always run `pytest -rs`.
- Windows Python writes **CRLF** when opening files with `"w"`; the repo is LF
  (`.gitattributes`). Use `newline="\n"` or fix with `sed -i 's/\r$//'`.
- Every new Unity file/folder needs a committed `.meta` with a stable GUID;
  move scripts with `git mv` together with their `.meta`.
- `unity/Temp/UnityLockfile` from 2026-06-25 is stale, not a running Editor.
- The ruff version is pinned in the lock (0.16.x, stricter defaults than older
  ruff); run ruff from the venv, not a global one.
- Unity C# can be compile-checked without a licence using Unity's bundled
  Roslyn (`Editor/Data/NetCoreRuntime/dotnet.exe` + `DotNetSdkRoslyn/csc.dll`)
  against `Editor/Data/Managed/UnityEngine/*.dll`; that is how the current
  Unity code was verified.

## Housekeeping waiting on a decision

- Stray empty Unity project at the repo root (`/Assets`, `/Library`,
  `/Packages`, `/ProjectSettings`; ignored) — delete after user OK.
- Git LFS not enabled; large binaries (34 MB PNG, 12 MB MP4) in plain history.
- `backend/.venv/Lib/site-packages/~umpy`: leftover pip temp dir, safe to delete.

## Session log

- **2026-11-10** — Unity 6 + MCP → desktop Level A (branch `unity6-mcp`).
  MCP confirmed working after the AI terms were accepted. The LSL4Unity git
  package did not compile on 6000.5 (`GetInstanceID` is an error), so it is
  embedded and patched. Added `FeedbackReceiver.Level/TargetSpeed/IsConnected`,
  an optional `CarDriver.LevelSource`, and `FeedbackHud`; wired
  `TwoCarTest.unity`. **Level tuning (resolved):** the level sat at ~0.05
  because of two demo defects, not the estimator. (1) The synthetic coherence
  ramp (`0.1 + 0.02 t`) hit 0.9 at 40 s, inside the 60 s baseline, so baseline
  correction removed it; the ramp now follows the session plan
  (`coherence_profile`: low in baseline/rest, ramps over 60% of each task
  block). (2) After the pipeline the INS spans only ~0.08 (c=0.1) → ~0.17
  (c=0.9) at a 22 s window, so gain 2.0 capped the level near 0.17; the demo
  gain is now 10 (`DEMO_GAIN`). Full-length curve: 0.00 in baseline, ~0.2 at
  +30 s, ~0.78 at +100 s, back to ~0 in rest, climbs again. Added
  `simulate --log-csv` (`RecordingSink`, buffered, written on close). Real data
  needs its own calibration. A 60 s window saturates the estimator (0.71 at
  c=0.1), so keep ~22–30 s (O3/O4).
  **Placement fixed (same day):** cars had spawned ~12 m up on top of a boundary
  wall (the old spawn probe hit the 15 m `Cube` walls) and `CarDriver` zeroed
  gravity by overwriting the whole velocity. The scaffold now spawns on a
  `Track_line*` tile surface, facing the ring tangent, ±2.5 m about the road
  centre line, with roll/pitch frozen; `CarDriver` keeps vertical velocity; the
  scaffold also wires `FeedbackReceiver` + HUD. Measured geometry (do not
  guess): car 2.1×1.4×4.8 m, road tiles 15 m wide (straights 15×15, corners
  30×30), road surface y≈0.0–0.1, boundary walls 15 m tall, ring ≈105×107 m.
  Proportions are realistic (circuit width), so nothing was rescaled. Unity
  inspection recipe: `Unity_RunCommand` for bounds/raycasts,
  `Unity_SceneView_CaptureMultiAngleSceneView` for images (open a Scene View
  window first); `Unity_Camera_Capture` failed with 64-bit EntityIds.
  Known: `FeedbackReceiver.Start` blocks ~5 s per car in `resolve_stream` when no
  stream exists — start the backend first, or move resolve off the main thread.
  The Unity 6 API updater changed `velocity` → `linearVelocity`
  (`CarController`, `XRCarController`, `CarDriver`): this branch must not merge
  to `main` (2022.3) as-is. Still broken: XR rig prefab (XRI 3 migration),
  `Road (2)` missing prefab; the console shows 5 missing-script warnings from
  XR settings. Start the backend with
  `backend/.venv/Scripts/python.exe -m mindx_hnf.scripts.simulate --lsl --full`
  (~5 min; default run lasts only ~17 s).
  **Table AR preview (simulated):** menu *MindX ▸ Build Table AR Preview
  (simulated)* builds `Assets/Scenes/TableARPreview.unity`. The game still runs
  1:1; the table shows scaled visual twins (`ScaledTwin`, scale 0.0075, ring ≈
  0.8 m) of the track and cars, seen from a seated headset-like camera. Physics
  is deliberately not run at miniature scale (contact offset 1 cm > scaled wall
  thickness; wheel colliders don't scale). Verified: twin mapping error 0.00000 m
  while driving; EditMode 20/20. It is a SIMULATION of the AR view (no
  passthrough, no anchoring) — say so in the presentation. Real AR needs the XR
  rig (still broken) and a headset. Unity re-imported TextMesh Pro assets on its
  own (uncommitted, not ours). Table road was patchy until the table top was
  lowered 4 mm (road underside is coplanar with the anchor height → z-fighting;
  it was not shadows).
  **Live INS curve + sham toggle:** `FeedbackHud` draws a rolling curve of the
  level (`LevelHistory`, 1 s buckets, 320 = whole 5-min session) and an operator
  overlay on **F1** (hidden by default: source REAL/SHAM, raw INS, sham stretches
  tinted orange). Participant view is one uniform colour. The source is changed
  on the backend terminal: `simulate --lsl --full --toggle`, then press Enter
  (or `s`) to flip REAL ↔ SHAM live (`FeedbackModeSwitch`; orchestrator reads it
  every frame and keeps the sham replay indexed by task time). The sham trace is
  now another synthetic dyad (`build_sham_trace`: seed 7, ramps 25% of a block
  later and slower, same pipeline/scale); the old constant 0.30–0.35 trace would
  have pinned the level at 1.0 after the gain change. Verified end to end:
  Unity source flipped real→sham→real exactly at the operator's two Enters
  (HUD timeline `REAL@0 SHAM@128 REAL@188`); real peak 0.71–0.80, sham ~0.2–0.36.
  Tests: backend 59, Unity EditMode 26.
  **Game mechanics (added later the same day):** coins and scoring did NOT exist
  anywhere in the repo or its history (only a line in the CLAUDE.md diagram), so
  they were built: `Coin` (+ saved `Assets/Prefabs/Coin.prefab`, spinning gold disc,
  trigger, respawns after 20 s), `CarScore` (+10 per coin, −5 per car-to-car crash
  to BOTH cars with a 1.5 s cooldown; may go negative), `ScoreHud` (own score in
  each player's own viewport + TEAM coins). 24 coins on 3 lanes, placed by
  ray-casting the inner/outer walls. Brain → speed → coins: measured ~10 coins/min
  at 5 m/s vs 20–26 coins/min at 15 m/s (level 0.7); only 24 coins, so it saturates
  at high speed. In hyperscanning both cars share one level, so this is a TEAM
  challenge; per-player competition needs Individual mode (O7, open).
  **Autopilot (`TrackAutopilot`):** wall-following steering (rays), per-car lane
  ±2.4 m + weave 1.4 m (periods 23/31 s) so the cars take different lines; speed
  still comes from the level. Stress test at fixed 8/13/18 m/s (35–55 s each, 1–2+
  laps): 0 wall hits, 0 crashes, 0 recoveries. Earlier version hit walls at 20 m/s;
  the fix was fading the lateral term near corners. The table scene now has TWO
  headset views side by side (P1/P2 seats, opposite sides), light from the side
  (a seat looking into the light washed out), matte table. Game view fixed at
  1920×1080 with `PlayModeWindow.SetCustomRenderingResolution` (the MCP command
  sandbox forbids `System.Reflection`; don't work around it). Pitfall found twice:
  runtime-only caches/lists are lost when the scene reloads for Play — serialize
  them (ScoreHud entries) or rebuild lazily (ScaledTwin). Tests: Unity 44.
  **Two bugs found by measuring, not guessing:** (1) the autopilot's side rays
  counted the OTHER car as a wall, so abreast cars steered each other into the
  walls (P2 touched the inner wall within seconds of the start) — it now measures
  walls only (ignores anything with a Rigidbody); verified 0 wall hits over 2 min.
  (2) Scores were unfair (P2 ≈ 2× P1's coins): the inside car laps ~9% faster and
  a SHARED centre lane meant P2 always reached those coins first (a coin stays
  gone 20 s). Coins are now in two lanes, one per player (12 each, pickup radius
  2.4 m); result P1 22 / P2 23 coins, each from its own lane. `TrackAutopilot`
  keeps diagnostics (`WallHitPositions`, straight-section lateral mean) and `Coin`
  keeps `CollectedBy`; use them before tuning. Remaining honesty point: in
  hyperscanning both cars have the same speed, so scores differ only by lap length
  (~9%) and the occasional crash; a per-player brain→coins comparison needs
  Individual mode (O7).
  **Demo on the MNE path:** `simulate --lsl --full --toggle --montage
  backend/configs/montage_demo.yaml` runs the MNE-NIRS preprocessing live on
  synthetic data; gain is `MONTAGE_GAIN = 8` (INS spans ~0.15 → 0.22–0.25 there;
  the generic gain 10 saturates the level at 1.0 — a test guards this).
  `analysis/make_demo_brain_figure.py` draws the montage, both players' ΔHbO and
  the INS/level (labelled SYNTHETIC) into `docs/demo/brain_synthetic.png`;
  `analysis/make_demo_gif.py` + `DemoFrameRecorder` build the time-lapse GIF
  (no ffmpeg on this machine). Tests now: backend 60, Unity 44.
  **Demo materials:** `docs/DEMO_RUNBOOK.md` (bullets only, black and white) with
  screenshots and a time-lapse GIF in `docs/demo/`; a styled version was published
  as a private Claude artifact (link given in the session). Slides come next (web
  deck, 15 min). **Waiting on a human decision:** (a) Individual mode / O7 — the
  per-player feature that would let the two cars have different speeds; (b) whether
  to install ffmpeg for an MP4; (c) the XR rig migration to XRI 3. Phone approvals
  need Remote Control enabled by the user (`/remote-control` in the session); the
  PushNotification tool only reaches the terminal until then.
  **Individual mode DEMO PLACEHOLDER (does NOT decide O7):** `simulate --individual
  [--lsl --full --montage ...]` gives each player their own synthetic activation
  profile and signal (placeholder feature = causal windowed 0.01-0.1 Hz power of that
  player's own channel-mean HbO, `scripts/individual_demo.py`), their own baseline
  and INDIVIDUAL-mode mapper; one sample per player per tick (subject index 0/1).
  Gains are measured (1000 generic, 5 on the MNE montage path). No sham/--toggle in
  this mode. Unity needed a fix: `FeedbackReceiver` now drains all pending samples
  and `LslFeedbackTransport.TryGetLatest` returns one per call (it kept only the
  newest, so a car never saw its own sample); the table caption now picks its text
  from the received session mode (`{mode}` token). Measured end to end on the MNE
  path at play t=172 s: P1 level 0.80 / 17.1 m/s / 38 coins per min, P2 level 0.39 /
  10.8 m/s / 22 per min, 0 wall hits. Tests: backend 67, Unity 45.

- **2026-10-05** — MNE Phase 2 (`4ad6f55`). Found the venv lacked mne, so the
  Phase 1 oracle tests had been silently skipping. Cross-language wire contract +
  Unity assembly split + EditMode tests + CI + lock file (`0cab246`). Fixed bug:
  an unknown subject drove every car in Individual mode. Google docstrings
  across the backend (`c7192d8`). Found that MNE-NIRS 0.7.3 regresses both
  wavelengths on the 760 nm short channel (we pair by wavelength). Corrected
  LSL4Unity/Ubiq install URLs. Mutation check: changing the channel order, a
  sentinel, or the sham code on the Python side now fails the contract test.
  First CI run (Linux+Windows × Py 3.11/3.13) caught an exact-float assert in
  `test_sham_integrity.py` failing on numpy 2.4 (1e-16); fixed with a 1e-12
  tolerance.

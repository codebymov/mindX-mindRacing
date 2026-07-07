# Decisions Log

Architecture decisions and open questions. When you resolve an open question,
move it to "Decided" with the date and rationale, in the same commit as the code.

## Decided

- **D1 — Typed seams between pipeline stages.** Stages communicate only via the
  `contracts.py` dataclasses/protocols. Rationale: independent testing,
  swappable implementations, no cross-stage coupling.
- **D2 — Synthetic source is first-class and the CI/dev default.** Rationale:
  hardware is scarce and gated by ethics approval; ground-truth synthetic data
  is the only way to validate INS correctness and measure latency deterministically.
- **D3 — One clock of record (LSL).** Rationale: cross-subject/cross-device
  alignment is otherwise silently wrong.
- **D4 — Persistence is non-blocking and may fail without affecting feedback.**
  Rationale: the real-time loop is the instrument; storage is the notebook.
- **D5 — Sham = replayed real other-dyad signal, identical mapping.** Rationale:
  experimental validity of the control condition.
- **D6 — OpenXR is the baseline runtime; target HTC Vive, Meta Quest Pro, Varjo
  XR-4 (2026-06-25).** Resolves O1. Build against OpenXR core + extensions
  (e.g. `XR_EXT_eye_gaze_interaction` for eye tracking), NOT vendor SDKs, so one
  code path serves all three headsets. Vendor APIs (Meta/Varjo pupil diameter,
  face/body) are an optional *later* add-on for richer research data, never the
  baseline. Rationale: device choice was gated on eye tracking + comfort + Unity
  integration; OpenXR avoids betting the codebase on a single vendor and keeps
  the door open to Varjo XR-4 as the high-end target.
- **D7 — One dyadic signal → one shared car (2026-06-25).** INS is a single
  number for the pair, so the game has ONE shared car that both participants see
  at the same physical position and influence together via their joint synchrony
  — this *is* the cooperative mechanic. All gameplay lives in **track-local
  space** so it is independent of where the table/world anchor lands (placement
  and gameplay stay decoupled). Supersedes the two-car competitive prototype in
  `_Reference/PhotonConnection.unity`; the colored car variants survive as
  cosmetics only. The backend contract already matches this: `FeedbackReceiver`
  drives a single car Transform from one `level`.
- **D8 — Two cars + two switchable session modes (2026-06-26).** Refines D7 and
  resolves O6. The game has a car per player and runs in one of two modes chosen
  per session:
  - **Hyperscanning mode** — the single joint **INS** signal drives BOTH cars
    together (each player owns a car body, both reflect the dyad's synchrony).
    This preserves the core science of D7; it is still ONE signal, two bodies.
  - **Individual-NF mode** — each car is driven by **that player's own
    neurofeedback** (a per-subject signal, NOT interpersonal synchrony). This is
    a distinct paradigm and requires the backend to compute and emit a per-subject
    feedback signal in addition to INS.
  Implications: (1) the `FeedbackSink`/`FeedbackSample` contract must carry a
  session `mode` and, in Individual mode, a per-subject channel; the INS path is
  unchanged for Hyperscanning. (2) Unity decouples *who drives the car* behind
  `ICarInput` (keyboard for dev, `NeurofeedbackCarInput` for runtime, network for
  the remote player) so the mode just selects the source. (3) **Hard rule still
  holds:** sham, one-clock and provenance apply to every feedback signal; a car
  must never be driven by a future/non-causal value. The single-player ML-Agent
  idea from O6 becomes a variant of Individual mode (the 2nd car's driver is an
  ML-Agent instead of a remote player) — still open, not yet built.

- **D9 — Transport to Unity = LSL (2026-07-07).** Resolves O2. Feedback is
  published as an LSL stream (`api.sink.LSLOutletSink`, stream `mindx_feedback`)
  and consumed by an LSL4Unity inlet (`unity/.../LslFeedbackTransport.cs`).
  Rationale: keeps the game on the **one clock of record** (D3) — each sample is
  pushed with its own backend LSL timestamp, not a fresh one — and lets the
  feedback stream be recorded into the same XDF as the neural streams for
  reproducibility. Websocket was the alternative (simpler on the Unity side) but
  would have forced manual time handling and a second clock. The sample is one
  5-channel float32 vector (`level, raw_ins, mode, session_mode, subject_index`);
  string fields are encoded numerically and decoded on the Unity side for logging
  only (never branched on — sham hard-rule). Both headsets subscribe to the same
  stream, so both get the identical joint signal. **Scope note:** LSL carries the
  *feedback signal* to both headsets; it does NOT synchronize game state /
  positions / a shared world anchor — that is O5 (multiplayer scene sync), still
  open. Setup recipe: `docs/LSL_UNITY_SETUP.md`.

- **D10 — MNE-NIRS is used in the real-time pipeline, not only offline
  (2026-07-07).** MNE-NIRS's validated fNIRS numerics (extinction coefficients,
  Beer-Lambert MBLL) are load-bearing in the ONLINE preprocessing, applied
  causally. This does not weaken D3/causality: MBLL is a fixed linear operator
  (empirically verified) so it runs per-frame; optical density keeps MNE's
  formula but references a causal baseline-block mean instead of the
  whole-recording mean; MNE's batch/zero-phase functions (TDDR, filtfilt) stay as
  OFFLINE ORACLES that the causal online approximations are unit-tested against.
  Pattern: **MNE builds the operator once at construction; numpy applies it on the
  hot path** (no per-frame `Raw`). Implies: `mne`+`scipy` move from the
  `[analysis]` extra to core runtime deps; a real optode **montage** becomes a
  first-class config; the synthetic source must emit wavelength-paired intensities.
  Full plan + verified findings: `docs/MNE_ONLINE_SCOPE.md`. Supersedes the
  earlier "MNE = offline analysis only" framing.

- **D12 — O5 netcode = Ubiq, self-hosted on the lab LAN (2026-07-07).** Resolves
  the O5 netcode sub-decision. Ubiq (UCL, Apache-2.0) is self-hostable with no
  third-party/cloud services, is built for VR *research* (session/room model,
  GDPR-safe), and co-locates on the same offline LAN as the LSL streams — matching
  the one-clock / reproducibility / no-PII hard rules. Rejected: Photon Fusion 2 /
  Normcore (cloud relay → external dep + uncontrolled latency in a soft-real-time
  loop); Mirror was the close runner-up (MIT, self-hostable) and stays the
  fallback if VCI has existing Mirror expertise. The Ubiq-specific networking sits
  behind a thin authority seam (`ISharedCarNetwork`) so the choice is swappable,
  per D1. Owner: VCI (may override on existing-expertise grounds).

- **D11 — Co-location = deterministic manual controller registration
  (2026-07-07).** Both headsets agree on one real-world origin by pointing a
  tracked controller at shared physical fiducial(s) at session start; each inverts
  to a shared origin transform. Rationale: cross-vendor cloud/anchor co-location
  does NOT exist in 2026 — Meta Shared Spatial Anchors are Quest-only + cloud-gated,
  OpenXR anchor extensions standardize the API but define no cross-runtime anchor
  interchange, and camera/QR is Quest-3-class only. Manual controller registration
  is the ONLY method that works across the D6 set (Vive/Quest Pro/Varjo), and it is
  the most reproducible (no cloud, no Meta account, no PII) — the registered origin
  IS the D7 track-local root. Full analysis: `docs/O5_MULTIPLAYER_SCOPE.md`.

## Open

- **O7 — Per-subject neurofeedback feature for Individual mode.** D8's contract
  seam is in (`FeedbackSample` carries `session_mode` + `subject`; the mapper is
  per-subject in Individual mode). What is NOT built is the *signal* that feeds
  Individual mode: a per-subject NF feature (e.g. per-subject HbO/HbR band power
  or a within-subject synchrony surrogate) computed causally on the hot path,
  distinct from the joint INS. Open: which feature, computed where (a per-subject
  estimator alongside `ins/`, or in `preprocessing/`), and its baseline/normalization.
  Hyperscanning (the joint-INS shared car) is unaffected and remains the default.
- **O3 — INS windowing trade-off.** Longer window = more stable coherence but
  more feedback latency / slower responsiveness; shorter = jumpier but snappier.
  Tune against pilot data; the estimator exposes `window_s` / `update_every_s`.
- **O4 — Exact INS estimator.** Welch-coherence baseline is in; whether to move
  to true Morlet wavelet coherence (and which scales) depends on pilot stability.
- **O5 — Multiplayer scene sync for the shared MR view.** Architecture scoped in
  `docs/O5_MULTIPLAYER_SCOPE.md`; co-location resolved (D11); netcode resolved
  (D12 = Ubiq). **Integration in progress:** the seam (`ISharedCarNetwork` /
  `SharedCarState`), the Ubiq adapter (`UbiqSharedCarNetwork`), the host↔client
  glue (`SharedCarAuthority`, LSL→car→replicate), and co-location
  (`ColocationRegistration`) are scaffolded — see `docs/UBIQ_SETUP.md`. Remaining:
  Ubiq package install + in-editor build/verify, spawning the car via Ubiq's
  `NetworkSpawner` (shared `NetworkId`), avatar prefab wiring + fidelity, a
  calibration UI for co-location, and whether P1/P2 also get an ICarInput steering
  role (ties O6). Owner: VCI.
- **O6 — Second car: role & controller per game mode.** The shared INS car (D7)
  stays the science instrument and is unchanged. A *second* car is wanted for
  non-hyperscanning modes: in **multi-user** it is another participant's car; in
  **single-player** it is a **Unity ML-Agent** that adapts its pace to the
  patient's neurofeedback level (adaptive difficulty / companion). Open: exactly
  what the 2nd car represents per mode, how its controller plugs in (remote-user
  network vs ML-Agent), and the ML-Agents package + training pipeline. **Hard
  constraint:** the 2nd car must NEVER drive the feedback signal — sham, one-clock
  and INS integrity apply only to the shared car; the agent is downstream scenery.
  Not yet built; recorded so the scaffold can grow a pluggable second-car slot.
  Owner: TBD.

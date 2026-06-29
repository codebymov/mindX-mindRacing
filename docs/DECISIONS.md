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

## Open

- **O2 — Transport to Unity: LSL outlet vs websocket.** LSL keeps one clock and
  fits the existing fabric; websocket is simpler on the Unity side but needs
  explicit time handling. Abstracted behind `api.FeedbackSink` so either works.
- **O3 — INS windowing trade-off.** Longer window = more stable coherence but
  more feedback latency / slower responsiveness; shorter = jumpier but snappier.
  Tune against pilot data; the estimator exposes `window_s` / `update_every_s`.
- **O4 — Exact INS estimator.** Welch-coherence baseline is in; whether to move
  to true Morlet wavelet coherence (and which scales) depends on pilot stability.
- **O5 — Multiplayer scene sync for the shared MR view.** Both headsets must show
  the *same* shared car/track at the same physical position (see D7). Photon
  (already in the project) vs alternatives. Owner: VCI (multiuser VR expertise).
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

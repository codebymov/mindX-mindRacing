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

## Open

- **O1 — Final XR device.** Candidates: Apple Vision Pro, Meta Quest Pro,
  Microsoft HoloLens 2. Drivers: pass-through quality, eye/face/body tracking,
  comfort for ages 16–21, SDK/Unity integration, cost. Owner: AVMZ + VCI.
- **O2 — Transport to Unity: LSL outlet vs websocket.** LSL keeps one clock and
  fits the existing fabric; websocket is simpler on the Unity side but needs
  explicit time handling. Abstracted behind `api.FeedbackSink` so either works.
- **O3 — INS windowing trade-off.** Longer window = more stable coherence but
  more feedback latency / slower responsiveness; shorter = jumpier but snappier.
  Tune against pilot data; the estimator exposes `window_s` / `update_every_s`.
- **O4 — Exact INS estimator.** Welch-coherence baseline is in; whether to move
  to true Morlet wavelet coherence (and which scales) depends on pilot stability.
- **O5 — Multiplayer scene sync (Photon vs alternatives) for the shared MR view.**
  Owner: VCI (multiuser VR expertise).

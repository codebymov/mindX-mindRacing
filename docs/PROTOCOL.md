# Protocol, Compliance & Safety

Engineering-facing summary of the experimental protocol and the standards the
software must uphold. Source of truth for the science is the project outline;
this file translates it into constraints on the code.

## Participants
- 36 same-sex, unrelated dyads (72 individuals), aged 16–21.
- Healthy; severe neurological/psychiatric disorders excluded (proof-of-concept).
- Consent/assent obtained before participation. No PII in code, logs, or
  artifacts — pseudonymized `sub-NN` / `dyad-NN` only.

## Session structure (per the study design, Fig. 2 of the outline)
- Three sessions per dyad on three different days within one week.
- Each session: a longer **baseline** resting block (task-free movie), then
  alternating **task** (with feedback) and **rest** blocks.
- One of the three sessions (randomized per dyad, decided at enrollment) is
  **fully sham**.
- A screen-based **transfer task** (exchange game) is run before session 1 and
  after session 3.
- Hard cap: a training session is restricted to ~30 minutes (fNIRS-cap and
  XR-exposure comfort). Enforced in `session/protocol.py`; sessions must be
  abortable at any time.

## Signal chain requirements
- Two NIRSport2 systems; probe optimized for PFC + rTPJ; short channels for
  physiological-noise regression; camera-based channel registration.
- Aux: ECG/EDA (movisens), accelerometer; XR device with pass-through + cameras.
- Online preprocessing must be **causal** (no future samples, no zero-phase).
- INS = a continuous joint feature across both subjects (wavelet coherence).

## Standards to comply with
- **BIDS** for neural data layout.
- **fNIRS best-practice** reporting (Yücel et al.).
- **CRED-nf** checklist for neurofeedback study reporting (Ros et al.).
- Code-versioning, unit testing, reproducible containerized environments.
- Reproducibility: every run reconstructable from config + raw LSL recording +
  git SHA. Stamp provenance on all artifacts.

## Safety notes that translate to code
- Time-limit enforcement and instant abort are not optional features; they are
  participant-safety mechanisms. Treat regressions here as critical.
- Sham must remain perceptually identical to real (experimental validity).
- Degrade gracefully: if persistence or the game link fails mid-session, the
  acquisition/feedback loop should continue or stop cleanly — never hang.

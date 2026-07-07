# Scope: O5 — Multiplayer scene sync + physical co-location (shared MR view)

**Goal.** Both participants (P1, P2), in the SAME room, wearing possibly-different
headsets (HTC Vive / Quest Pro / Varjo XR-4, per D6), see the SAME shared car on
the SAME physical spot — each from their own player viewpoint — and see each
other (head/hands). The car is driven by the joint INS signal (D7/D8) arriving
over LSL (D9). Owner: VCI (multiuser VR).

This is genuinely two problems that are usually conflated:
1. **Co-location** — make both headsets agree on one real-world origin.
2. **Scene sync** — replicate the shared car + avatars between the two headsets.

Findings below are from a 2026 review (see "Sources"). Cost is a non-factor at
2 concurrent users; the real axis is **cloud dependency vs. self-hosted LAN
determinism** — and for a reproducible, PII-sensitive neuro lab, that points hard
toward self-hosted.

## 1. Co-location — the constraint that decides the design

**Cross-vendor cloud co-location does NOT exist in 2026.**
- Meta Shared Spatial Anchors / Colocation are **Quest-only and cloud-gated**
  (upload point cloud to Meta servers; require a Meta account + Enhanced Spatial
  Services). A Quest Pro cannot share an anchor with a Vive or Varjo.
- OpenXR anchor extensions (`XR_FB_*`, `XR_MSFT_*`, `XR_HTC_anchor`, `XR_EXT_*
  spatial entities` ratified 2025, Varjo Base 4.16) standardize the **API**, but
  an anchor is an opaque handle into one runtime's private SLAM map — there is
  **no cross-runtime anchor interchange format**. Persistence means "same device,
  later session," not "different vendor's device."
- Camera/QR (Meta MRUK QR, Passthrough Camera API) is **Quest-3-class only**;
  Quest Pro is not supported and Vive/Varjo have no vendor-neutral camera-frame
  OpenXR extension. AR Foundation image tracking is phone-backend (ARKit/ARCore),
  not the HMD OpenXR path.

**⇒ The only method that works across all three D6 headsets is deterministic
manual origin registration** using tracked controllers: at session start, both
users point a controller at the same one or two known physical fiducials (e.g. a
marked point on the racing table); each headset inverts those poses to a shared
origin transform. Universal (needs only OpenXR controller tracking), fully
reproducible, no cloud, no Meta account, no PII. ~cm precision; a short
per-session calibration ritual — trivial for a seated, stationary dyad. A GI VR/AR
Workshop 2025 paper backs *one-shot* registration (not continuous fiducials,
which drift/occlude under motion) — exactly right for D7's stationary shared car.

**This dovetails with D7's "track-local space".** The registered shared origin IS
the track-local root: all gameplay already lives in track-local space, so once
both headsets share that root, the car/track render at the same physical place by
construction. Co-location = establishing the D7 track root on both headsets.

## 2. Scene sync — self-hosted LAN, not cloud relay

| Option | License / hosting | Why / why not for this lab |
|---|---|---|
| **Ubiq** (UCL) | Apache-2.0, **self-hostable**, no third-party services | **Recommended.** Research-grade (ACM VRST 2021), explicitly "GDPR-safe for experiments," rooms/avatars/voice, multiple sync models. Best fit for reproducibility + PII rules. |
| **Mirror** | MIT, free, **self-hostable** | **Recommended (simpler).** Snapshot interpolation ("perfectly smooth"), no-GC hot path, listen-server on the lab PC. You write the VR-rig smoothing. Huge community. |
| **Photon Fusion 2** | Cloud relay (Shared/Host); dedicated server option | What the project used before (PUN2, now **legacy — don't start new**). Fusion 2 has the best turnkey XR samples ("Fusion VR Shared" maps cleanly onto one shared car), but Shared/Host route through **Photon Cloud relay** → uncontrolled latency into a soft-real-time loop + cloud dependency that undermines reproducibility. Acceptable only if the relay dependency is accepted. |
| **Normcore** | Cloud-only (hosted rooms) | Smoothest VR out-of-the-box + built-in voice, but **cloud-only external dependency** — rejected on the same reproducibility/PII grounds. |
| **Unity NGO** | Free, server-auth / distributed-authority | Viable + first-party, but Relay/Lobby are paid PaaS and it's less VR-turnkey than Ubiq/Mirror. |

**Recommendation: Ubiq (research/GDPR fit) or Mirror (simplicity), self-hosted on
a lab machine on the same offline LAN as the LSL streams.** Both avoid the
cloud-relay dependency of Normcore and Fusion Shared/Host.

## 3. Proposed architecture

```
  Lab LAN (offline, no cloud) — one clock of record
  ┌───────────────────────────────────────────────────────────────┐
  │  backend (Python)  ──LSL "mindx_feedback"──►  Lab-host (Unity)  │
  │                                               = scene AUTHORITY │
  │                                               owns the car(s)   │
  │                                                 │  netcode       │
  │                                    ┌────────────┴───────────┐    │
  │                                 P1 headset               P2 headset
  │                              (own XR rig/cam)          (own XR rig/cam)
  │                              renders shared car        renders shared car
  │                              + P2 avatar               + P1 avatar
  └───────────────────────────────────────────────────────────────┘
   Shared origin = D7 track root, set once per session by manual controller
   registration on BOTH headsets.
```

- **Authority.** The **lab-host** process is the scene authority. It is the LSL
  consumer (via `LslFeedbackTransport` / a headless bridge): it receives INS,
  drives the authoritative car transform, and the netcode replicates it to both
  headset clients. This keeps the science signal single-authoritative and the two
  headsets as pure renderers — no client can perturb the car.
  - Hyperscanning (D7/D8): one shared car, host-owned, both clients render it.
  - Individual mode (D8): two cars; still host-owned (routed by `subjectIndex`),
    or per-player ownership if a player also *steers* (ICarInput). Keep the
    INS/NF-driven axis (speed) host-authoritative regardless — a car must never be
    driven by a client-side/non-causal value (D8 hard rule).
- **Transports stay separate (important).** INS/feedback over **LSL** (one clock,
  bounded latency, recordable into the same XDF); car/avatar **state over the
  self-hosted netcode**. LSL is a data-stream transport, NOT a state/authority
  layer — do not try to sync game state over LSL.
- **Avatars.** Networked head + two hands per player (hand tracking already
  imported: XR Hands HandVisualizer sample) so each participant sees the other —
  part of "various views ... of the same game."
- **Reproducibility.** Everything on the offline lab LAN; the shared-origin
  registration transform is stamped into the run artifacts (like config + git
  SHA) so a session's spatial frame is reconstructable.

## 4. Decisions & open points

- **D11 (proposed) — Co-location = deterministic manual controller registration.**
  Forced by D6 (cross-vendor) + the 2026 state of anchors; also the most
  reproducible. Establishes the D7 track root on both headsets.
- **O5 sub-decision (needs VCI) — netcode library.** Ubiq vs Mirror vs Photon
  Fusion 2. Recommendation: self-hosted (Ubiq or Mirror). Photon only if the
  cloud-relay dependency is explicitly accepted.
- **Still open:** avatar fidelity (head+hands vs full body), whether P1/P2 also
  get an ICarInput steering role (D8/O6) or are pure NF passengers, and where the
  lab-host runs (dedicated PC vs one of the headsets as listen-server — dedicated
  PC preferred for authority isolation).

## Sources
Photon Fusion 2 (v2.0.12, Mar 2026) topologies & VR Shared sample; PUN2 legacy
status; Unity NGO v2.13 distributed authority; Normcore ownership/pricing; Mirror
v96 (MIT); Coherence pricing; **Ubiq** (UCL, Apache-2.0, VRST 2021); Meta Shared
Spatial Anchors & Colocation Discovery (Quest-only, cloud); Khronos OpenXR Spatial
Entities (2025) & Varjo Base 4.16; Meta MRUK QR / Passthrough Camera API
(Quest-3-only); GI VR/AR Workshop 2025 (arXiv 2509.06582) on one-shot marker
registration; LSL (Imaging Neuroscience 2025) as a data-stream (not state) layer.

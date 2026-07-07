# O5 shared MR view: Ubiq setup recipe

How the two headsets see the SAME shared car at the SAME physical spot, each from
their own viewpoint (decisions **D12** netcode = Ubiq, **D11** co-location =
manual controller registration, **D7** track-local space).

```
        backend (Python)
            │  LSL "mindx_feedback"  (INS signal, one clock of record)
            ▼
   ┌──────────────────────┐        Ubiq (self-hosted, lab LAN)
   │  LAB-HOST (Unity)     │  ── car transform + level ──►  ┌───────────────┐
   │  = scene AUTHORITY    │                                │ P1 headset    │
   │  UbiqSharedCarNetwork │  ◄── avatars (head+hands) ───► │ (own XR view) │
   │  (isAuthority = true) │                                └───────────────┘
   │  SharedCarAuthority   │  ── car transform + level ──►  ┌───────────────┐
   │  (LSL inlet -> car)   │                                │ P2 headset    │
   └──────────────────────┘  ◄── avatars ───────────────►  │ (own XR view) │
                                                            └───────────────┘
   Shared origin (= D7 track root) set on each headset by ColocationRegistration.
```

## Roles

- **Lab-host** — a Unity process on a lab PC (not a headset). It is the *only* LSL
  consumer and the scene authority: `SharedCarAuthority` reads the INS level and
  advances the car; `UbiqSharedCarNetwork` (`isAuthority = true`) replicates it.
  Isolating authority on the host means neither participant's client can perturb
  the science-critical car.
- **P1 / P2 headsets** — Ubiq clients. They render the replicated car under their
  own co-located track root and show each other's avatars. No LSL, no car physics.

## 1. Install Ubiq (one-time, in the Unity Editor)

Not committed to `manifest.json` (a bad package URL breaks resolution for
everyone — same policy as LSL4Unity):

1. **Window ▸ Package Manager ▸ + ▸ Add package from git URL…**
   `https://github.com/UCL-VR/ubiq.git?path=/Unity/Assets/Runtime` *(confirm the
   current UPM path/branch on the Ubiq repo — the layout has moved between
   releases).* Ubiq exposes the `Ubiq.Messaging` namespace used by
   `UbiqSharedCarNetwork.cs`.
2. Ubiq needs a **room server**. For a lab, run the Node.js server **on the lab
   PC / LAN** (Ubiq ships it under `Node/`): `npm install && node server.js`.
   Point the scene's `NetworkScene` config at that LAN address — **no cloud**.
3. Add a Ubiq `NetworkScene` + `RoomClient` to the scene; all three peers join the
   same room name.

## 2. Wire the scene

On the **shared car** GameObject (a child of the track root, in track-local space):
- `UbiqSharedCarNetwork` — set `isAuthority = true` **only in the lab-host build/
  scene**; leave it false on the headset clients.
- `SharedCarAuthority` — set `trackRoot`, `car`, optional `engine` AudioSource,
  `streamName = mindx_feedback`, and `carSubjectIndex` (-1 for the shared
  Hyperscanning car; 0/1 for Individual-mode per-player cars).

On **each headset rig**:
- `ColocationRegistration` — set `trackRoot`. At session start the operator marks
  the physical origin + a forward point with the controller trigger; the track
  root snaps to the shared origin. Do this on **both** headsets against the **same
  physical marks**.
- Ubiq avatar prefab (from the Ubiq samples) so each player sees the other.

## 3. Run order

1. Start the Ubiq room server on the lab LAN.
2. Start the backend: `python -m mindx_hnf.scripts.simulate --lsl` (or a live
   session). The lab-host's `SharedCarAuthority` connects to the LSL stream.
3. Launch the lab-host Unity process (authority) — it joins the room and starts
   driving + replicating the car.
4. Launch both headset clients — they join the room, register co-location, and
   render the shared car + avatars.

## What this gives — and the seams that keep it swappable

- ✅ One INS-driven car, authored on the host, seen identically by both players at
  the same physical spot, each from their own view; avatars for mutual presence.
- ✅ Everything on the offline lab LAN (Ubiq + LSL) → reproducible, no PII/cloud.
- 🔌 The netcode lives entirely behind `ISharedCarNetwork` (`SharedCarState`), so
  swapping Ubiq for Mirror (the recorded fallback) is one new adapter, no changes
  to `SharedCarAuthority` or the game logic.

## Status / not-yet

- `UbiqSharedCarNetwork.cs` needs the Ubiq package to compile (step 1) — this is
  scaffolding pending an in-editor build + verification pass, like the LSL4Unity
  transport was.
- Avatar prefab wiring, the calibration UI/prompts for `ColocationRegistration`,
  and spawning the car via Ubiq's `NetworkSpawner` (so the `NetworkId` matches
  across peers) are the next O5 steps.

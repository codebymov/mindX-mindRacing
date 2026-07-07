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

### The shared car — spawned, not scene-placed
So all three peers get an instance with a **matching NetworkId**, the car is
**spawned via Ubiq**, not placed in the scene:
1. Make a **car prefab** whose root has `UbiqSharedCarNetwork` (implements
   `INetworkSpawnable`) + `SharedCarAuthority`, plus the car body/audio as
   children. Set on `SharedCarAuthority`: `trackRoot`, `car`, optional `engine`
   AudioSource, `streamName = mindx_feedback`, and `carSubjectIndex` (-1 = shared
   Hyperscanning car; 0/1 = Individual-mode per-player cars).
2. Register that prefab in the **`NetworkScene`'s `PrefabCatalogue`**.
3. Put a **`SharedCarSpawner`** in the scene, assign the car prefab, and set
   `spawnAsAuthority = true` **only in the lab-host scene/build**. On Start the
   host spawns the car room-scoped and promotes its own instance to authority;
   clients receive the instance as renderers (`isAuthority = false`).

### Each headset rig — co-location + avatar
- `ColocationRegistration` — set `trackRoot`. At session start the operator marks
  the physical origin + a forward point with the controller trigger; the track
  root snaps to the shared origin. Do this on **both** headsets against the **same
  physical marks**. Add `CalibrationUIController` (+ a world-space Canvas Text/TMP
  bound to its `PromptChanged`) to guide the two steps on screen.
- **Avatar (mutual presence).** Add Ubiq's **`AvatarManager`** and set its local
  avatar prefab to a **three-point (head + two hands)** avatar
  (`ThreePointTrackedAvatar`, from the Ubiq XR samples). Ubiq drives it from the
  local rig's HMD + controller poses and replicates it, so each player sees the
  other's head and hands — enough to point at the shared car. (Full-body IK is a
  later upgrade; head+hands is the recommended default for a seated dyad — see
  DECISIONS O5.)

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

Done (code): the seam (`ISharedCarNetwork`), Ubiq adapter
(`UbiqSharedCarNetwork`), host↔client glue (`SharedCarAuthority`), room-scoped
spawn (`SharedCarSpawner`), co-location (`ColocationRegistration`) with step
events, and the calibration prompts (`CalibrationUIController`).

Still manual / next:
- **Install the Ubiq package + run the room server + in-editor compile/verify**
  (step 1). The Ubiq-dependent scripts (`UbiqSharedCarNetwork`,
  `SharedCarSpawner`) only compile once the package is present — scaffolding
  pending an Editor build pass, like the LSL4Unity transport was.
- Build the **car prefab** + register it in the `PrefabCatalogue`.
- Add the **`AvatarManager`** + a three-point avatar prefab, and a world-space
  Canvas bound to `CalibrationUIController.PromptChanged`.
- Confirm the exact **Ubiq UPM path** for the current release.

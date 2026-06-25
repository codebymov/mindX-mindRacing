# XR Setup — OpenXR multi-device build recipe

Supersedes `QUEST2_SETUP.md`. This reflects the kickoff decisions recorded in
`docs/DECISIONS.md` **D6** (OpenXR baseline; HTC Vive / Quest Pro / Varjo XR-4)
and **D7** (one shared dyadic car, track-local space). Read the root `CLAUDE.md`
first — the LSL-clock, two-track, and sham-integrity rules still bind the game.

Main scene: **`Assets/Scenes/MindXRacing.unity`**
Track + cars reference: **`Assets/Scenes/_Reference/PhotonConnection.unity`**

---

## 0. What changed from the old Quest-2 recipe

| Old (`QUEST2_SETUP.md`) | Now (this doc) |
|---|---|
| Meta Quest 2, Meta OpenXR + MR-Template AR rig | **OpenXR only**, one code path for Vive / Quest Pro / Varjo XR-4 |
| Two cars (Blue=P1, Red=P2), Photon competitive race | **One shared car** both influence via joint INS (cooperative) |
| Track copied into world space at `(0,0,5)` | Everything under a **track-local `TrackRoot`**, decoupled from the anchor |

**Hard rule:** build against **OpenXR core + extensions**, never vendor SDKs
(SRanipal, Meta SDK, Varjo SDK). Vendor APIs are an optional later add-on for
richer data (e.g. pupil diameter), never the baseline. One code path serves all
three headsets.

---

## 1. Runtimes & build targets

| Headset | Runtime | Unity build target |
|---|---|---|
| HTC Vive (eye tracking) | SteamVR OpenXR | Standalone (Windows) |
| Meta Quest Pro (eye tracking) | Meta OpenXR (standalone) or Link | Android (standalone) and/or Standalone via Link |
| Varjo XR-4 | Varjo OpenXR | Standalone (Windows) |

Two physical build configs: **Standalone/Windows** (Vive, Varjo, Quest-Link) and
**Android** (Quest Pro on-device). Same scripts, same scene.

---

## 2. Project Settings — OpenXR

> **Status (already applied in this repo):** OpenXR is the active loader on both
> Standalone and Android. Enabled interaction profiles — Standalone: HTC Vive,
> Valve Index, KHR Simple (generic/Varjo fallback), Meta Quest Touch Pro, Oculus
> Touch, + Eye Gaze. Android: Meta Quest Touch Pro, Oculus Touch, + Eye Gaze.
> Player settings already correct (Standalone IL2CPP/.NET Standard 2.1; Android
> IL2CPP/ARM64/minSDK 29). The steps below document how to reproduce/extend it.

**Edit → Project Settings → XR Plug-in Management**
- Enable **OpenXR** on **both** the *PC/Standalone* and *Android* tabs.
- Remove any vendor-loader (Oculus, etc.) — OpenXR only.

**XR Plug-in Management → OpenXR** (do this per tab):
- **Interaction profiles** — add all that apply so one build runs everywhere:
  - *HTC Vive Controller Profile*
  - *Oculus Touch Controller Profile* (Quest Pro)
  - *Varjo* uses the standard profiles + its OpenXR runtime
  - *Eye Gaze Interaction Profile*  ← enables eye tracking via OpenXR
- **OpenXR Features** — enable **Eye Gaze Interaction** (`XR_EXT_eye_gaze_interaction`).
  This is the *only* eye-tracking path in the baseline. Do **not** add SRanipal /
  Meta / Varjo eye SDKs here.

**Player settings**
- Standalone: API compat **.NET Standard 2.1**.
- Android (Quest Pro): Min API **29+**, Scripting backend **IL2CPP**, target
  arch **ARM64**, remove other architectures.

---

## 3. Scene architecture (D7: shared car, track-local)

Build `MindXRacing` to this shape. The point is that **placement** (where the
`TrackRoot` anchor lands on the real table) and **gameplay** (car physics, INS →
speed) are decoupled: all gameplay math stays in `TrackRoot`-local coordinates.

```
MindXRacing
├── XR Origin (OpenXR)          ← camera + controllers + eye gaze; NO standalone Main Camera
├── Directional Light
├── TrackRoot                   ← the single anchorable root; move THIS to place the world
│   ├── CircularMap             ← BEDRILL track, copied from _Reference (track-local at origin)
│   │   └── Prefabs_Obs/...     ← track pieces with colliders
│   ├── TrackBoundaries         ← BEDRILL fence prefabs
│   └── SharedCar               ← ONE car (cosmetic = a Free Racing Car variant)
│       ├── Rigidbody           ← Collision Detection = Continuous Speculative (already set on base prefab)
│       └── FeedbackReceiver    ← drives this car from INS `level`; set its `car` ref to SharedCar
└── UI                          ← world-space HUD for sync score (later)
```

### Bringing the track in (track-local)
1. Open `_Reference/PhotonConnection.unity` in a second tab.
2. Copy **`CircularMap`** → paste under **`TrackRoot`** in `MindXRacing`.
3. Zero `CircularMap`'s local transform so it sits at `TrackRoot` origin. Place
   the whole world later by moving **`TrackRoot`** only.
4. Add fence prefabs from `Assets/BEDRILL/Modular_Track_Free/Prefabs_Obs/` under
   `TrackBoundaries`.

### The one shared car
- Use a single `Free Racing Car *.prefab` instance as `SharedCar`. The colored
  variants are cosmetics now — there is no per-player car.
- Add the **`FeedbackReceiver`** component (or put it on a child) and assign its
  `car` field to `SharedCar`. INS `level` → speed/pitch (see
  `Assets/Scripts/FeedbackReceiver.cs` and `backend/.../contracts.py`).
- **Do not** branch on `sample.mode` (sham vs real) anywhere perceptible.

---

## 4. Feedback transport (O2, still open)

`FeedbackReceiver` takes an `IFeedbackTransport`. The LSL-outlet vs websocket
decision (`docs/DECISIONS.md` O2) is abstracted behind that interface — wire up
whichever is chosen without touching gameplay. Until then the receiver runs with
a null/stub transport.

---

## 5. Shared view across two headsets (O5, later)

Both participants must see the *same* `SharedCar` at the *same physical spot*.
That needs (a) a shared spatial anchor so each headset places `TrackRoot`
identically in the room, and (b) state sync of `SharedCar`'s track-local pose.
Photon is already in the project; the transport choice is open (O5). This is a
later milestone — single-headset playable comes first.

---

## 6. Still-useful mechanical references

The vendor-neutral bits of the old `QUEST2_SETUP.md` (Build Settings scene list,
URP material conversion for pink materials, regenerating the VS solution) still
apply; only the device/rig/two-car parts are superseded by this doc.

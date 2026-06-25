# MindX — Keep / Delete Reference

Clean project created from `whichOne\mindX-mindRacing` (GitHub: `codebymov/mindX-mindRacing`).

**Before:** 2,826 files  
**After:** ~1,660 files (~41% reduction)

---

## KEPT (in `C:\Users\sukha\MindX\unity`)

### Root
| Path | Purpose |
|------|---------|
| `ProjectSettings/` | Unity project config (Unity **2022.3.5f1**) |
| `Packages/` | URP, XR, Input System, OpenXR, Meta OpenXR |
| `.gitignore` | Standard Unity ignore (Library, Temp, .sln, etc.) |
| `.vsconfig` | Visual Studio package recommendations |

### Assets — Game content
| Path | Purpose |
|------|---------|
| `Assets/BEDRILL/Modular_Track_Free/` | Racing track models, materials, **`Prefabs_Obs/`** (colliders) |
| `Assets/CarControll/CarController.cs` | Car movement script (rewrite for XR + Photon) |
| `Assets/CarControll/Prefabs (With Colliders)/` | **Use these** car prefabs (2 color variants for 2 players) |
| `Assets/CarControll/Prefabs (Meshes Only)/` | Visual-only car variants (optional) |
| `Assets/CarControll/Meshes/ARCADE - FREE Racing Car.fbx` | Car mesh |
| `Assets/CarControll/Materials/` | Car materials |
| `Assets/CarControll/Textures/` | Car textures |
| `Assets/CarControll/Skybox/` | Day/night skyboxes |
| `Assets/PhotonManager.cs` | Photon lobby/room bootstrap |

### Assets — Networking (core SDK only)
| Path | Purpose |
|------|---------|
| `Assets/Photon/PhotonUnityNetworking/` | PUN runtime + editor (no Demos) |
| `Assets/Photon/PhotonRealtime/` | Photon realtime API (no Demos) |
| `Assets/Photon/PhotonLibs/` | Native / WebSocket libs |

### Assets — XR / MR foundation
| Path | Purpose |
|------|---------|
| `Assets/MRTemplateAssets/` | MR Interaction Setup, controllers, UI, scripts, shaders |
| `Assets/XR/` | OpenXR loaders, Quest/Oculus settings |
| `Assets/XRI/` | XR Interaction Toolkit layer settings |
| `Assets/Settings/` | URP renderer + input settings |

### Assets — UI & scenes
| Path | Purpose |
|------|---------|
| `Assets/TextMesh Pro/` | Text rendering |
| `Assets/Scenes/MindXRacing.unity` | **Main scene** (MR template base — add track here) |
| `Assets/Scenes/_Reference/PhotonConnection.unity` | Desktop 2-player reference (copy track layout from here) |

---

## DELETED (not copied into MindX)

| Path (was in GitHub clone) | Reason |
|----------------------------|--------|
| `first-try_BackUpThisFolder_ButDontShipItWithYourGame/` | IL2CPP build dump (~100MB+ bloat) |
| `Assets/Samples/` | XR Interaction Toolkit sample scenes |
| `Assets/Photon/PhotonUnityNetworking/Demos/` | Asteroids, SlotRacer, PunBasics, etc. |
| `Assets/Photon/PhotonRealtime/Demos/` | Load-balancing demo |
| `Assets/Photon/PhotonChat/` | Not used by this project |
| `Assets/MRTemplateAssets/Tutorial/` | Onboarding tutorial assets |
| `Assets/MRTemplateAssets/Videos/` | Onboarding video |
| `Assets/CarControll/Scenes/` | Old keyboard-only car demo |
| `Assets/BEDRILL/.../Example.unity` | Vendor track demo scene |
| `Assets/CarControll/Meshes/Road.fbx` | Superseded by BEDRILL modular track |
| `.plastic/` | Plastic SCM metadata (use Git instead) |
| `ignore.conf` | Plastic SCM config |

---

## OPTIONAL — delete later in Unity (safe once XR scene works)

| Path | When to remove |
|------|----------------|
| `Assets/CarControll/Car Controll.prefab` | After you spawn cars from `Prefabs (With Colliders)` + attach `CarController` |
| `Assets/CarControll/Prefabs (Meshes Only)/` | If you only use collider prefabs |
| `Assets/Scenes/_Reference/` | After track is rebuilt in `MindXRacing.unity` |
| `Assets/MRTemplateAssets/Prefabs/Totem*.prefab` | MR template demo objects |
| `Assets/MRTemplateAssets/Prefabs/Blaster/` | MR template toy gun demo |

---

## NOT USED — sibling folders in `whichOne`

| Folder | Status |
|--------|--------|
| `whichOne\mindX` | Plastic skeleton only (31 files) — ignore |
| `whichOne\MindRacing` | Plastic skeleton only — ignore |
| `whichOne\MindRacingGame` | Plastic skeleton only — ignore |
| `whichOne\mindX-mindRacing` | Original clone — keep as archive or delete manually |

---

## Custom C# you will write next (in `Assets/Scripts/`)

Create this folder in Unity and open in Visual Studio:

- `XRCarController.cs` — thumbstick / trigger driving for Quest controllers
- `PhotonCarSpawner.cs` — network-instantiate cars per player
- `NeurofeedbackLSL.cs` — LSL4Unity stream reader (add package later)
- `RaceHUD.cs` — world-space UI for sync score / speed

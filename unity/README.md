# MindX

XR cooperative mind-racing game — OpenXR, targeting HTC Vive / Meta Quest Pro /
Varjo XR-4. Cleaned from `codebymov/mindX-mindRacing`. One shared car driven by
the dyad's joint neural synchrony (see `docs/DECISIONS.md` D6, D7).

## Quick start

1. Open **`C:\Users\sukha\MindX\unity`** in Unity Hub (2022.3.5f1).
2. Open scene **`Assets/Scenes/MindXRacing.unity`**.
3. Follow **`XR_SETUP.md`** for the OpenXR multi-device build + scene architecture.
   (`QUEST2_SETUP.md` is superseded — kept only for vendor-neutral mechanical steps.)
4. See **`KEEP_DELETE.md`** for what was kept vs removed.

## Visual Studio

After opening in Unity once: **Assets → Open C# Project** → edit scripts in `Assets/Scripts/`.

## Scenes

| Scene | Purpose |
|-------|---------|
| `Scenes/MindXRacing.unity` | **Main** — MR/XR base (build this) |
| `Scenes/_Reference/PhotonConnection.unity` | Desktop 2-player reference (copy `CircularMap` from here) |

## Custom scripts

| Script | Location |
|--------|----------|
| `PhotonManager.cs` | `Assets/` — networking bootstrap |
| `CarController.cs` | `Assets/CarControll/` — keyboard prototype (replace for Quest) |
| `XRCarController.cs` | `Assets/Scripts/` — Quest thumbstick driving (starter) |

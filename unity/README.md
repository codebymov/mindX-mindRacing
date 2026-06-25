# MindX

XR cooperative mind-racing game for Meta Quest 2 — cleaned from `codebymov/mindX-mindRacing`.

## Quick start

1. Open **`C:\Users\sukha\MindX\unity`** in Unity Hub (2022.3.5f1).
2. Open scene **`Assets/Scenes/MindXRacing.unity`**.
3. Follow **`QUEST2_SETUP.md`** to merge the BEDRILL track and configure Quest 2.
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

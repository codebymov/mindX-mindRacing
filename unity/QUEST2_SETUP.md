# Quest 2 Setup — Merge BEDRILL Track into XR Scene

Main scene: **`Assets/Scenes/MindXRacing.unity`**  
Reference layout: **`Assets/Scenes/_Reference/PhotonConnection.unity`**

---

## Part 1 — Open project in Unity

1. Install **Unity Hub** + **Unity 2022.3.5f1** (or 2022.3 LTS).
2. **Add** project → select `C:\Users\sukha\MindX\unity`.
3. Wait for package import (URP, XR, OpenXR, Meta OpenXR).
4. Open `Assets/Scenes/MindXRacing.unity`.

---

## Part 2 — Configure Quest 2 / OpenXR

1. **Edit → Project Settings → XR Plug-in Management**
   - **Android** tab: enable **OpenXR**
   - **Standalone** tab: enable **OpenXR** (for Link / desktop testing)

2. **Edit → Project Settings → XR Plug-in Management → OpenXR**
   - Android: enable **Meta Quest Touch Controller Profile**
   - Add interaction profile: **Oculus Touch Controller Profile**

3. **Edit → Project Settings → Player → Android**
   - Minimum API Level: **29** or higher
   - Scripting Backend: **IL2CPP**
   - Target Architectures: **ARM64** only
   - Graphics APIs: remove Vulkan if Quest build fails (try OpenGLES3)

4. **Edit → Project Settings → Quality**
   - Use **Performant** URP preset for Quest builds (`Assets/Settings/Project Configuration/`)

---

## Part 3 — Merge BEDRILL track into MindXRacing (step-by-step)

### Step 1 — Open both scenes

1. Open `MindXRacing.unity` (double-click).
2. Open `_Reference/PhotonConnection.unity` in a second tab (double-click).

### Step 2 — Copy the track hierarchy

In **PhotonConnection**:

1. In Hierarchy, find **`CircularMap`** (parent of all BEDRILL track pieces).
2. Right-click **`CircularMap` → Copy**.
3. Switch to **MindXRacing** tab.
4. Right-click Hierarchy root → **Paste**.

### Step 3 — Position track for XR

1. Select **`CircularMap`**.
2. Set Transform:
   - Position: `(0, 0, 5)` — place track slightly ahead of spawn
   - Rotation: `(0, 0, 0)`
   - Scale: `(1, 1, 1)`
3. Adjust Y so track surface is at **y = 0** (use Scene view).

### Step 4 — Add track boundaries (replace cubes)

Instead of primitive cubes from the reference scene:

1. From Project window: `Assets/BEDRILL/Modular_Track_Free/Prefabs_Obs/`
2. Drag fence prefabs around the outer edge:
   - `Track_Fence_line_type_01_15m_free_obs`
   - `Track_Fence_line_type_01_red_block_1&5m_free_obs`
3. Parent fences under a new empty GameObject: **`TrackBoundaries`**.

### Step 5 — Add Photon networking

1. Create empty GameObject: **`NetworkManager`**
2. **Add Component → PhotonManager** (existing script at `Assets/PhotonManager.cs`)
3. Configure Photon App ID:
   - Open `Assets/Photon/PhotonUnityNetworking/Resources/PhotonServerSettings.asset`
   - Paste your App ID from [dashboard.photonengine.com](https://dashboard.photonengine.com)

### Step 6 — Place two cars (replace old Car Controll prefab)

Do **not** use `Car Controll.prefab` (desktop camera bundle).

1. Create empty: **`Cars`**
2. Drag from `Assets/CarControll/Prefabs (With Colliders)/`:
   - `Free Racing Car Blue Variant.prefab` → rename **`Car_Player1`**
   - `Free Racing Car Red Variant.prefab` → rename **`Car_Player2`**
3. Add **`CarController`** component to each (or new `XRCarController` once written).
4. Ensure each has **Rigidbody** + collider (prefab includes these).
5. Place on opposite sides of the start/finish straight.
6. Disable **`Car_Player2`** until Photon spawns remote player.

### Step 7 — XR player rig (already in MindXRacing)

`MindXRacing` is based on the MR Template. Confirm Hierarchy contains:

- **`XR Origin`** or **`MRInteractionSetup`** prefab instance
- Left / Right controller objects under it

If missing:

1. Delete any standalone **Main Camera** (XR Origin has its own).
2. Drag `Assets/MRTemplateAssets/Prefabs/MRInteractionSetup.prefab` into scene.
3. Position XR Origin at track edge: `(0, 1.6, -10)` facing the track.

### Step 8 — Driving from Quest controllers (next code task)

`CarController.cs` uses keyboard (`WASD`). For Quest 2, create `Assets/Scripts/XRCarController.cs`:

- Read **left thumbstick** via Input System (`XRController` / `ActionBasedController`)
- Forward = stick Y → acceleration
- Turn = stick X → rotation
- Attach to car; disable `CarController` on same object

### Step 9 — Save and set build scene

1. **File → Save** (`MindXRacing.unity`)
2. **File → Build Settings**
3. Confirm only **`MindXRacing`** is checked (already set in `EditorBuildSettings`)
4. Platform: **Android** → **Switch Platform** (first time takes several minutes)

### Step 10 — Build to Quest 2

1. Enable **Developer Mode** on Quest (Meta phone app).
2. Connect Quest via USB.
3. **File → Build Settings → Build And Run**
4. Or build APK, then `adb install`.

---

## Part 4 — Open in Visual Studio

1. **Edit → Preferences → External Tools**
   - External Script Editor: **Visual Studio 2022**
   - Check **Generate .csproj files for:** Embedded packages, Local packages, Registry packages

2. **Edit → Project Settings → Player → Other Settings**
   - Api Compatibility Level: **.NET Standard 2.1**

3. In Unity: **Assets → Open C# Project**  
   This generates `MindX.sln` and opens Visual Studio.

4. Create folder `Assets/Scripts/` in Unity Project window.
5. Add scripts there — they appear in the **Assembly-CSharp** project in VS.

6. Install VS workload: **Game development with Unity** (Visual Studio Installer).

---

## Part 5 — Recommended scene hierarchy (final)

```
MindXRacing
├── MRInteractionSetup (XR Origin + controllers)
├── Directional Light
├── NetworkManager          ← PhotonManager.cs
├── CircularMap             ← BEDRILL track (from reference scene)
│   ├── Track straights / corners (Prefabs_Obs)
│   └── ...
├── TrackBoundaries         ← Fence prefabs
├── Cars
│   ├── Car_Player1
│   └── Car_Player2
└── UI                      ← MRTemplate UI for neurofeedback HUD (later)
```

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Pink materials | **Edit → Rendering → Materials → Convert All Built-in Materials to URP** |
| No XR on device | Check OpenXR enabled for Android; reinstall Meta Quest app |
| Photon won't connect | Verify App ID in PhotonServerSettings; check internet |
| Cars fall through track | Use `Prefabs_Obs` (colliders), not mesh-only prefabs |
| VS doesn't open | Regenerate: **Edit → Preferences → External Tools → Regenerate project files** |

---

## Next development milestones

1. `XRCarController.cs` — Quest thumbstick driving
2. `PhotonCarSpawner.cs` — `PhotonNetwork.Instantiate` per player
3. Add **LSL4Unity** package — neurofeedback data stream
4. `RaceHUD.cs` — world-space canvas for hyperscanning score
5. Remove `_Reference/` folder once track merge is verified

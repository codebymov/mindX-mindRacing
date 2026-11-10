// MindXSceneScaffold.cs — builds the track-local scene scaffold described in
// unity/XR_SETUP.md (DECISIONS.md D7): ONE shared car + the BEDRILL track under
// a single anchorable TrackRoot, with FeedbackReceiver wired to drive the car.
//
// Run from the editor menu (MindX > Build Track-Local Scaffold) or headless via
//   Unity.exe -batchmode -quit -projectPath <unity> -executeMethod MindXEditor.MindXSceneScaffold.Build
// Idempotent: re-running rebuilds TrackRoot cleanly. Non-destructive to the rig.

using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace MindXEditor
{
    public static class MindXSceneScaffold
    {
        const string MainScenePath = "Assets/Scenes/MindXRacing.unity";
        const string RefScenePath  = "Assets/Scenes/_Reference/PhotonConnection.unity";
        const string CarPrefabPath = "Assets/CarControll/Prefabs (With Colliders)/Free Racing Car Blue Variant.prefab";
        const string GazeInteractorPrefab = "Assets/Samples/XR Interaction Toolkit/2.5.4/Starter Assets/Prefabs/Interactors/Gaze Interactor.prefab";
        const string TwoCarTestScene = "Assets/Scenes/TwoCarTest.unity";
        const string TableArScene = "Assets/Scenes/TableARPreview.unity";
        const string CarBluePrefab = "Assets/CarControll/Prefabs (With Colliders)/Free Racing Car Blue Variant.prefab";
        const string CarRedPrefab = "Assets/CarControll/Prefabs (With Colliders)/Free Racing Car Red Variant.prefab";

        [MenuItem("MindX/Build Track-Local Scaffold")]
        public static void Build()
        {
            var main = EditorSceneManager.OpenScene(MainScenePath, OpenSceneMode.Single);
            var rootNames = string.Join(", ", main.GetRootGameObjects().Select(g => g.name));
            Log($"opened {main.name}; roots: {rootNames}");

            // Idempotent: drop any prior TrackRoot
            foreach (var old in main.GetRootGameObjects().Where(g => g.name == "TrackRoot").ToArray())
                Object.DestroyImmediate(old);

            // 1) TrackRoot — the single anchorable, track-local root. Move THIS to place
            //    the world; all gameplay stays in TrackRoot-local coordinates (D7).
            var trackRoot = new GameObject("TrackRoot");
            SceneManager.MoveGameObjectToScene(trackRoot, main);
            trackRoot.transform.position = Vector3.zero;

            // 2) Copy the track (CircularMap, + Boundries if it's separate) from the
            //    reference scene into TrackRoot, track-local at origin.
            var refScene = EditorSceneManager.OpenScene(RefScenePath, OpenSceneMode.Additive);
            var map = FindInScene(refScene, "CircularMap");
            if (map != null)
            {
                var copy = Object.Instantiate(map);
                copy.name = "CircularMap";
                SceneManager.MoveGameObjectToScene(copy, main);
                copy.transform.SetParent(trackRoot.transform, false);
                copy.transform.localPosition = Vector3.zero;
                copy.transform.localRotation = Quaternion.identity;

                // bring the walls along only if they aren't already inside CircularMap
                if (copy.GetComponentsInChildren<Transform>(true).All(t => t.name != "Boundries"))
                {
                    var walls = FindInScene(refScene, "Boundries");
                    if (walls != null)
                    {
                        var wcopy = Object.Instantiate(walls);
                        wcopy.name = "Boundries";
                        SceneManager.MoveGameObjectToScene(wcopy, main);
                        wcopy.transform.SetParent(trackRoot.transform, false);
                    }
                }
                Log("track copied under TrackRoot");
            }
            else Warn("CircularMap not found in reference scene");
            EditorSceneManager.CloseScene(refScene, true);

            // 3) SharedCar — exactly ONE car, driven by joint INS via FeedbackReceiver.
            var carPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(CarPrefabPath);
            GameObject car;
            if (carPrefab != null)
            {
                car = (GameObject)PrefabUtility.InstantiatePrefab(carPrefab, main);
                car.name = "SharedCar";
            }
            else
            {
                car = new GameObject("SharedCar");
                SceneManager.MoveGameObjectToScene(car, main);
                Warn($"car prefab not found at {CarPrefabPath}; created empty SharedCar");
            }
            car.transform.SetParent(trackRoot.transform, false);
            car.transform.localPosition = new Vector3(0f, 0.5f, 0f);

            var engine = car.GetComponent<AudioSource>();
            if (engine == null) engine = car.AddComponent<AudioSource>();
            engine.playOnAwake = true; engine.loop = true; engine.spatialBlend = 1f;

            var fr = car.GetComponent<MindX.FeedbackReceiver>();
            if (fr == null) fr = car.AddComponent<MindX.FeedbackReceiver>();
            var so = new SerializedObject(fr);
            var carProp = so.FindProperty("car");
            if (carProp != null) carProp.objectReferenceValue = car.transform;
            var engProp = so.FindProperty("engine");
            if (engProp != null) engProp.objectReferenceValue = engine;
            so.ApplyModifiedProperties();
            Log("SharedCar created and FeedbackReceiver wired (car + engine)");

            EditorSceneManager.MarkSceneDirty(main);
            EditorSceneManager.SaveScene(main);
            Log("scaffold complete and scene saved.");
        }

        // Wire eye-gaze as an input on the rig: add the XRI Gaze Interactor. Its
        // GazeInputManager auto-selects the OpenXR "EyeGaze" device when eye tracking
        // is available (we enabled the Eye Gaze Interaction Profile), and falls back
        // to head pose otherwise. Idempotent.
        [MenuItem("MindX/Wire Eye-Gaze On Rig")]
        public static void WireEyeGaze()
        {
            var main = EditorSceneManager.OpenScene(MainScenePath, OpenSceneMode.Single);

            var cam = Camera.main;
            if (cam == null) cam = Object.FindObjectOfType<Camera>();
            if (cam == null) { Warn("no camera in scene; cannot attach gaze interactor"); return; }
            var parent = cam.transform.parent != null ? cam.transform.parent : cam.transform;

            foreach (var old in parent.GetComponentsInChildren<Transform>(true)
                         .Where(t => t.name == "Gaze Interactor").ToArray())
                Object.DestroyImmediate(old.gameObject);

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(GazeInteractorPrefab);
            if (prefab == null) { Warn($"Gaze Interactor prefab not found: {GazeInteractorPrefab}"); return; }
            var gaze = (GameObject)PrefabUtility.InstantiatePrefab(prefab, main);
            gaze.name = "Gaze Interactor";
            gaze.transform.SetParent(parent, false);
            gaze.transform.localPosition = Vector3.zero;
            gaze.transform.localRotation = Quaternion.identity;

            Log($"Gaze Interactor attached under '{parent.name}' (eye-gaze via GazeInputManager; head fallback).");
            EditorSceneManager.MarkSceneDirty(main);
            EditorSceneManager.SaveScene(main);
            Log("eye-gaze wired and scene saved.");
        }

        // Phase 1: a runnable, hardware-free TWO-CAR test scene. Non-XR so it
        // plays without a headset and doesn't fight the XR camera. Track + two cars
        // (P1=WASD, P2=Arrows via KeyboardCarInput + CarDriver) + split-screen
        // cameras + a safety ground plane. Press Play and drive.
        [MenuItem("MindX/Build Local Two-Car Test (WASD + Split-Screen)")]
        public static void BuildLocalTwoCarTest()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var lightGO = new GameObject("Directional Light");
            SceneManager.MoveGameObjectToScene(lightGO, scene);
            var light = lightGO.AddComponent<Light>();
            light.type = LightType.Directional;
            lightGO.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            var trackRoot = new GameObject("TrackRoot");
            SceneManager.MoveGameObjectToScene(trackRoot, scene);
            var refScene = EditorSceneManager.OpenScene(RefScenePath, OpenSceneMode.Additive);
            GameObject trackCopy = null;
            var map = FindInScene(refScene, "CircularMap");
            if (map != null)
            {
                trackCopy = Object.Instantiate(map);
                trackCopy.name = "CircularMap";
                SceneManager.MoveGameObjectToScene(trackCopy, scene);
                trackCopy.transform.SetParent(trackRoot.transform, false);
                trackCopy.transform.localPosition = Vector3.zero;
            }
            else Warn("CircularMap not found in reference scene");
            EditorSceneManager.CloseScene(refScene, true);

            Physics.SyncTransforms();

            // bounds of the track + a safety ground plane so cars never fall into the void
            Vector3 start = new Vector3(0f, 1f, 0f);
            Vector3 tangent = Vector3.forward;
            if (trackCopy != null)
            {
                var rends = trackCopy.GetComponentsInChildren<Renderer>();
                if (rends.Length > 0)
                {
                    Bounds b = rends[0].bounds;
                    foreach (var r in rends) b.Encapsulate(r.bounds);

                    var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
                    ground.name = "Ground (safety)";
                    SceneManager.MoveGameObjectToScene(ground, scene);
                    ground.transform.position = new Vector3(b.center.x, b.min.y, b.center.z);
                    ground.transform.localScale = Vector3.one * (Mathf.Max(b.size.x, b.size.z) / 5f);

                    if (TryFindRoadSpawn(trackCopy, out var spawn, out tangent)) start = spawn;
                    else Warn("no road tile found; cars placed at the origin");
                }
            }

            Quaternion facing = Quaternion.LookRotation(tangent, Vector3.up);
            Vector3 right = Vector3.Cross(Vector3.up, tangent);
            const float LaneOffset = 2.5f; // metres either side of the road centre line

            var car1 = CreateTestCar(scene, CarBluePrefab, "Car_Player1 (Blue)", start - right * LaneOffset, facing,
                          MindX.KeyboardCarInput.Scheme.WASD, new Rect(0f, 0f, 0.5f, 1f), addListener: true);
            var car2 = CreateTestCar(scene, CarRedPrefab, "Car_Player2 (Red)", start + right * LaneOffset, facing,
                          MindX.KeyboardCarInput.Scheme.Arrows, new Rect(0.5f, 0f, 0.5f, 1f), addListener: false);

            WireFeedback(scene, new[] { car1, car2 });

            // Safety net: a car that leaves the play area is put back on the road.
            foreach (var car in new[] { car1, car2 })
                car.AddComponent<MindX.CarRecovery>().TrackRoot = trackRoot.transform;

            // Game mechanics: coins on the road and a score per player. The score is drawn
            // in that player's own view; faster driving (a higher brain-synchrony level)
            // passes more coins per minute.
            var score1 = AddScore(car1, "P1");
            var score2 = AddScore(car2, "P2");
            if (trackCopy != null) PlaceCoins(scene, trackCopy, EnsureCoinPrefab());
            var scoreHud = new GameObject("ScoreHud").AddComponent<MindX.ScoreHud>();
            scoreHud.Add(score1, car1.GetComponentInChildren<Camera>());
            scoreHud.Add(score2, car2.GetComponentInChildren<Camera>());

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, TwoCarTestScene);
            Log($"Two-car test built -> {TwoCarTestScene}. P1=WASD (left view), P2=Arrows (right view). Press Play.");
        }

        // A SIMULATED table-top AR view. The game runs 1:1 (the two-car test world);
        // the table shows scaled visual twins of the track and cars, seen from a
        // headset-like camera. No passthrough: this previews how the game would sit
        // on a table, it is not the XR build.
        [MenuItem("MindX/Build Table AR Preview (simulated)")]
        public static void BuildTableArPreview()
        {
            BuildLocalTwoCarTest(); // leaves the 1:1 simulation as the active scene
            var scene = EditorSceneManager.GetActiveScene();

            // Autopilot instead of the keyboard: each car holds its own lane and weaves
            // with its own period, so the cars stay on the track and take different
            // lines. Speed still comes from the feedback level (CarDriver.LevelSource).
            var pilots = Object.FindObjectsByType<MindX.CarDriver>().OrderBy(d => d.name).ToArray();
            for (int i = 0; i < pilots.Length; i++)
            {
                foreach (var keys in pilots[i].GetComponents<MindX.KeyboardCarInput>()) Object.DestroyImmediate(keys);
                var pilot = pilots[i].gameObject.AddComponent<MindX.TrackAutopilot>();
                // Lanes 4.8 m apart with a 1.4 m weave: the cars take different lines and
                // only occasionally touch (the gap can close to ~2 m, about a car width), so
                // the crash penalty is possible but not constant.
                pilot.LaneOffset = i == 0 ? -2.4f : 2.4f; // car 1 left lane, car 2 right lane of travel
                pilot.SetWeave(1.4f, i == 0 ? 23f : 31f, i == 0 ? 0f : 1.7f);
                var driverSo = new SerializedObject(pilots[i]);
                driverSo.FindProperty("turnSpeed").floatValue = 120f; // corners at up to ~17 m/s
                driverSo.ApplyModifiedPropertiesWithoutUndo();
            }

            // Light from the side: the two seats look along the table's length, and the
            // default light shines straight at one of them, washing that view out.
            var sun = Object.FindAnyObjectByType<Light>();
            if (sun != null) sun.transform.rotation = Quaternion.Euler(65f, 90f, 0f);

            const float Scale = 0.0075f; // the ~105 m ring becomes ~0.8 m on the table
            var tableOrigin = new Vector3(1000f, 0.75f, 0f); // far from the 1:1 world; y = table top

            var map = GameObject.Find("CircularMap");
            if (map == null) { Warn("CircularMap not found; table preview not built"); return; }

            // The ring centre is the point that sits at the middle of the table.
            var tiles = map.GetComponentsInChildren<Collider>().Where(c => c.name.StartsWith("Track_")).ToArray();
            Vector3 centre = Vector3.zero;
            foreach (var t in tiles) centre += t.bounds.center;
            centre /= Mathf.Max(1, tiles.Length);
            var simOrigin = new Vector3(centre.x, 0f, centre.z);

            // Room: floor and table.
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Room Floor";
            floor.transform.position = new Vector3(tableOrigin.x, 0f, 0f);
            floor.transform.localScale = Vector3.one * 0.6f;
            var table = GameObject.CreatePrimitive(PrimitiveType.Cube);
            table.name = "Table";
            table.transform.localScale = new Vector3(1.4f, 0.05f, 1.0f);
            // 4 mm below the anchor: the road underside sits exactly at the anchor height
            // and would z-fight with a table top at the same height (patchy road).
            table.transform.position = new Vector3(tableOrigin.x, tableOrigin.y - 0.025f - 0.004f, tableOrigin.z);
            foreach (var go in new[] { floor, table }) Object.DestroyImmediate(go.GetComponent<Collider>());
            SetFlatColor(floor, "Assets/Scenes/TableAR_Floor.mat", new Color(0.16f, 0.15f, 0.14f));
            SetFlatColor(table, "Assets/Scenes/TableAR_Table.mat", new Color(0.55f, 0.38f, 0.22f));

            // Visual twin of the track: no colliders, and without the 15 m boundary walls.
            var trackTwin = Object.Instantiate(map);
            trackTwin.name = "TableTrack (visual twin)";
            trackTwin.transform.SetParent(null);
            foreach (var wall in trackTwin.GetComponentsInChildren<Transform>(true)
                         .Where(t => t.name.StartsWith("Cube")).Select(t => t.gameObject).ToArray())
                Object.DestroyImmediate(wall);
            foreach (var col in trackTwin.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(col);
            trackTwin.transform.position = MindX.ScaledTwin.MapPosition(map.transform.position, simOrigin, tableOrigin, Scale);
            trackTwin.transform.rotation = map.transform.rotation;
            trackTwin.transform.localScale = Vector3.one * Scale;
            NoShadows(trackTwin);
            NoShadows(floor);
            NoShadows(table);

            // Visual twins of the cars, following the simulated cars.
            foreach (var driver in Object.FindObjectsByType<MindX.CarDriver>())
            {
                string prefabPath = driver.name.Contains("Red") ? CarRedPrefab : CarBluePrefab;
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
                if (prefab == null) { Warn($"car prefab not found: {prefabPath}"); continue; }
                var twin = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                twin.name = driver.name + " (table twin)";
                foreach (var mb in twin.GetComponentsInChildren<MonoBehaviour>(true)) Object.DestroyImmediate(mb);
                foreach (var col in twin.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(col);
                foreach (var body in twin.GetComponentsInChildren<Rigidbody>(true)) Object.DestroyImmediate(body);
                twin.AddComponent<MindX.ScaledTwin>().Configure(driver.transform, simOrigin, tableOrigin, Scale);
                NoShadows(twin);
            }

            // Coin twins: a miniature of every coin on the table, hidden while collected.
            foreach (var coin in Object.FindObjectsByType<MindX.Coin>())
            {
                var coinTwin = Object.Instantiate(coin.gameObject);
                coinTwin.name = coin.name + " (table twin)";
                foreach (var logic in coinTwin.GetComponentsInChildren<MindX.Coin>(true)) Object.DestroyImmediate(logic);
                foreach (var col in coinTwin.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(col);
                coinTwin.AddComponent<MindX.ScaledTwin>().Configure(coin.transform, simOrigin, tableOrigin, Scale);
                NoShadows(coinTwin);
            }

            // Two simulated headset views, one per player, seated on opposite sides of the
            // table and shown side by side. The chase cameras are turned off; each view shows
            // that player's own score. The simulated cars are still driven in the 1:1 world.
            foreach (var cam in Object.FindObjectsByType<Camera>())
                if (cam.GetComponentInParent<MindX.CarDriver>() != null) cam.gameObject.SetActive(false);
            var tableCentre = new Vector3(tableOrigin.x, tableOrigin.y, tableOrigin.z);
            var view1 = CreateHeadsetView("P1 Headset View (simulated)", tableCentre + new Vector3(0f, 0.4f, -0.72f), tableCentre,
                                          new Rect(0f, 0f, 0.5f, 1f), withListener: true);
            var view2 = CreateHeadsetView("P2 Headset View (simulated)", tableCentre + new Vector3(0f, 0.4f, 0.72f), tableCentre,
                                          new Rect(0.5f, 0f, 0.5f, 1f), withListener: false);
            var tableScores = Object.FindObjectsByType<MindX.CarScore>().OrderBy(s => s.name).ToArray();
            var tableScoreHud = Object.FindAnyObjectByType<MindX.ScoreHud>();
            if (tableScoreHud != null && tableScores.Length >= 2)
            {
                tableScoreHud.Clear();
                tableScoreHud.Add(tableScores[0], view1);
                tableScoreHud.Add(tableScores[1], view2);
            }

            var hud = Object.FindAnyObjectByType<MindX.FeedbackHud>();
            if (hud != null)
                hud.Caption = "SIMULATED AR VIEW - track anchored on a table (headset pending). "
                              + "Synthetic data. {mode}";

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, TableArScene);
            Log($"Table AR preview built -> {TableArScene}. Steer P1=WASD, P2=Arrows. Press Play.");
        }

        static MindX.CarScore AddScore(GameObject car, string playerName)
        {
            var score = car.AddComponent<MindX.CarScore>();
            score.PlayerName = playerName;
            return score;
        }

        // A spinning gold disc with a trigger, saved as a prefab so it is a real asset
        // that can be replaced by art later (keep the Coin component and the trigger).
        static GameObject EnsureCoinPrefab()
        {
            const string path = "Assets/Prefabs/Coin.prefab";

            // A car counts as collecting a coin when it passes within this radius (metres).
            // Each player's coins lie in that player's own lane (6 m apart) and a car weaves
            // up to ~1.4 m about its lane, so 2.4 m reaches every coin in the own lane and
            // none in the other lane.
            const float PickupRadius = 2.4f;

            var existing = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (existing != null)
            {
                var contents = PrefabUtility.LoadPrefabContents(path);
                var existingTrigger = contents.GetComponent<SphereCollider>();
                if (existingTrigger != null && !Mathf.Approximately(existingTrigger.radius, PickupRadius))
                {
                    existingTrigger.radius = PickupRadius;
                    PrefabUtility.SaveAsPrefabAsset(contents, path);
                }

                PrefabUtility.UnloadPrefabContents(contents);
                return AssetDatabase.LoadAssetAtPath<GameObject>(path);
            }

            if (!AssetDatabase.IsValidFolder("Assets/Prefabs")) AssetDatabase.CreateFolder("Assets", "Prefabs");
            var root = new GameObject("Coin");
            var trigger = root.AddComponent<SphereCollider>();
            trigger.isTrigger = true;
            trigger.radius = PickupRadius;
            root.AddComponent<MindX.Coin>();

            var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            disc.name = "Disc";
            disc.transform.SetParent(root.transform, false);
            disc.transform.localRotation = Quaternion.Euler(90f, 0f, 0f); // stands on its edge
            disc.transform.localScale = new Vector3(1.7f, 0.1f, 1.7f);
            Object.DestroyImmediate(disc.GetComponent<Collider>());
            SetFlatColor(disc, "Assets/Prefabs/Coin_Gold.mat", new Color(1f, 0.78f, 0.1f));

            var prefab = PrefabUtility.SaveAsPrefabAsset(root, path);
            Object.DestroyImmediate(root);
            return prefab;
        }

        // Puts coins on the road in two lanes, one per player: no lane is shared, so one
        // player cannot take the other's coins first (the inside car laps faster, and a
        // shared centre lane gave it nearly all of those coins). The road centre at each
        // angle is found by ray-casting to the inner and outer boundary walls and taking
        // the midpoint, so no track data is needed. Travel is clockwise seen from above, so
        // the "right of travel" side of the road is toward the infield.
        static List<GameObject> PlaceCoins(Scene scene, GameObject track, GameObject coinPrefab)
        {
            var coins = new List<GameObject>();
            var tiles = track.GetComponentsInChildren<Collider>().Where(c => c.name.StartsWith("Track_")).ToArray();
            if (tiles.Length == 0 || coinPrefab == null) return coins;

            Vector3 centre = Vector3.zero;
            foreach (var t in tiles) centre += t.bounds.center;
            centre /= tiles.Length;
            var origin = new Vector3(centre.x, 1f, centre.z);

            const int Steps = 72;
            const float Lane = 3f;
            float[] lanes = { -Lane, Lane }; // car 1's lane (left of travel), car 2's lane (right)
            for (int k = 0; k < Steps; k += 3)
            {
                float angle = k * 2f * Mathf.PI / Steps;
                var dir = new Vector3(Mathf.Cos(angle), 0f, Mathf.Sin(angle));
                if (!Physics.Raycast(origin, dir, out var inner, 200f) || !inner.collider.name.StartsWith("Cube")) continue;
                if (!Physics.Raycast(origin + dir * 150f, -dir, out var outer, 200f) || !outer.collider.name.StartsWith("Cube")) continue;

                float middle = (inner.distance + (150f - outer.distance)) * 0.5f;
                Vector3 onCentreLine = new Vector3(centre.x, 0f, centre.z) + dir * middle;
                Vector3 tangent = Vector3.Cross(Vector3.up, dir);
                Vector3 rightOfTravel = Vector3.Cross(Vector3.up, tangent);
                Vector3 position = onCentreLine + rightOfTravel * lanes[(k / 3) % 2];
                position.y = 1.2f;

                var coin = (GameObject)PrefabUtility.InstantiatePrefab(coinPrefab, scene);
                coin.name = $"Coin {coins.Count + 1}";
                coin.transform.position = position;
                coins.Add(coin);
            }

            Log($"placed {coins.Count} coins on the road");
            return coins;
        }

        static Camera CreateHeadsetView(string name, Vector3 position, Vector3 lookAt, Rect viewport, bool withListener)
        {
            var go = new GameObject(name);
            var cam = go.AddComponent<Camera>();
            cam.fieldOfView = 55f;
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 50f; // the 1:1 world is ~1 km away and stays out of view
            cam.rect = viewport;
            if (withListener)
            {
                go.tag = "MainCamera";
                go.AddComponent<AudioListener>();
            }

            go.transform.position = position;
            go.transform.LookAt(lookAt);
            return cam;
        }

        // Miniature (0.0075 scale) geometry with default shadow bias shows dark
        // acne blotches on the table, so the table-top twins neither cast nor
        // receive shadows.
        static void NoShadows(GameObject root)
        {
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r.receiveShadows = false;
            }
        }

        // Gives a primitive a saved, flat-coloured material (an unsaved runtime
        // material would be lost when the scene is reloaded).
        static void SetFlatColor(GameObject go, string materialPath, Color color)
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard");
            var mat = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (mat == null)
            {
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, materialPath);
            }

            mat.color = color;
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", 0f); // matte: no glare
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", 0f);
            EditorUtility.SetDirty(mat);
            go.GetComponent<Renderer>().sharedMaterial = mat;
        }

        static GameObject CreateTestCar(Scene scene, string prefabPath, string name, Vector3 pos, Quaternion rot,
                                  MindX.KeyboardCarInput.Scheme scheme, Rect viewport, bool addListener)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            GameObject car;
            if (prefab != null) { car = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene); car.name = name; }
            else { car = new GameObject(name); SceneManager.MoveGameObjectToScene(car, scene); Warn($"car prefab not found: {prefabPath}"); }
            car.transform.SetPositionAndRotation(pos, rot);

            // strip any conflicting movers from the prefab so only CarDriver moves it
            foreach (var cc in car.GetComponents<CarController>()) Object.DestroyImmediate(cc);
            foreach (var fr in car.GetComponents<MindX.FeedbackReceiver>()) Object.DestroyImmediate(fr);
            if (car.GetComponent<Rigidbody>() == null) car.AddComponent<Rigidbody>();

            // CarDriver steers by rotating about Y only: lock roll/pitch so the car cannot tip.
            car.GetComponent<Rigidbody>().constraints = RigidbodyConstraints.FreezeRotationX | RigidbodyConstraints.FreezeRotationZ;

            var input = car.GetComponent<MindX.KeyboardCarInput>();
            if (input == null) input = car.AddComponent<MindX.KeyboardCarInput>();
            input.InputScheme = scheme;
            if (car.GetComponent<MindX.CarDriver>() == null) car.AddComponent<MindX.CarDriver>();

            var camGO = new GameObject(name + " Camera");
            camGO.transform.SetParent(car.transform, false);
            camGO.transform.localPosition = new Vector3(0f, 4f, -7f);
            camGO.transform.localRotation = Quaternion.Euler(18f, 0f, 0f);
            var cam = camGO.AddComponent<Camera>();
            cam.rect = viewport;
            if (addListener) camGO.AddComponent<AudioListener>();
            return car;
        }

        // Adds a FeedbackReceiver to each car (subject index = car index), points
        // CarDriver at it so LSL level sets the speed, and adds the on-screen HUD.
        static void WireFeedback(Scene scene, GameObject[] cars)
        {
            var receivers = new MindX.FeedbackReceiver[cars.Length];
            for (int i = 0; i < cars.Length; i++)
            {
                var fr = cars[i].AddComponent<MindX.FeedbackReceiver>();
                var so = new SerializedObject(fr);
                so.FindProperty("streamName").stringValue = "mindx_feedback";
                so.FindProperty("autoConnect").boolValue = true;
                so.FindProperty("carSubjectIndex").intValue = i;
                so.FindProperty("car").objectReferenceValue = null; // CarDriver moves the car
                so.ApplyModifiedPropertiesWithoutUndo();
                cars[i].GetComponent<MindX.CarDriver>().LevelSource = fr;
                receivers[i] = fr;
            }

            var hudGo = new GameObject("FeedbackHud");
            SceneManager.MoveGameObjectToScene(hudGo, scene);
            hudGo.AddComponent<MindX.FeedbackHud>().SetReceivers(receivers);
        }

        // Finds a spawn point ON THE ROAD: the surface of a straight road tile
        // (only colliders named Track_* under the track count, never the boundary
        // walls), plus the driving direction along the ring. Cars face
        // the tangent of the ring at that tile, snapped to the tile's axis.
        static bool TryFindRoadSpawn(GameObject track, out Vector3 point, out Vector3 tangent)
        {
            point = Vector3.zero;
            tangent = Vector3.forward;

            var tiles = track.GetComponentsInChildren<Collider>()
                .Where(c => c.name.StartsWith("Track_")).ToArray();
            if (tiles.Length == 0) return false;

            // Ring centre = mean of the tile centres; pick the straight tile with the lowest Z.
            Vector3 centre = Vector3.zero;
            foreach (var t in tiles) centre += t.bounds.center;
            centre /= tiles.Length;

            var straight = tiles.Where(c => c.name.StartsWith("Track_line"))
                .OrderBy(c => c.bounds.center.z).FirstOrDefault();
            if (straight == null) return false;

            Vector3 top = straight.bounds.center + Vector3.up * 50f;
            bool found = false;
            foreach (var hit in Physics.RaycastAll(top, Vector3.down, 100f))
            {
                if (hit.collider != straight) continue; // ignore walls and the safety plane
                point = hit.point + Vector3.up * 0.15f;
                found = true;
                break;
            }
            if (!found) return false;

            Vector3 radial = straight.bounds.center - centre; radial.y = 0f;
            Vector3 around = Vector3.Cross(Vector3.up, radial); // anticlockwise seen from above
            tangent = Mathf.Abs(around.x) > Mathf.Abs(around.z)
                ? new Vector3(Mathf.Sign(around.x), 0f, 0f)
                : new Vector3(0f, 0f, Mathf.Sign(around.z));
            return true;
        }

        static GameObject FindInScene(Scene s, string name)
        {
            foreach (var root in s.GetRootGameObjects())
            {
                if (root.name == name) return root;
                var hit = root.GetComponentsInChildren<Transform>(true).FirstOrDefault(t => t.name == name);
                if (hit != null) return hit.gameObject;
            }
            return null;
        }

        static void Log(string m)  => Debug.Log($"[scaffold] {m}");
        static void Warn(string m) => Debug.LogWarning($"[scaffold] {m}");
    }
}

// MindXSceneScaffold.cs — builds the track-local scene scaffold described in
// unity/XR_SETUP.md (DECISIONS.md D7): ONE shared car + the BEDRILL track under
// a single anchorable TrackRoot, with FeedbackReceiver wired to drive the car.
//
// Run from the editor menu (MindX > Build Track-Local Scaffold) or headless via
//   Unity.exe -batchmode -quit -projectPath <unity> -executeMethod MindXEditor.MindXSceneScaffold.Build
// Idempotent: re-running rebuilds TrackRoot cleanly. Non-destructive to the rig.

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

                    if (TryFindTrackSurface(b, out var surf)) start = surf + Vector3.up * 0.6f;
                    else start = new Vector3(b.center.x, b.min.y + 0.6f, b.center.z);
                }
            }

            CreateTestCar(scene, CarBluePrefab, "Car_Player1 (Blue)", start + Vector3.left * 2f,
                          KeyboardCarInput.Scheme.WASD, new Rect(0f, 0f, 0.5f, 1f), addListener: true);
            CreateTestCar(scene, CarRedPrefab, "Car_Player2 (Red)", start + Vector3.right * 2f,
                          KeyboardCarInput.Scheme.Arrows, new Rect(0.5f, 0f, 0.5f, 1f), addListener: false);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, TwoCarTestScene);
            Log($"Two-car test built -> {TwoCarTestScene}. P1=WASD (left view), P2=Arrows (right view). Press Play.");
        }

        static void CreateTestCar(Scene scene, string prefabPath, string name, Vector3 pos,
                                  KeyboardCarInput.Scheme scheme, Rect viewport, bool addListener)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            GameObject car;
            if (prefab != null) { car = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene); car.name = name; }
            else { car = new GameObject(name); SceneManager.MoveGameObjectToScene(car, scene); Warn($"car prefab not found: {prefabPath}"); }
            car.transform.position = pos;

            // strip any conflicting movers from the prefab so only CarDriver moves it
            foreach (var cc in car.GetComponents<CarController>()) Object.DestroyImmediate(cc);
            foreach (var fr in car.GetComponents<MindX.FeedbackReceiver>()) Object.DestroyImmediate(fr);
            if (car.GetComponent<Rigidbody>() == null) car.AddComponent<Rigidbody>();

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
        }

        // Scan downward from above the track to find a road point on the ring
        // (the center of a circular track is empty, so try increasing radii).
        static bool TryFindTrackSurface(Bounds b, out Vector3 point)
        {
            point = Vector3.zero;
            float top = b.max.y + 10f;
            foreach (var f in new[] { 0.5f, 0.7f, 0.6f, 0.8f, 0.4f, 0.9f, 0.0f })
                foreach (var dir in new[] { Vector3.right, Vector3.forward, Vector3.left, Vector3.back })
                {
                    Vector3 xz = b.center + dir * (b.extents.x * f);
                    if (Physics.Raycast(new Vector3(xz.x, top, xz.z), Vector3.down, out var hit, 60f))
                    {
                        point = hit.point;
                        return true;
                    }
                }
            return false;
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

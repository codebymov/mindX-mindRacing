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

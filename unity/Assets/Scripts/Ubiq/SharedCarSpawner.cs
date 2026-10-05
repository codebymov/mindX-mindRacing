// SharedCarSpawner.cs — spawn the shared car room-wide via Ubiq (O5, item 2).
//
// Ubiq room-scoped spawning gives every peer an instance of the car prefab with
// a MATCHING NetworkId, which is what lets the host's state messages route to the
// right object on each client. Only the lab-host spawns (spawnAsAuthority = true);
// a room-scoped spawn instantiates the prefab on all peers with isAuthority =
// false, so the host promotes its OWN returned instance to authority. Clients
// receive the instance through Ubiq and stay renderers.
//
// Requires the Ubiq package. The car prefab must be registered in the
// NetworkScene's PrefabCatalogue and its root must carry UbiqSharedCarNetwork
// (which implements INetworkSpawnable). See docs/UBIQ_SETUP.md.

using Ubiq.Spawning;
using UnityEngine;

namespace MindX
{
    public class SharedCarSpawner : MonoBehaviour
    {
        [Tooltip("The shared-car prefab (root has UbiqSharedCarNetwork + SharedCarAuthority). Must be in the PrefabCatalogue.")]
        [SerializeField] private GameObject carPrefab;

        [Tooltip("True ONLY in the lab-host scene/build. Clients leave this false — they receive the spawned car.")]
        [SerializeField] private bool spawnAsAuthority = false;

        private bool _spawned;

        void Start()
        {
            if (!spawnAsAuthority || _spawned || carPrefab == null)
                return;

            GameObject go = NetworkSpawnManager.Find(this).SpawnWithRoomScope(carPrefab);
            var net = go.GetComponent<UbiqSharedCarNetwork>();
            if (net != null)
                net.SetAuthority(true); // this peer is the single authority
            else
                Debug.LogWarning("[MindX] Spawned car prefab has no UbiqSharedCarNetwork on its root.");

            _spawned = true;
            Debug.Log("[MindX] Shared car spawned (room scope) as authority.");
        }
    }
}

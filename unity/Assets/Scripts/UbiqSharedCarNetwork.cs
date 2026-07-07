// UbiqSharedCarNetwork.cs — Ubiq implementation of the O5 shared-car seam (D12).
//
// REQUIRES the Ubiq package (UCL-VR/ubiq) — see docs/UBIQ_SETUP.md. Until it is
// installed this file will not compile; that is expected (same as the LSL4Unity
// dependency for LslFeedbackTransport). The Ubiq-specific surface is deliberately
// tiny and lives only here, behind ISharedCarNetwork.
//
// Model: Ubiq is peer message-passing (no built-in server authority), so we
// assign the authority role ourselves — the lab-host instance has isAuthority =
// true and is the only peer that SendJson's state; clients apply it in
// ProcessMessage and never emit. All three peers share one spawnable NetworkId so
// they address the same object.

using Ubiq.Messaging;
using UnityEngine;

namespace MindX
{
    public class UbiqSharedCarNetwork : MonoBehaviour, ISharedCarNetwork, INetworkSpawnable
    {
        // Assigned by Ubiq's NetworkSpawner when the object is spawned; the same
        // id on every peer is what routes messages to the matching component.
        public NetworkId NetworkId { get; set; }

        [Tooltip("True on the lab-host only (the LSL consumer + scene authority). Clients leave this false.")]
        [SerializeField] private bool isAuthority = false;

        public bool IsAuthority => isAuthority;

        /// Promote/demote this instance's authority role. A room-scoped spawn
        /// instantiates the SAME prefab on every peer (isAuthority = false), so
        /// the lab-host that spawned it calls this on its own returned instance to
        /// become the single authority. See SharedCarSpawner.
        public void SetAuthority(bool value) => isAuthority = value;

        private NetworkContext _context;
        private SharedCarState _latest;
        private bool _have;

        void Start()
        {
            // Register with Ubiq and keep the returned context to send with.
            _context = NetworkScene.Register(this);
        }

        public void PublishState(SharedCarState state)
        {
            if (!isAuthority)
                return; // only the authority emits — clients are pure renderers
            _latest = state;
            _have = true;
            _context.SendJson(state);
        }

        public void ProcessMessage(ReferenceCountedSceneGraphMessage message)
        {
            if (isAuthority)
                return; // authority is the source of truth; ignore any echo
            _latest = message.FromJson<SharedCarState>();
            _have = true;
        }

        public bool TryGetLatest(out SharedCarState state)
        {
            state = _latest;
            return _have;
        }
    }
}

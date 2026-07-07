using UnityEngine;

namespace MindX
{
    /// A replicated snapshot of the shared car's authoritative state (O5).
    ///
    /// Position/rotation are in **track-local space** (D7): relative to the
    /// co-located track root each headset established at session start (D11). That
    /// is what makes one number valid on every headset regardless of where each
    /// runtime's physical origin sits — apply it under the local track root and
    /// the car appears at the same real-world spot for both players.
    ///
    /// level/subjectIndex/tLsl ride along so every client renders exactly the same
    /// speed-and-audio feedback, on the one clock of record (D3/D9).
    [System.Serializable]
    public struct SharedCarState
    {
        public Vector3 position;     // track-local
        public Quaternion rotation;  // track-local
        public float level;          // [0,1] feedback level driving this car
        public int subjectIndex;     // -1 = shared (hyperscanning); else owning subject
        public double tLsl;          // source LSL timestamp (one clock of record)
    }

    /// Thin seam decoupling shared-car authority + replication from the concrete
    /// netcode. Ubiq is the chosen implementation (D12), but keeping the game
    /// logic behind this interface means the choice stays swappable — the same
    /// D1 typed-seam discipline as IFeedbackTransport and ICarInput.
    ///
    /// Roles: the **lab-host** is the authority — it drives the car from the INS
    /// signal (arriving over LSL) and publishes state. The **headset clients** are
    /// pure renderers — they apply the latest replicated state and never emit, so
    /// a client can never perturb the science-critical car.
    public interface ISharedCarNetwork
    {
        /// True only on the lab-host (the LSL consumer + scene authority).
        bool IsAuthority { get; }

        /// Authority only: replicate the current car state to all peers. No-op on
        /// clients.
        void PublishState(SharedCarState state);

        /// Clients: latest state received from the authority. Returns false until
        /// the first snapshot arrives.
        bool TryGetLatest(out SharedCarState state);
    }
}

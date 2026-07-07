// FeedbackReceiver.cs — Unity side of the backend <-> game contract.
//
// The backend publishes one FeedbackSample per update tick (see
// backend/mindx_hnf/contracts.py::FeedbackSample). The game maps `level` (a
// value in [0, 1]) onto the car's speed and the engine sound's pitch/gain in
// the "mind racing" cooperation task, and reads back nothing — feedback is
// one-directional from brains to game.
//
// Transport is an open decision (see docs/DECISIONS.md O2): LSL inlet or
// websocket. This stub abstracts that so the game logic is transport-agnostic.
//
// This file is a SCAFFOLD: it pins the contract and the mapping seam. Wire up
// the chosen transport (LSL4Unity or a websocket client) where marked.

using UnityEngine;

namespace MindX
{
    /// Mirror of the backend FeedbackSample. Keep field names/semantics in sync
    /// with backend/mindx_hnf/contracts.py::FeedbackSample.
    public struct FeedbackSample
    {
        public double tLsl;        // LSL-clock timestamp (single clock of record)
        public float level;        // normalized, baseline-corrected, smoothed [0,1]
        public string mode;        // "real" | "sham" — for logging ONLY, never branch on it
        public float rawIns;       // pre-mapping INS, for logging
        public string sessionMode; // "hyperscanning" | "individual" (DECISIONS.md D8)
        public string subject;     // null/empty = shared dyad car (hyperscanning);
                                   // a subject id routes to that player's car (individual)
    }

    /// Transport-agnostic source of feedback samples.
    public interface IFeedbackTransport
    {
        bool TryGetLatest(out FeedbackSample sample);
        void Close();
    }

    public class FeedbackReceiver : MonoBehaviour
    {
        [Header("Mapping (game feel lives in the backend; these are limits)")]
        [SerializeField] private float baseSpeed = 5f;     // fixed base velocity
        [SerializeField] private float maxBonusSpeed = 15f; // added at level == 1
        [SerializeField] private float minPitch = 0.8f;
        [SerializeField] private float maxPitch = 1.6f;

        [Header("Refs")]
        [SerializeField] private Transform car;
        [SerializeField] private AudioSource engine;

        private IFeedbackTransport _transport;
        private float _currentLevel;

        // CRITICAL: do NOT branch on sample.mode anywhere a participant could
        // perceive a difference. Sham must be indistinguishable from real.
        void Update()
        {
            if (_transport != null && _transport.TryGetLatest(out var s))
            {
                _currentLevel = Mathf.Clamp01(s.level);
                // TODO: log (s.tLsl, s.level, s.mode, s.rawIns) for offline analysis.
            }

            float speed = baseSpeed + maxBonusSpeed * _currentLevel;
            if (car != null)
                car.Translate(Vector3.forward * speed * Time.deltaTime, Space.Self);

            if (engine != null)
            {
                engine.pitch = Mathf.Lerp(minPitch, maxPitch, _currentLevel);
                engine.volume = Mathf.Lerp(0.3f, 1.0f, _currentLevel);
            }
        }

        public void AttachTransport(IFeedbackTransport transport) => _transport = transport;

        void OnDestroy() => _transport?.Close();
    }

    // TODO: implement LslFeedbackTransport (LSL4Unity StreamInlet on
    // "mindx_feedback") and/or WebSocketFeedbackTransport. Both implement
    // IFeedbackTransport so FeedbackReceiver doesn't change when the
    // O2 transport decision is made.
}

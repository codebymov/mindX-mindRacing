// FeedbackReceiver.cs — Unity side of the backend <-> game contract.
//
// The backend publishes one FeedbackSample per update tick (see
// backend/mindx_hnf/contracts.py::FeedbackSample). The game maps `level` (a
// value in [0, 1]) onto the car's speed and the engine sound's pitch/gain in
// the "mind racing" cooperation task, and reads back nothing — feedback is
// one-directional from brains to game.
//
// Transport is LSL (DECISIONS.md D9, resolving O2): LslFeedbackTransport wraps
// an LSL4Unity inlet on the "mindx_feedback" stream. It stays behind
// IFeedbackTransport so this component is transport-agnostic and testable with a
// mock. Attach one FeedbackReceiver per car; `carSubjectIndex` routes samples:
// a Hyperscanning sample (shared, subjectIndex < 0) drives every car, while an
// Individual sample drives only the car whose owner it names (D8).

using UnityEngine;

namespace MindX
{
    /// Mirror of the backend FeedbackSample. Keep field names/semantics in sync
    /// with backend/mindx_hnf/contracts.py::FeedbackSample and the channel order
    /// in api/sink.py::FEEDBACK_CHANNELS.
    public struct FeedbackSample
    {
        public double tLsl;        // LSL-clock timestamp (single clock of record)
        public float level;        // normalized, baseline-corrected, smoothed [0,1]
        public string mode;        // "real" | "sham" — for logging ONLY, never branch on it
        public float rawIns;       // pre-mapping INS, for logging
        public string sessionMode; // "hyperscanning" | "individual" (DECISIONS.md D8)
        public int subjectIndex;   // -1 = shared dyad car (hyperscanning); else the
                                   // owning subject's index (individual) — used to route
        public string subject;     // decoded subject id for logging (null when shared)
    }

    /// Transport-agnostic source of feedback samples.
    public interface IFeedbackTransport
    {
        bool TryGetLatest(out FeedbackSample sample);
        void Close();
    }

    public class FeedbackReceiver : MonoBehaviour
    {
        [Header("Transport (LSL)")]
        [Tooltip("LSL stream published by the backend (LSLOutletSink).")]
        [SerializeField] private string streamName = "mindx_feedback";
        [Tooltip("Auto-resolve the LSL stream on Start. Turn off to inject a transport via AttachTransport (tests/mocks).")]
        [SerializeField] private bool autoConnect = true;
        [Tooltip("Which car this is (0, 1, ...). Shared/Hyperscanning samples drive every car regardless.")]
        [SerializeField] private int carSubjectIndex = 0;

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

        void Start()
        {
            if (autoConnect && _transport == null)
            {
                try
                {
                    _transport = new LslFeedbackTransport(streamName);
                    Debug.Log($"[MindX] FeedbackReceiver connected to LSL '{streamName}'.");
                }
                catch (System.Exception e)
                {
                    // Degrade gracefully: no stream yet just means the car idles
                    // at baseSpeed. Never hang or throw in a live session.
                    Debug.LogWarning($"[MindX] No feedback stream yet ({e.Message}). " +
                                     "Car idles until the backend publishes.");
                }
            }
        }

        // CRITICAL: do NOT branch on sample.mode anywhere a participant could
        // perceive a difference. Sham must be indistinguishable from real.
        void Update()
        {
            if (_transport != null && _transport.TryGetLatest(out var s))
            {
                // Route: shared (Hyperscanning) sample drives every car; an
                // Individual sample drives only its owning car.
                if (s.subjectIndex < 0 || s.subjectIndex == carSubjectIndex)
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

        /// Inject a transport explicitly (e.g. a mock in tests, or a shared
        /// transport). Disables the need for autoConnect.
        public void AttachTransport(IFeedbackTransport transport) => _transport = transport;

        void OnDestroy() => _transport?.Close();
    }
}

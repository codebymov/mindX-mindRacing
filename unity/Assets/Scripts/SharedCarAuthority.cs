// SharedCarAuthority.cs — bridges LSL feedback -> shared car -> Ubiq replication.
//
// This is the O5 lab-host/authority glue. It sits on the shared-car GameObject
// alongside an ISharedCarNetwork (e.g. UbiqSharedCarNetwork).
//
//   Lab-host  (network.IsAuthority == true):
//     read the INS feedback level from an LSL inlet -> advance the car forward in
//     TRACK-LOCAL space (speed proportional to INS, D7) -> PublishState so both
//     headsets replicate it. This host is the single authority; it is also the
//     only LSL consumer, keeping the science signal single-sourced.
//
//   Headset client (IsAuthority == false):
//     apply the latest replicated state under the local (co-located) track root.
//     No LSL, no car physics of its own — a pure, non-perturbing renderer.
//
// This is the NETWORKED path; FeedbackReceiver remains the single-user (non-
// networked) path. Use one or the other on a given car. The level->speed/audio
// mapping mirrors FeedbackReceiver by design so the feel is identical.

using UnityEngine;

namespace MindX
{
    public class SharedCarAuthority : MonoBehaviour
    {
        [Header("Scene refs")]
        [Tooltip("The co-located track root (D11). Replicated positions are relative to this.")]
        [SerializeField] private Transform trackRoot;
        [Tooltip("The car body to move / follow. Defaults to this transform.")]
        [SerializeField] private Transform car;
        [SerializeField] private AudioSource engine;

        [Header("Feedback source (host only)")]
        [SerializeField] private string streamName = "mindx_feedback";
        [Tooltip("Which car this is; a shared Hyperscanning sample (subjectIndex < 0) drives every car.")]
        [SerializeField] private int carSubjectIndex = 0;

        [Header("Mapping (limits; game feel lives in the backend)")]
        [SerializeField] private float baseSpeed = 5f;
        [SerializeField] private float maxBonusSpeed = 15f;
        [SerializeField] private float minPitch = 0.8f;
        [SerializeField] private float maxPitch = 1.6f;

        private ISharedCarNetwork _net;
        private IFeedbackTransport _feedback; // host-side LSL inlet
        private float _level;
        private double _tLsl;

        void Awake()
        {
            _net = GetComponent<ISharedCarNetwork>();
            if (car == null) car = transform;
        }

        void Start()
        {
            // Only the authority consumes the LSL feedback stream.
            if (_net != null && _net.IsAuthority)
            {
                try
                {
                    _feedback = new LslFeedbackTransport(streamName);
                    Debug.Log($"[MindX] SharedCarAuthority (host) connected to LSL '{streamName}'.");
                }
                catch (System.Exception e)
                {
                    Debug.LogWarning($"[MindX] Host has no feedback stream yet ({e.Message}). " +
                                     "Car holds until the backend publishes.");
                }
            }
        }

        void Update()
        {
            if (_net == null) return;

            if (_net.IsAuthority)
                DriveAndPublish();
            else
                FollowReplicated();

            ApplyAudio(_level); // audio tracks the effective level on every peer
        }

        private void DriveAndPublish()
        {
            if (_feedback != null && _feedback.TryGetLatest(out var s))
            {
                // Route: shared sample drives every car; individual only its owner.
                if (s.subjectIndex < 0 || s.subjectIndex == carSubjectIndex)
                {
                    _level = Mathf.Clamp01(s.level);
                    _tLsl = s.tLsl;
                }
            }

            float speed = baseSpeed + maxBonusSpeed * _level;
            car.Translate(Vector3.forward * speed * Time.deltaTime, Space.Self);

            _net.PublishState(new SharedCarState
            {
                position = ToTrackLocalPos(car.position),
                rotation = ToTrackLocalRot(car.rotation),
                level = _level,
                subjectIndex = carSubjectIndex, // -1 if this is the shared hyperscanning car
                tLsl = _tLsl,
            });
        }

        private void FollowReplicated()
        {
            if (!_net.TryGetLatest(out var s)) return;
            _level = s.level;
            car.position = FromTrackLocalPos(s.position);
            car.rotation = FromTrackLocalRot(s.rotation);
        }

        private void ApplyAudio(float level)
        {
            if (engine == null) return;
            engine.pitch = Mathf.Lerp(minPitch, maxPitch, level);
            engine.volume = Mathf.Lerp(0.3f, 1.0f, level);
        }

        // Track-local <-> world helpers. With no track root set, fall back to world
        // space so a single-headset dev scene still works.
        private Vector3 ToTrackLocalPos(Vector3 world) =>
            trackRoot ? trackRoot.InverseTransformPoint(world) : world;
        private Quaternion ToTrackLocalRot(Quaternion world) =>
            trackRoot ? Quaternion.Inverse(trackRoot.rotation) * world : world;
        private Vector3 FromTrackLocalPos(Vector3 local) =>
            trackRoot ? trackRoot.TransformPoint(local) : local;
        private Quaternion FromTrackLocalRot(Quaternion local) =>
            trackRoot ? trackRoot.rotation * local : local;

        void OnDestroy() => _feedback?.Close();
    }
}

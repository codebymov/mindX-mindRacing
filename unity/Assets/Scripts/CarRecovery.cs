// CarRecovery.cs — safety net that keeps a car in view and on the track.
//
// The track's boundary walls already stop a car leaving the road corridor. This
// component covers what walls cannot: a bad spawn, a physics glitch, tunnelling,
// or a fall. A car that leaves the play area is put back at the last pose where it
// was inside the area and standing on something. In a headset a lost car is a
// ruined session, so this is a hard requirement, not polish.

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Teleports a car back to its last safe pose when it leaves the play area.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class CarRecovery : MonoBehaviour
    {
        [Tooltip("Track root whose renderers define the play area.")]
        [SerializeField] private Transform trackRoot;

        [Tooltip("Extra distance in metres past the track bounds before recovering.")]
        [SerializeField] private float margin = 5f;

        [Tooltip("Seconds between checks.")]
        [SerializeField] private float checkInterval = 0.25f;

        [Tooltip("How far below the car to look for ground when saving a safe pose.")]
        [SerializeField] private float groundProbe = 2f;

        private Rigidbody _rb;
        private Bounds _area;
        private bool _hasArea;
        private Pose _lastSafe;
        private float _nextCheck;

        /// <summary>
        /// Gets the number of times this car has been recovered.
        /// </summary>
        public int RecoveryCount { get; private set; }

        /// <summary>
        /// Gets or sets the track root that defines the play area.
        /// </summary>
        public Transform TrackRoot
        {
            get => trackRoot;
            set => trackRoot = value;
        }

        /// <summary>
        /// Tells whether a position is outside the play area.
        /// </summary>
        /// <param name="area">Play area bounds, already including any margin.</param>
        /// <param name="position">World position to test.</param>
        /// <returns>True when the position is outside the area on any axis.</returns>
        public static bool IsOutside(Bounds area, Vector3 position)
        {
            return !area.Contains(position);
        }

        /// <summary>
        /// Builds the play area from every renderer under a root.
        /// </summary>
        /// <param name="root">The track root.</param>
        /// <param name="extraMargin">Metres added on every side.</param>
        /// <param name="area">The resulting bounds.</param>
        /// <returns>True when the root has at least one renderer.</returns>
        public static bool TryBuildArea(Transform root, float extraMargin, out Bounds area)
        {
            area = default;
            if (root == null)
            {
                return false;
            }

            var renderers = root.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0)
            {
                return false;
            }

            area = renderers[0].bounds;
            for (int i = 1; i < renderers.Length; i++)
            {
                area.Encapsulate(renderers[i].bounds);
            }

            area.Expand(extraMargin * 2f);
            return true;
        }

        private void Start()
        {
            _rb = GetComponent<Rigidbody>();
            _hasArea = TryBuildArea(trackRoot, margin, out _area);
            _lastSafe = new Pose(transform.position, transform.rotation);
            if (!_hasArea)
            {
                Debug.LogWarning("[MindX] CarRecovery has no track root; recovery is disabled.", this);
            }
        }

        private void FixedUpdate()
        {
            if (!_hasArea || Time.time < _nextCheck)
            {
                return;
            }

            _nextCheck = Time.time + checkInterval;

            if (IsOutside(_area, transform.position))
            {
                Recover();
            }
            else if (Physics.Raycast(transform.position + (Vector3.up * 0.3f), Vector3.down, groundProbe))
            {
                _lastSafe = new Pose(transform.position, transform.rotation);
            }
        }

        private void Recover()
        {
            RecoveryCount++;
            _rb.linearVelocity = Vector3.zero;
            _rb.angularVelocity = Vector3.zero;
            _rb.position = _lastSafe.position;
            _rb.rotation = _lastSafe.rotation;
            transform.SetPositionAndRotation(_lastSafe.position, _lastSafe.rotation);
            Debug.LogWarning($"[MindX] {name} left the play area and was put back (recovery #{RecoveryCount}).", this);
        }
    }
}

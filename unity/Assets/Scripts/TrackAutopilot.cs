// TrackAutopilot.cs — a wall-following driver so a car stays on the track.
//
// Demo-only steering: the car measures its distance to the boundary walls with a
// few rays and steers to hold a lane and to turn into corners. It needs no path
// data, so it works on any enclosed track. Speed is NOT decided here: it comes from
// the neurofeedback level through CarDriver, so the autopilot only chooses the line.
// Each car gets its own lane and a slow lateral weave, so the cars take visibly
// different lines without ever crossing.

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Steers a car along an enclosed track by following its walls.
    /// </summary>
    public class TrackAutopilot : MonoBehaviour, ICarInput
    {
        private static readonly RaycastHit[] Hits = new RaycastHit[16];

        [Header("Line")]
        [Tooltip("Base lane in metres from the road centre; positive is to the right of travel.")]
        [SerializeField] private float laneOffset;

        [Tooltip("Amplitude in metres of the slow lateral weave around the lane.")]
        [SerializeField] private float weaveAmplitude = 1f;

        [Tooltip("Period in seconds of the lateral weave.")]
        [SerializeField] private float weavePeriod = 25f;

        [Tooltip("Phase of the weave in radians.")]
        [SerializeField] private float weavePhase;

        [Header("Steering")]
        [Tooltip("Steering per metre of lateral error.")]
        [SerializeField] private float centreGain = 0.18f;

        [Tooltip("Steering added when a corner is ahead.")]
        [SerializeField] private float cornerGain = 1.2f;

        [Tooltip("Distance ahead in metres at which corners start to matter.")]
        [SerializeField] private float lookAhead = 40f;

        [Tooltip("Longest ray in metres.")]
        [SerializeField] private float range = 55f;

        [Tooltip("Height of the rays above the car pivot.")]
        [SerializeField] private float rayHeight = 1f;

        [Tooltip("Angle in degrees of the two forward-diagonal rays.")]
        [SerializeField] private float diagonalAngle = 35f;

        private readonly System.Collections.Generic.List<Vector3> _wallHitPositions =
            new System.Collections.Generic.List<Vector3>();

        private float _steer;
        private float _sumLateral;
        private float _sumTarget;

        /// <summary>
        /// Gets the number of times the car touched a boundary wall.
        /// </summary>
        public int WallHits { get; private set; }

        /// <summary>
        /// Gets where the car was at each wall contact (the first 50), for diagnosis.
        /// </summary>
        public System.Collections.Generic.IReadOnlyList<Vector3> WallHitPositions => _wallHitPositions;

        /// <summary>
        /// Gets the throttle command; always full, as speed comes from the feedback level.
        /// </summary>
        public float Throttle => 1f;

        /// <summary>
        /// Gets the steering command in [-1, 1].
        /// </summary>
        public float Steer => _steer;

        /// <summary>
        /// Gets or sets the base lane in metres from the road centre (positive is right).
        /// </summary>
        public float LaneOffset
        {
            get => laneOffset;
            set => laneOffset = value;
        }

        /// <summary>
        /// Sets the lateral weave.
        /// </summary>
        /// <param name="amplitude">Amplitude in metres.</param>
        /// <param name="period">Period in seconds.</param>
        /// <param name="phase">Phase in radians.</param>
        public void SetWeave(float amplitude, float period, float phase)
        {
            weaveAmplitude = amplitude;
            weavePeriod = Mathf.Max(0.1f, period);
            weavePhase = phase;
        }

        /// <summary>
        /// Computes the steering command from the five wall distances.
        /// </summary>
        /// <param name="left">Distance to the wall on the left, in metres.</param>
        /// <param name="right">Distance to the wall on the right, in metres.</param>
        /// <param name="frontLeft">Distance along the forward-left diagonal.</param>
        /// <param name="frontRight">Distance along the forward-right diagonal.</param>
        /// <param name="forward">Distance straight ahead.</param>
        /// <param name="lane">Wanted lateral position; positive is right of the centre line.</param>
        /// <param name="centreGain">Steering per metre of lateral error.</param>
        /// <param name="cornerGain">Steering added when a corner is ahead.</param>
        /// <param name="lookAhead">Distance ahead at which corners start to matter.</param>
        /// <returns>Steering in [-1, 1]; positive turns right.</returns>
        public static float ComputeSteer(
            float left,
            float right,
            float frontLeft,
            float frontRight,
            float forward,
            float lane,
            float centreGain,
            float cornerGain,
            float lookAhead)
        {
            // How close a corner is: 0 on a straight, 1 when the wall ahead is touching.
            float urgency = Mathf.Clamp01(1f - (forward / Mathf.Max(lookAhead, 0.01f)));

            // Positive when the car is right of the centre line (closer to the right wall).
            // In a bend the side rays no longer measure the offset from the road centre, so
            // this correction fades as a corner approaches and the corner term takes over.
            float lateral = (left - right) * 0.5f;
            float steer = -centreGain * (lateral - lane) * (1f - (0.85f * urgency));

            // Turn toward the side with more room, more strongly the nearer the wall ahead.
            float room = frontLeft + frontRight;
            if (room > 0.01f)
            {
                steer += cornerGain * urgency * ((frontRight - frontLeft) / room);
            }

            return Mathf.Clamp(steer, -1f, 1f);
        }

        private void Update()
        {
            float weave = weaveAmplitude * Mathf.Sin((2f * Mathf.PI * Time.time / weavePeriod) + weavePhase);
            Vector3 forward = transform.forward;
            Vector3 right = transform.right;
            Vector3 frontRight = Quaternion.AngleAxis(diagonalAngle, Vector3.up) * forward;
            Vector3 frontLeft = Quaternion.AngleAxis(-diagonalAngle, Vector3.up) * forward;

            float distLeft = Probe(-right);
            float distRight = Probe(right);
            float distForward = Probe(forward);
            float targetLane = laneOffset + weave;

            _steer = ComputeSteer(
                distLeft,
                distRight,
                Probe(frontLeft),
                Probe(frontRight),
                distForward,
                targetLane,
                centreGain,
                cornerGain,
                lookAhead);

            // Diagnostics: on straights (no corner within ~90% of the look-ahead) record
            // where the car really is against where it was told to be.
            if (distForward > lookAhead * 0.9f)
            {
                StraightSamples++;
                _sumLateral += (distLeft - distRight) * 0.5f;
                _sumTarget += targetLane;
            }
        }

        /// <summary>
        /// Gets the number of per-frame samples taken on straight sections.
        /// </summary>
        public int StraightSamples { get; private set; }

        /// <summary>
        /// Gets the mean measured lateral offset on straights (positive is right of centre).
        /// </summary>
        public float StraightLateralMean => StraightSamples > 0 ? _sumLateral / StraightSamples : 0f;

        /// <summary>
        /// Gets the mean target lane on straights, for comparison with the measured offset.
        /// </summary>
        public float StraightTargetMean => StraightSamples > 0 ? _sumTarget / StraightSamples : 0f;

        private float Probe(Vector3 direction)
        {
            Vector3 origin = transform.position + (Vector3.up * rayHeight);
            int count = Physics.RaycastNonAlloc(origin, direction, Hits, range, ~0, QueryTriggerInteraction.Ignore);
            float nearest = range;
            for (int i = 0; i < count; i++)
            {
                // Measure walls only. Anything with a Rigidbody is a car (this one or the
                // other): treating the other car as a wall made the lane estimate jump when
                // the cars ran abreast and steered a car into the wall.
                if (Hits[i].rigidbody != null || Hits[i].collider.transform.IsChildOf(transform))
                {
                    continue;
                }

                nearest = Mathf.Min(nearest, Hits[i].distance);
            }

            return nearest;
        }

        private void OnCollisionEnter(Collision collision)
        {
            if (collision.collider.name.StartsWith("Cube", System.StringComparison.Ordinal))
            {
                WallHits++;
                if (_wallHitPositions.Count < 50)
                {
                    _wallHitPositions.Add(transform.position);
                }
            }
        }
    }
}

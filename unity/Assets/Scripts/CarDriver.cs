using UnityEngine;

namespace MindX
{
    /// Moves a car from whatever ICarInput is on the same GameObject (keyboard,
    /// neurofeedback, network). The movement math mirrors XRCarController.ApplyDrive
    /// so behaviour is identical regardless of the input source. Swap the ICarInput
    /// component to change WHO/WHAT drives the car; the driver never changes.
    [RequireComponent(typeof(Rigidbody))]
    public class CarDriver : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float acceleration = 5f;
        [SerializeField] private float maxSpeed = 20f;
        [SerializeField] private float turnSpeed = 50f;
        [SerializeField] private float brakePower = 10f;

        [Header("Neurofeedback (optional)")]
        [Tooltip("When set, speed follows the feedback level (D7) and the input source only steers.")]
        [SerializeField] private FeedbackReceiver levelSource;

        private Rigidbody _rb;
        private ICarInput _input;
        private float _currentSpeed;

        /// <summary>
        /// Gets or sets the feedback source that drives speed. Null keeps the
        /// accel/brake keyboard model.
        /// </summary>
        public FeedbackReceiver LevelSource
        {
            get => levelSource;
            set => levelSource = value;
        }

        void Awake()
        {
            _rb = GetComponent<Rigidbody>();
            _input = GetComponent<ICarInput>(); // Unity resolves interfaces on the GameObject
        }

        /// Allow code (e.g. a spawner) to inject the input source explicitly.
        public void SetInput(ICarInput source) => _input = source;

        void Update()
        {
            if (_input == null) return;

            float throttle = Mathf.Clamp(_input.Throttle, -1f, 1f);
            float steer = Mathf.Clamp(_input.Steer, -1f, 1f);

            if (levelSource != null)
                _currentSpeed = Mathf.MoveTowards(_currentSpeed, levelSource.TargetSpeed, acceleration * 2f * Time.deltaTime);
            else if (throttle > 0.1f)
                _currentSpeed = Mathf.Min(_currentSpeed + acceleration * throttle * Time.deltaTime, maxSpeed);
            else if (throttle < -0.1f)
                _currentSpeed = Mathf.Max(_currentSpeed - brakePower * Mathf.Abs(throttle) * Time.deltaTime, 0f);
            else
                _currentSpeed = Mathf.MoveTowards(_currentSpeed, 0f, brakePower * 0.5f * Time.deltaTime);

            // Drive along the ground plane only; keep the vertical component so
            // gravity and wheel suspension still act on the car.
            Vector3 flatForward = Vector3.ProjectOnPlane(transform.forward, Vector3.up).normalized;
            Vector3 velocity = flatForward * _currentSpeed;
            velocity.y = _rb.linearVelocity.y;
            _rb.linearVelocity = velocity;

            if (Mathf.Abs(steer) > 0.1f && _currentSpeed > 0.5f)
                transform.Rotate(Vector3.up, steer * turnSpeed * Time.deltaTime);
        }
    }
}

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

        private Rigidbody _rb;
        private ICarInput _input;
        private float _currentSpeed;

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

            if (throttle > 0.1f)
                _currentSpeed = Mathf.Min(_currentSpeed + acceleration * throttle * Time.deltaTime, maxSpeed);
            else if (throttle < -0.1f)
                _currentSpeed = Mathf.Max(_currentSpeed - brakePower * Mathf.Abs(throttle) * Time.deltaTime, 0f);
            else
                _currentSpeed = Mathf.MoveTowards(_currentSpeed, 0f, brakePower * 0.5f * Time.deltaTime);

            _rb.velocity = transform.forward * _currentSpeed;

            if (Mathf.Abs(steer) > 0.1f && _currentSpeed > 0.5f)
                transform.Rotate(Vector3.up, steer * turnSpeed * Time.deltaTime);
        }
    }
}

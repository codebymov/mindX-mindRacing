using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// Quest 2 / XR car input. Attach to a car prefab from
/// Assets/CarControll/Prefabs (With Colliders)/ and disable CarController on the same object.
/// Wire the Drive action to the left thumbstick in the Input Actions asset, or assign it in the Inspector.
/// </summary>
[RequireComponent(typeof(Rigidbody))]
public class XRCarController : MonoBehaviour
{
    [Header("Movement")]
    public float acceleration = 5f;
    public float maxSpeed = 20f;
    public float turnSpeed = 50f;
    public float brakePower = 10f;

    [Header("Input (assign left thumbstick Vector2 action)")]
    public InputActionReference driveAction;

    private Rigidbody rb;
    private float currentSpeed;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
    }

    void OnEnable()
    {
        driveAction?.action?.Enable();
    }

    void OnDisable()
    {
        driveAction?.action?.Disable();
    }

    void Update()
    {
        Vector2 input = driveAction != null ? driveAction.action.ReadValue<Vector2>() : Vector2.zero;
        ApplyDrive(input.y, input.x);
    }

    void ApplyDrive(float throttle, float steer)
    {
        if (throttle > 0.1f)
        {
            currentSpeed = Mathf.Min(currentSpeed + acceleration * throttle * Time.deltaTime, maxSpeed);
        }
        else if (throttle < -0.1f)
        {
            currentSpeed = Mathf.Max(currentSpeed - brakePower * Mathf.Abs(throttle) * Time.deltaTime, 0f);
        }

        rb.velocity = transform.forward * currentSpeed;

        if (Mathf.Abs(steer) > 0.1f && currentSpeed > 0.5f)
        {
            transform.Rotate(Vector3.up, steer * turnSpeed * Time.deltaTime);
        }
    }
}

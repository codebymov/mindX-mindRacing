using UnityEngine;

public class CarController : MonoBehaviour
{
    public float acceleration = 5f;
    public float maxSpeed = 20f;
    public float turnSpeed = 50f;
    public float brakePower = 10f;
    private float currentSpeed = 0f;
    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void Update()
    {
        HandleInput();
    }

    void HandleInput()
    {
        // Forward and backward movement
        if (Input.GetKey(KeyCode.W))
        {
            Accelerate();
        }
        else if (Input.GetKey(KeyCode.S))
        {
            Brake();
        }

        // Left and right turning
        if (Input.GetKey(KeyCode.A))
        {
            TurnLeft();
        }
        else if (Input.GetKey(KeyCode.D))
        {
            TurnRight();
        }
    }

    void Accelerate()
    {
        if (currentSpeed < maxSpeed)
        {
            currentSpeed += acceleration * Time.deltaTime;
        }
        rb.velocity = transform.forward * currentSpeed;
    }

    void Brake()
    {
        if (currentSpeed > 0)
        {
            currentSpeed -= brakePower * Time.deltaTime;
        }
        rb.velocity = transform.forward * currentSpeed;
    }

    void TurnLeft()
    {
        transform.Rotate(Vector3.up, -turnSpeed * Time.deltaTime);
    }

    void TurnRight()
    {
        transform.Rotate(Vector3.up, turnSpeed * Time.deltaTime);
    }
}

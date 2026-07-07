// ColocationRegistration.cs — deterministic manual co-location (D11).
//
// The only co-location method that works across the D6 headset set (Vive / Quest
// Pro / Varjo) in 2026: each headset independently registers the SAME physical
// reference, and inverts it to a shared origin. That origin is the D7 track root,
// so once both headsets register against the same real-world marks, the shared
// car/track render at the same physical place for both players.
//
// Two-point registration (origin + forward), captured with a tracked controller:
//   1. Point the controller at a marked physical point (the track origin) and
//      press the trigger  -> captures the origin.
//   2. Point at a second mark along the desired +Z (forward) and press again
//      -> captures the forward direction; yaw is derived from origin -> forward.
// Height is dropped to the origin's floor level; roll/pitch are ignored (the room
// floor is level). Deterministic, reproducible, no cloud, no vendor SDK.
//
// This is transport-agnostic (no Ubiq/LSL dependency) and uses only core
// UnityEngine.XR controller tracking, which every OpenXR runtime provides.

using System;
using UnityEngine;
using UnityEngine.XR;

namespace MindX
{
    public class ColocationRegistration : MonoBehaviour
    {
        [Tooltip("The track root to place = the shared co-located origin (D7/D11).")]
        [SerializeField] private Transform trackRoot;
        [Tooltip("Which hand registers the points.")]
        [SerializeField] private XRNode controllerNode = XRNode.RightHand;

        /// Fired once both points are captured and the track root is placed.
        public event Action Registered;

        public bool IsRegistered { get; private set; }

        private bool _haveOrigin;
        private Vector3 _origin;
        private bool _triggerWasDown;

        void Update()
        {
            InputDevice device = InputDevices.GetDeviceAtXRNode(controllerNode);
            if (!device.isValid) return;

            device.TryGetFeatureValue(CommonUsages.triggerButton, out bool triggerDown);
            // Rising edge = one deliberate capture per press.
            if (triggerDown && !_triggerWasDown &&
                device.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 pos))
            {
                CapturePoint(pos);
            }
            _triggerWasDown = triggerDown;
        }

        /// Capture the current controller tip position as the next registration
        /// point. Exposed so a calibration UI or a test can drive it directly.
        public void CapturePoint(Vector3 worldPoint)
        {
            if (!_haveOrigin)
            {
                _origin = worldPoint;
                _haveOrigin = true;
                Debug.Log("[MindX] Co-location: origin captured; now mark the forward point.");
                return;
            }

            // Second point: derive yaw from origin -> forward on the horizontal plane.
            Vector3 forward = worldPoint - _origin;
            forward.y = 0f;
            if (forward.sqrMagnitude < 1e-4f)
            {
                Debug.LogWarning("[MindX] Co-location: forward point too close to origin; retry.");
                return;
            }

            Quaternion rotation = Quaternion.LookRotation(forward.normalized, Vector3.up);
            if (trackRoot != null)
                trackRoot.SetPositionAndRotation(_origin, rotation);

            IsRegistered = true;
            _haveOrigin = false; // allow re-registration if needed
            Debug.Log($"[MindX] Co-location registered: origin={_origin}, yaw set from forward mark.");
            Registered?.Invoke();
        }

        /// Clear the registration to start over (e.g. a fresh session). Named to
        /// avoid Unity's built-in Reset() editor message.
        public void ResetRegistration()
        {
            IsRegistered = false;
            _haveOrigin = false;
        }
    }
}

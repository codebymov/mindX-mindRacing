using UnityEngine;
using UnityEngine.InputSystem;

namespace MindX
{
    /// Dev / test car input from the keyboard. Lets two cars be driven locally on
    /// one machine (split-screen) before networking and neurofeedback driving
    /// exist. This is a stand-in for the real driver — the game is NOT meant to be
    /// played by keyboard; it exists to validate the two-car + camera + track setup
    /// without a headset or hardware. Pick a scheme per car: P1 = WASD, P2 = Arrows.
    public class KeyboardCarInput : MonoBehaviour, ICarInput
    {
        public enum Scheme { WASD, Arrows }

        [SerializeField] private Scheme scheme = Scheme.WASD;

        public Scheme InputScheme { get => scheme; set => scheme = value; }

        private (Key fwd, Key back, Key left, Key right) Keys => scheme == Scheme.Arrows
            ? (Key.UpArrow, Key.DownArrow, Key.LeftArrow, Key.RightArrow)
            : (Key.W, Key.S, Key.A, Key.D);

        public float Throttle
        {
            get
            {
                var k = Keyboard.current;
                if (k == null) return 0f;
                var keys = Keys;
                return (k[keys.fwd].isPressed ? 1f : 0f) - (k[keys.back].isPressed ? 1f : 0f);
            }
        }

        public float Steer
        {
            get
            {
                var k = Keyboard.current;
                if (k == null) return 0f;
                var keys = Keys;
                return (k[keys.right].isPressed ? 1f : 0f) - (k[keys.left].isPressed ? 1f : 0f);
            }
        }
    }
}

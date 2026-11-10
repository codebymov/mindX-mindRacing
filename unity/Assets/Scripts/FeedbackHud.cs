// FeedbackHud.cs — on-screen readout of the LSL feedback level, for demos.
//
// Shows whether the LSL stream is connected and the live INS-driven level and
// speed. Display only: it never branches on sample.mode (sham must stay
// indistinguishable from real).

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Draws the connection state, level bar and speed of one or more
    /// <see cref="FeedbackReceiver"/>s in the top-left corner.
    /// </summary>
    public class FeedbackHud : MonoBehaviour
    {
        [SerializeField] private FeedbackReceiver[] receivers;

        private GUIStyle _style;

        /// <summary>
        /// Sets the receivers to display.
        /// </summary>
        /// <param name="source">The receivers, one per car.</param>
        public void SetReceivers(FeedbackReceiver[] source) => receivers = source;

        void OnGUI()
        {
            if (receivers == null || receivers.Length == 0)
                return;

            if (_style == null)
            {
                _style = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold };
                _style.normal.textColor = Color.white;
            }

            const float width = 320f;
            GUI.Box(new Rect(10f, 10f, width, 36f + (receivers.Length * 30f)), GUIContent.none);

            bool connected = receivers[0] != null && receivers[0].IsConnected;
            GUI.Label(
                new Rect(20f, 14f, width, 28f),
                connected ? "LSL: connected" : "LSL: waiting for stream...",
                _style);

            for (int i = 0; i < receivers.Length; i++)
            {
                if (receivers[i] == null)
                    continue;

                float y = 44f + (i * 30f);
                float level = receivers[i].Level;
                GUI.Label(
                    new Rect(20f, y, width, 28f),
                    $"Car {i + 1}  INS {level:0.00}  {receivers[i].TargetSpeed:0.0} m/s",
                    _style);
                GUI.Box(new Rect(20f, y + 24f, (width - 20f) * Mathf.Clamp01(level), 4f), GUIContent.none);
            }
        }
    }
}

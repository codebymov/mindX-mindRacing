// FeedbackHud.cs — on-screen readout of the LSL feedback signal, for demos.
//
// Shows the connection state, the live INS-driven level and speed per car, and a
// rolling curve of the level over the session. The curve is the participant-facing
// view: it draws one uniform line whatever the signal source, so sham stays
// indistinguishable from real.
//
// The operator overlay (F1, hidden by default) is for the presenter or
// experimenter only: it shows the signal source (real or sham), the raw INS and
// tints the sham stretches of the curve. It reads the source for display; nothing
// in the game depends on it.

using UnityEngine;
using UnityEngine.InputSystem;

namespace MindX
{
    /// <summary>
    /// Draws the connection state, level bars, a live level curve and an optional
    /// operator overlay for one or more <see cref="FeedbackReceiver"/>s.
    /// </summary>
    public class FeedbackHud : MonoBehaviour
    {
        private const string ShamMode = "sham";

        [SerializeField] private FeedbackReceiver[] receivers;
        [SerializeField] private string caption;

        private readonly LevelHistory _history = new LevelHistory(320, 1f);
        private GUIStyle _style;
        private GUIStyle _small;
        private bool _operatorView;

        /// <summary>
        /// Gets or sets a line of text drawn along the bottom of the screen.
        /// </summary>
        public string Caption
        {
            get => caption;
            set => caption = value;
        }

        /// <summary>
        /// Gets or sets a value indicating whether the operator overlay is shown.
        /// Toggled with F1; hidden by default and never meant for participants.
        /// </summary>
        public bool OperatorView
        {
            get => _operatorView;
            set => _operatorView = value;
        }

        /// <summary>
        /// Gets the rolling level history drawn as the curve.
        /// </summary>
        public LevelHistory History => _history;

        /// <summary>
        /// Sets the receivers to display.
        /// </summary>
        /// <param name="source">The receivers, one per car.</param>
        public void SetReceivers(FeedbackReceiver[] source) => receivers = source;

        private void Update()
        {
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null && keyboard.f1Key.wasPressedThisFrame)
            {
                _operatorView = !_operatorView;
            }

            if (receivers != null && receivers.Length > 0 && receivers[0] != null)
            {
                bool sham = string.Equals(receivers[0].LastMode, ShamMode, System.StringComparison.Ordinal);
                _history.Record(Time.time, receivers[0].Level, sham);
            }
        }

        private void OnGUI()
        {
            if (receivers == null || receivers.Length == 0)
            {
                return;
            }

            if (_style == null)
            {
                _style = new GUIStyle(GUI.skin.label) { fontSize = 18, fontStyle = FontStyle.Bold };
                _style.normal.textColor = Color.white;
                _small = new GUIStyle(GUI.skin.label) { fontSize = 14 };
                _small.normal.textColor = Color.white;
            }

            bool hasCaption = !string.IsNullOrEmpty(caption);
            if (hasCaption)
            {
                GUI.Box(new Rect(10f, Screen.height - 44f, Screen.width - 20f, 34f), GUIContent.none);
                GUI.Label(new Rect(20f, Screen.height - 40f, Screen.width - 40f, 28f), caption, _style);
            }

            DrawStatus();
            DrawCurve(hasCaption ? 54f : 10f);
            if (_operatorView)
            {
                DrawOperatorOverlay();
            }
        }

        private void DrawStatus()
        {
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
                {
                    continue;
                }

                float y = 44f + (i * 30f);
                float level = receivers[i].Level;
                GUI.Label(
                    new Rect(20f, y, width, 28f),
                    $"Car {i + 1}  INS {level:0.00}  {receivers[i].TargetSpeed:0.0} m/s",
                    _style);
                GUI.Box(new Rect(20f, y + 24f, (width - 20f) * Mathf.Clamp01(level), 4f), GUIContent.none);
            }
        }

        private void DrawCurve(float bottomMargin)
        {
            float width = Mathf.Min(660f, Screen.width - 20f);
            const float height = 130f;
            var panel = new Rect(10f, Screen.height - bottomMargin - height, width, height);
            GUI.Box(panel, GUIContent.none);

            float now = receivers[0] != null ? receivers[0].Level : 0f;
            GUI.Label(
                new Rect(panel.x + 8f, panel.y + 2f, panel.width - 16f, 22f),
                $"INS over the session (baseline-corrected)   now {now:0.00}",
                _small);

            float plotLeft = panel.x + 10f;
            float plotBottom = panel.yMax - 8f;
            float plotHeight = height - 38f;
            float plotWidth = panel.width - 20f;
            float columnWidth = plotWidth / _history.Capacity;

            Color previous = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, 0.25f);
            GUI.DrawTexture(new Rect(plotLeft, plotBottom - (plotHeight * 0.5f), plotWidth, 1f), Texture2D.whiteTexture);
            GUI.DrawTexture(new Rect(plotLeft, plotBottom, plotWidth, 1f), Texture2D.whiteTexture);

            for (int i = 0; i < _history.Count; i++)
            {
                float h = Mathf.Max(1f, Mathf.Clamp01(_history[i]) * plotHeight);

                // One uniform colour for participants; only the operator view tints sham.
                GUI.color = _operatorView && _history.Flag(i)
                    ? new Color(1f, 0.6f, 0.15f, 0.95f)
                    : new Color(0.3f, 0.85f, 1f, 0.95f);
                GUI.DrawTexture(
                    new Rect(plotLeft + (i * columnWidth), plotBottom - h, Mathf.Max(1f, columnWidth), h),
                    Texture2D.whiteTexture);
            }

            GUI.color = previous;
        }

        private void DrawOperatorOverlay()
        {
            const float width = 320f;
            var box = new Rect(Screen.width - width - 10f, 10f, width, 100f);
            GUI.Box(box, GUIContent.none);

            FeedbackReceiver first = receivers[0];
            string source = first != null && first.LastMode != null ? first.LastMode.ToUpperInvariant() : "-";
            bool sham = string.Equals(source, "SHAM", System.StringComparison.Ordinal);

            GUI.Label(new Rect(box.x + 10f, box.y + 4f, width - 20f, 22f), "OPERATOR VIEW  (F1 hides)", _small);

            Color previous = GUI.color;
            GUI.color = sham ? new Color(1f, 0.6f, 0.15f) : new Color(0.5f, 1f, 0.6f);
            GUI.Label(new Rect(box.x + 10f, box.y + 28f, width - 20f, 28f), $"Source: {source}", _style);
            GUI.color = previous;

            float raw = first != null ? first.RawIns : 0f;
            GUI.Label(new Rect(box.x + 10f, box.y + 62f, width - 20f, 22f), $"raw INS: {raw:0.000}", _small);
        }
    }
}

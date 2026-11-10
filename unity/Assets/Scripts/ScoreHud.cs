// ScoreHud.cs — each player's points, drawn in that player's own view.
//
// Every entry pairs a car's score with the camera that shows it; the panel is drawn
// in the corner of that camera's viewport, so with split-screen each player sees
// their own score in their own view. A team line shows the combined coins, which is
// the shared challenge in hyperscanning (one joint signal drives both cars).

using System.Collections.Generic;
using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Draws a score panel in the viewport of each player's camera.
    /// </summary>
    public class ScoreHud : MonoBehaviour
    {
        private const float FlashSeconds = 1.4f;

        // Serialized, so the pairs survive saving the scene and entering Play mode.
        [SerializeField] private List<Entry> _entries = new List<Entry>();
        private GUIStyle _big;
        private GUIStyle _small;
        private GUIStyle _flash;

        /// <summary>
        /// Gets the number of players shown.
        /// </summary>
        public int EntryCount => _entries.Count;

        /// <summary>
        /// Removes every entry.
        /// </summary>
        public void Clear() => _entries.Clear();

        /// <summary>
        /// Adds a player's score and the camera that shows their view.
        /// </summary>
        /// <param name="score">The player's score.</param>
        /// <param name="view">The camera of that player's view.</param>
        public void Add(CarScore score, Camera view)
        {
            _entries.Add(new Entry { Score = score, View = view });
        }

        private void OnGUI()
        {
            if (_entries.Count == 0)
            {
                return;
            }

            if (_big == null)
            {
                _big = new GUIStyle(GUI.skin.label) { fontSize = 26, fontStyle = FontStyle.Bold };
                _big.normal.textColor = Color.white;
                _small = new GUIStyle(GUI.skin.label) { fontSize = 15 };
                _small.normal.textColor = Color.white;
                _flash = new GUIStyle(GUI.skin.label) { fontSize = 30, fontStyle = FontStyle.Bold, alignment = TextAnchor.MiddleCenter };
            }

            int team = 0;
            float now = Time.time;
            foreach (Entry e in _entries)
            {
                if (e.Score == null)
                {
                    continue;
                }

                team += e.Score.Coins;
                Rect view = ViewRect(e.View);
                DrawPlayer(e.Score, view, now);
            }

            DrawTeam(team);
        }

        private static Rect ViewRect(Camera cam)
        {
            if (cam == null)
            {
                return new Rect(0f, 0f, Screen.width, Screen.height);
            }

            // Camera pixel rects have their origin at the bottom left; GUI at the top left.
            Rect p = cam.pixelRect;
            return new Rect(p.x, Screen.height - p.yMax, p.width, p.height);
        }

        private void DrawPlayer(CarScore score, Rect view, float now)
        {
            var panel = new Rect(view.x + 12f, view.y + 116f, 270f, 92f);
            GUI.Box(panel, GUIContent.none);
            GUI.Label(new Rect(panel.x + 10f, panel.y + 2f, 250f, 34f), $"{score.PlayerName}   {score.Points} pts", _big);
            GUI.Label(
                new Rect(panel.x + 10f, panel.y + 38f, 250f, 22f),
                $"coins {score.Coins}   ({score.CoinsPerMinute(now):0} / min)",
                _small);
            GUI.Label(new Rect(panel.x + 10f, panel.y + 60f, 250f, 22f), $"crashes {score.Crashes}", _small);

            float age = now - score.LastEventTime;
            if (age >= 0f && age < FlashSeconds && score.LastEvent.Length > 0)
            {
                Color previous = GUI.color;
                GUI.color = score.LastEventWasPenalty ? new Color(1f, 0.3f, 0.3f, 1f - (age / FlashSeconds)) : new Color(1f, 0.9f, 0.2f, 1f - (age / FlashSeconds));
                GUI.Label(new Rect(view.x, view.y + (view.height * 0.3f), view.width, 50f), score.LastEvent, _flash);
                GUI.color = previous;
            }
        }

        private void DrawTeam(int teamCoins)
        {
            var panel = new Rect((Screen.width * 0.5f) - 110f, 10f, 220f, 34f);
            GUI.Box(panel, GUIContent.none);
            GUI.Label(new Rect(panel.x + 10f, panel.y + 4f, 210f, 26f), $"TEAM coins: {teamCoins}", _small);
        }

        [System.Serializable]
        private struct Entry
        {
            public CarScore Score;
            public Camera View;
        }
    }
}

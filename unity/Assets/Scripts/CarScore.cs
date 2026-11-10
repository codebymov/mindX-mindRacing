// CarScore.cs — one player's points: coins collected, crashes penalised.
//
// Coins add points; hitting the other car subtracts points from BOTH cars (neither is
// judged at fault). A short cooldown stops one crash being counted every physics
// contact. The score may go below zero so a penalty is always visible.

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Keeps a car's points, coin count and crash count.
    /// </summary>
    public class CarScore : MonoBehaviour
    {
        [SerializeField] private string playerName = "Player";
        [SerializeField] private int coinPoints = 10;
        [SerializeField] private int crashPenalty = 5;
        [SerializeField] private float crashCooldown = 1.5f;

        private readonly System.Collections.Generic.Queue<float> _coinTimes =
            new System.Collections.Generic.Queue<float>();

        private float _lastCrashTime = -999f;

        /// <summary>
        /// Gets the coin collection rate over a recent window.
        /// </summary>
        /// <param name="now">Current time in seconds.</param>
        /// <param name="windowSeconds">Length of the window in seconds.</param>
        /// <returns>Coins per minute over the window; faster driving raises it.</returns>
        public float CoinsPerMinute(float now, float windowSeconds = 30f)
        {
            while (_coinTimes.Count > 0 && now - _coinTimes.Peek() > windowSeconds)
            {
                _coinTimes.Dequeue();
            }

            return _coinTimes.Count * 60f / Mathf.Max(windowSeconds, 1f);
        }

        /// <summary>
        /// Gets or sets the name shown on the scoreboard.
        /// </summary>
        public string PlayerName
        {
            get => playerName;
            set => playerName = value;
        }

        /// <summary>
        /// Gets the current points (coins minus crash penalties).
        /// </summary>
        public int Points { get; private set; }

        /// <summary>
        /// Gets the number of coins collected.
        /// </summary>
        public int Coins { get; private set; }

        /// <summary>
        /// Gets the number of penalised crashes.
        /// </summary>
        public int Crashes { get; private set; }

        /// <summary>
        /// Gets the text of the latest scoring event, such as "+10" or "CRASH -5".
        /// </summary>
        public string LastEvent { get; private set; } = string.Empty;

        /// <summary>
        /// Gets the time of the latest scoring event, or a large negative value if none.
        /// </summary>
        public float LastEventTime { get; private set; } = -999f;

        /// <summary>
        /// Gets a value indicating whether the latest event was a penalty.
        /// </summary>
        public bool LastEventWasPenalty { get; private set; }

        /// <summary>
        /// Adds the points for one coin.
        /// </summary>
        /// <param name="now">Current time in seconds.</param>
        public void RegisterCoin(float now)
        {
            Coins++;
            _coinTimes.Enqueue(now);
            Points += coinPoints;
            LastEvent = $"+{coinPoints}";
            LastEventTime = now;
            LastEventWasPenalty = false;
        }

        /// <summary>
        /// Subtracts the crash penalty unless this car was penalised very recently.
        /// </summary>
        /// <param name="now">Current time in seconds.</param>
        /// <returns>True when the penalty was applied.</returns>
        public bool RegisterCrash(float now)
        {
            if (now - _lastCrashTime < crashCooldown)
            {
                return false;
            }

            _lastCrashTime = now;
            Crashes++;
            Points -= crashPenalty;
            LastEvent = $"CRASH -{crashPenalty}";
            LastEventTime = now;
            LastEventWasPenalty = true;
            return true;
        }

        private void OnCollisionEnter(Collision collision)
        {
            CarScore other = collision.collider.GetComponentInParent<CarScore>();
            if (other != null && other != this)
            {
                RegisterCrash(Time.time);
            }
        }
    }
}

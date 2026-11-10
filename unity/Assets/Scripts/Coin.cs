// Coin.cs — a collectible that gives its collector points, then respawns.
//
// A trigger collider on the coin root detects the car. Collecting hides the coin
// (its renderers and collider, not the GameObject, so it keeps counting down) and
// it reappears after a delay, so a long session never runs out of coins. The coin
// spins and bobs for visibility.

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// A spinning coin that scores for the first car to touch it.
    /// </summary>
    public class Coin : MonoBehaviour
    {
        [SerializeField] private float respawnSeconds = 20f;
        [SerializeField] private float spinDegreesPerSecond = 180f;
        [SerializeField] private float bobHeight = 0.15f;

        private readonly System.Collections.Generic.Dictionary<string, int> _collectedBy =
            new System.Collections.Generic.Dictionary<string, int>();

        private Renderer[] _renderers;
        private Collider _collider;
        private Vector3 _basePosition;
        private float _collectedAt = -999f;

        /// <summary>
        /// Gets a value indicating whether the coin can be collected.
        /// </summary>
        public bool Available { get; private set; } = true;

        /// <summary>
        /// Gets how many times each player has collected this coin, keyed by player name.
        /// Diagnostic: shows whether the lanes give the players an equal chance.
        /// </summary>
        public System.Collections.Generic.IReadOnlyDictionary<string, int> CollectedBy => _collectedBy;

        /// <summary>
        /// Collects the coin for a car if it is available.
        /// </summary>
        /// <param name="collector">The car's score.</param>
        /// <param name="now">Current time in seconds.</param>
        /// <returns>True when the coin was collected.</returns>
        public bool Collect(CarScore collector, float now)
        {
            if (!Available || collector == null)
            {
                return false;
            }

            collector.RegisterCoin(now);
            _collectedBy.TryGetValue(collector.PlayerName, out int times);
            _collectedBy[collector.PlayerName] = times + 1;
            Available = false;
            _collectedAt = now;
            SetVisible(false);
            return true;
        }

        /// <summary>
        /// Brings the coin back once the respawn delay has passed.
        /// </summary>
        /// <param name="now">Current time in seconds.</param>
        public void UpdateRespawn(float now)
        {
            if (!Available && now - _collectedAt >= respawnSeconds)
            {
                Available = true;
                SetVisible(true);
            }
        }

        private void Awake()
        {
            _renderers = GetComponentsInChildren<Renderer>(true);
            _collider = GetComponent<Collider>();
            _basePosition = transform.position;
        }

        private void Update()
        {
            UpdateRespawn(Time.time);
            if (Available)
            {
                transform.Rotate(Vector3.up, spinDegreesPerSecond * Time.deltaTime, Space.World);
                Vector3 p = _basePosition;
                p.y += Mathf.Sin(Time.time * 2f + (_basePosition.x * 0.1f)) * bobHeight;
                transform.position = p;
            }
        }

        private void OnTriggerEnter(Collider other)
        {
            Collect(other.GetComponentInParent<CarScore>(), Time.time);
        }

        private void SetVisible(bool visible)
        {
            if (_renderers != null)
            {
                foreach (Renderer r in _renderers)
                {
                    r.enabled = visible;
                }
            }

            if (_collider != null)
            {
                _collider.enabled = visible;
            }
        }
    }
}

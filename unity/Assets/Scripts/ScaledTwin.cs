// ScaledTwin.cs — a scaled, visual-only copy of a simulated object.
//
// The game logic and physics stay at 1:1 (metres). For the table-top AR view the
// track and cars are shown as small twins placed from the simulation, so physics
// never runs at miniature scale (where contact offsets and wheel colliders break).
// The same split is what a real table-anchored AR build needs: simulate in metres,
// present anchored to the table.

using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Mirrors a simulated transform onto a scaled copy shown on a table.
    /// </summary>
    public class ScaledTwin : MonoBehaviour
    {
        [SerializeField] private Transform source;
        [SerializeField] private Vector3 simOrigin;
        [SerializeField] private Vector3 tableOrigin;
        [SerializeField] private float scale = 0.0075f;

        /// <summary>
        /// Maps a simulation position to its place on the table.
        /// </summary>
        /// <param name="simPosition">Position in the 1:1 simulation, in metres.</param>
        /// <param name="simOrigin">The simulation point that maps to the table anchor.</param>
        /// <param name="tableOrigin">Table anchor in world space.</param>
        /// <param name="scale">Table metres per simulation metre.</param>
        /// <returns>The world position of the twin.</returns>
        public static Vector3 MapPosition(Vector3 simPosition, Vector3 simOrigin, Vector3 tableOrigin, float scale)
        {
            return tableOrigin + ((simPosition - simOrigin) * scale);
        }

        /// <summary>
        /// Sets what this twin follows and how it is placed.
        /// </summary>
        /// <param name="sourceTransform">The simulated object to follow.</param>
        /// <param name="simulationOrigin">The simulation point that maps to the table anchor.</param>
        /// <param name="tableAnchor">Table anchor in world space.</param>
        /// <param name="tableScale">Table metres per simulation metre.</param>
        public void Configure(Transform sourceTransform, Vector3 simulationOrigin, Vector3 tableAnchor, float tableScale)
        {
            source = sourceTransform;
            simOrigin = simulationOrigin;
            tableOrigin = tableAnchor;
            scale = tableScale;
            Sync();
        }

        /// <summary>
        /// Copies the source pose onto the twin.
        /// </summary>
        public void Sync()
        {
            if (source == null)
            {
                return;
            }

            transform.SetPositionAndRotation(MapPosition(source.position, simOrigin, tableOrigin, scale), source.rotation);
            transform.localScale = Vector3.one * scale;
        }

        private void LateUpdate()
        {
            Sync();
        }
    }
}

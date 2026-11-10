// ScaledTwinTests.cs — the sim-to-table mapping used by the AR table preview.

using NUnit.Framework;
using UnityEngine;

namespace MindX.Tests
{
    public class ScaledTwinTests
    {
        private static readonly Vector3 SimOrigin = new Vector3(-44.8f, 0f, 15f);
        private static readonly Vector3 TableOrigin = new Vector3(1000f, 0.75f, 0f);

        [Test]
        public void MapPosition_SimOrigin_MapsToTheTableAnchor()
        {
            Vector3 p = ScaledTwin.MapPosition(SimOrigin, SimOrigin, TableOrigin, 0.0075f);
            Assert.AreEqual(0f, Vector3.Distance(TableOrigin, p), 1e-4f);
        }

        [Test]
        public void MapPosition_ScalesOffsetsFromTheOrigin()
        {
            Vector3 simPoint = SimOrigin + new Vector3(40f, 2f, -20f);
            Vector3 p = ScaledTwin.MapPosition(simPoint, SimOrigin, TableOrigin, 0.01f);
            Assert.AreEqual(TableOrigin.x + 0.4f, p.x, 1e-4f);
            Assert.AreEqual(TableOrigin.y + 0.02f, p.y, 1e-4f);
            Assert.AreEqual(TableOrigin.z - 0.2f, p.z, 1e-4f);
        }

        [Test]
        public void MapPosition_PreservesRelativeDistancesUpToScale()
        {
            Vector3 a = new Vector3(0f, 0f, 0f);
            Vector3 b = new Vector3(30f, 0f, 40f); // 50 m apart
            float d = Vector3.Distance(
                ScaledTwin.MapPosition(a, SimOrigin, TableOrigin, 0.01f),
                ScaledTwin.MapPosition(b, SimOrigin, TableOrigin, 0.01f));
            Assert.AreEqual(0.5f, d, 1e-4f);
        }

        [Test]
        public void Sync_CopiesRotationAndAppliesScale()
        {
            var src = new GameObject("src");
            var twin = new GameObject("twin");
            try
            {
                src.transform.SetPositionAndRotation(SimOrigin + new Vector3(10f, 0f, 0f), Quaternion.Euler(0f, 90f, 0f));
                var t = twin.AddComponent<ScaledTwin>();
                t.Configure(src.transform, SimOrigin, TableOrigin, 0.01f);

                Assert.AreEqual(TableOrigin.x + 0.1f, twin.transform.position.x, 1e-4f);
                Assert.AreEqual(90f, twin.transform.eulerAngles.y, 1e-3f);
                Assert.AreEqual(0.01f, twin.transform.localScale.x, 1e-6f);
            }
            finally
            {
                Object.DestroyImmediate(src);
                Object.DestroyImmediate(twin);
            }
        }
    }
}

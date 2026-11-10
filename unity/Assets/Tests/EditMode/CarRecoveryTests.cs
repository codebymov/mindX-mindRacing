// CarRecoveryTests.cs — the play-area maths behind the car safety net.
//
// Pure geometry: whether a position counts as lost, and how the area is built from
// a track's renderers. The teleport itself needs physics and is checked in Play mode.

using NUnit.Framework;
using UnityEngine;

namespace MindX.Tests
{
    public class CarRecoveryTests
    {
        private static readonly Bounds Area = new Bounds(new Vector3(0f, 4f, 0f), new Vector3(100f, 20f, 100f));

        [Test]
        public void IsOutside_PointOnTheRoad_IsInside()
        {
            Assert.IsFalse(CarRecovery.IsOutside(Area, new Vector3(10f, 0.1f, -20f)));
        }

        [Test]
        public void IsOutside_FallenBelowTheArea_IsOutside()
        {
            Assert.IsTrue(CarRecovery.IsOutside(Area, new Vector3(0f, -50f, 0f)));
        }

        [Test]
        public void IsOutside_FarPastTheEdge_IsOutside()
        {
            Assert.IsTrue(CarRecovery.IsOutside(Area, new Vector3(80f, 1f, 0f)));
        }

        [Test]
        public void TryBuildArea_NullRoot_ReturnsFalse()
        {
            Assert.IsFalse(CarRecovery.TryBuildArea(null, 5f, out _));
        }

        [Test]
        public void TryBuildArea_AddsMarginOnEverySide()
        {
            var root = new GameObject("TestTrack");
            try
            {
                var cube = GameObject.CreatePrimitive(PrimitiveType.Cube);
                cube.transform.SetParent(root.transform, false);
                cube.transform.localScale = new Vector3(10f, 2f, 10f);

                Assert.IsTrue(CarRecovery.TryBuildArea(root.transform, 5f, out Bounds area));
                Assert.AreEqual(20f, area.size.x, 0.01f);
                Assert.AreEqual(12f, area.size.y, 0.01f);
                Assert.AreEqual(20f, area.size.z, 0.01f);
            }
            finally
            {
                Object.DestroyImmediate(root);
            }
        }
    }
}

// TrackAutopilotTests.cs — the steering law of the wall-following autopilot.
//
// Pure arithmetic on five wall distances. Sign convention: positive steer turns
// right, and lateral position is positive to the right of the road centre.

using NUnit.Framework;

namespace MindX.Tests
{
    public class TrackAutopilotTests
    {
        private const float CentreGain = 0.2f;
        private const float CornerGain = 1.0f;
        private const float LookAhead = 30f;

        private static float Steer(float left, float right, float fl, float fr, float fwd, float lane = 0f)
        {
            return TrackAutopilot.ComputeSteer(left, right, fl, fr, fwd, lane, CentreGain, CornerGain, LookAhead);
        }

        [Test]
        public void CentredOnAStraight_SteersNowhere()
        {
            Assert.AreEqual(0f, Steer(7f, 7f, 40f, 40f, 45f), 1e-5f);
        }

        [Test]
        public void CloserToTheRightWall_SteersLeft()
        {
            Assert.Less(Steer(10f, 4f, 40f, 40f, 45f), 0f);
        }

        [Test]
        public void CloserToTheLeftWall_SteersRight()
        {
            Assert.Greater(Steer(4f, 10f, 40f, 40f, 45f), 0f);
        }

        [Test]
        public void WantedLaneOnTheRight_HoldsTheCarThere()
        {
            // 2 m right of centre (left 9, right 5) with a +2 m lane: no correction.
            Assert.AreEqual(0f, Steer(9f, 5f, 40f, 40f, 45f, 2f), 1e-5f);
        }

        [Test]
        public void LeftCornerAhead_TurnsLeft()
        {
            // The road bends left: the right diagonal hits the outer wall early.
            Assert.Less(Steer(7f, 7f, 30f, 8f, 10f), 0f);
        }

        [Test]
        public void RightCornerAhead_TurnsRight()
        {
            Assert.Greater(Steer(7f, 7f, 8f, 30f, 10f), 0f);
        }

        [Test]
        public void CornerFarAway_IsIgnored()
        {
            Assert.AreEqual(0f, Steer(7f, 7f, 30f, 8f, 45f), 1e-5f);
        }

        [Test]
        public void NearACorner_TheLateralCorrectionFades()
        {
            // Same 3 m offset toward the right wall, no corner term (equal diagonals).
            float onStraight = Steer(10f, 4f, 40f, 40f, 45f);
            float inCorner = Steer(10f, 4f, 40f, 40f, 4f);
            Assert.Less(onStraight, 0f);
            Assert.Less(inCorner, 0f);
            Assert.Greater(inCorner, onStraight, "the correction is weaker in a corner");
        }

        [Test]
        public void Output_IsClampedToTheUnitRange()
        {
            Assert.AreEqual(1f, Steer(0f, 40f, 1f, 40f, 1f), 1e-5f);
            Assert.AreEqual(-1f, Steer(40f, 0f, 40f, 1f, 1f), 1e-5f);
        }
    }
}

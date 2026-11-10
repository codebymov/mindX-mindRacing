// LevelHistoryTests.cs — the rolling record behind the HUD's live INS curve.

using NUnit.Framework;

namespace MindX.Tests
{
    public class LevelHistoryTests
    {
        [Test]
        public void Record_LatestValueInABucketWins()
        {
            var h = new LevelHistory(10, 1f);
            h.Record(100f, 0.2f);
            h.Record(100.4f, 0.5f);
            Assert.AreEqual(1, h.Count);
            Assert.AreEqual(0.5f, h[0], 1e-6f);
        }

        [Test]
        public void Record_GapCarriesTheLastValueForward()
        {
            var h = new LevelHistory(10, 1f);
            h.Record(0f, 0.3f);
            h.Record(4f, 0.9f);
            Assert.AreEqual(5, h.Count);
            Assert.AreEqual(0.3f, h[1], 1e-6f);
            Assert.AreEqual(0.3f, h[3], 1e-6f);
            Assert.AreEqual(0.9f, h[4], 1e-6f);
        }

        [Test]
        public void Record_WhenFullScrollsAndKeepsTheNewest()
        {
            var h = new LevelHistory(5, 1f);
            for (int t = 0; t < 8; t++)
            {
                h.Record(t, t);
            }

            Assert.AreEqual(5, h.Count);
            Assert.AreEqual(3f, h[0], 1e-6f);
            Assert.AreEqual(7f, h[4], 1e-6f);
        }

        [Test]
        public void Record_GapLongerThanTheRecordRestarts()
        {
            var h = new LevelHistory(5, 1f);
            h.Record(0f, 0.1f);
            h.Record(1000f, 0.7f);
            Assert.AreEqual(1, h.Count);
            Assert.AreEqual(0.7f, h[0], 1e-6f);
        }

        [Test]
        public void Flag_IsStoredPerBucketAndCarriedAcrossGaps()
        {
            var h = new LevelHistory(10, 1f);
            h.Record(0f, 0.1f, false);
            h.Record(1f, 0.2f, true);
            h.Record(4f, 0.3f, false);
            Assert.IsFalse(h.Flag(0));
            Assert.IsTrue(h.Flag(1));
            Assert.IsTrue(h.Flag(2), "gap buckets keep the previous flag");
            Assert.IsFalse(h.Flag(4));
        }

        [Test]
        public void Record_TimeBeforeTheOriginIsIgnored()
        {
            var h = new LevelHistory(5, 1f);
            h.Record(10f, 0.4f);
            h.Record(5f, 0.9f);
            Assert.AreEqual(1, h.Count);
            Assert.AreEqual(0.4f, h[0], 1e-6f);
        }
    }
}

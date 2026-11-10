// ScoringTests.cs — coin points, crash penalties and the coin lifecycle.

using NUnit.Framework;
using UnityEngine;

namespace MindX.Tests
{
    public class ScoringTests
    {
        private GameObject _car;
        private CarScore _score;

        [SetUp]
        public void SetUp()
        {
            _car = new GameObject("car");
            _score = _car.AddComponent<CarScore>();
        }

        [TearDown]
        public void TearDown()
        {
            Object.DestroyImmediate(_car);
        }

        [Test]
        public void Coin_AddsPointsAndCounts()
        {
            _score.RegisterCoin(1f);
            _score.RegisterCoin(2f);
            Assert.AreEqual(20, _score.Points);
            Assert.AreEqual(2, _score.Coins);
            Assert.AreEqual("+10", _score.LastEvent);
            Assert.IsFalse(_score.LastEventWasPenalty);
        }

        [Test]
        public void Crash_SubtractsPointsAndMayGoNegative()
        {
            Assert.IsTrue(_score.RegisterCrash(10f));
            Assert.AreEqual(-5, _score.Points);
            Assert.AreEqual(1, _score.Crashes);
            Assert.IsTrue(_score.LastEventWasPenalty);
            Assert.AreEqual("CRASH -5", _score.LastEvent);
        }

        [Test]
        public void Crash_WithinTheCooldownCountsOnce()
        {
            Assert.IsTrue(_score.RegisterCrash(10f));
            Assert.IsFalse(_score.RegisterCrash(10.5f));
            Assert.IsFalse(_score.RegisterCrash(11.4f));
            Assert.AreEqual(1, _score.Crashes);
            Assert.AreEqual(-5, _score.Points);
        }

        [Test]
        public void Crash_AfterTheCooldownCountsAgain()
        {
            _score.RegisterCrash(10f);
            Assert.IsTrue(_score.RegisterCrash(11.6f));
            Assert.AreEqual(2, _score.Crashes);
            Assert.AreEqual(-10, _score.Points);
        }

        [Test]
        public void Coin_CollectedOnce_ScoresForTheFirstCollectorOnly()
        {
            var coinGo = new GameObject("coin");
            var otherCar = new GameObject("other");
            try
            {
                var coin = coinGo.AddComponent<Coin>();
                var other = otherCar.AddComponent<CarScore>();

                Assert.IsTrue(coin.Collect(_score, 5f));
                Assert.IsFalse(coin.Available);
                Assert.IsFalse(coin.Collect(other, 5.1f));
                Assert.AreEqual(10, _score.Points);
                Assert.AreEqual(0, other.Points);
            }
            finally
            {
                Object.DestroyImmediate(coinGo);
                Object.DestroyImmediate(otherCar);
            }
        }

        [Test]
        public void Coin_RespawnsAfterTheDelay()
        {
            var coinGo = new GameObject("coin");
            try
            {
                var coin = coinGo.AddComponent<Coin>();
                coin.Collect(_score, 100f);

                coin.UpdateRespawn(110f);
                Assert.IsFalse(coin.Available, "still within the 20 s delay");

                coin.UpdateRespawn(120.5f);
                Assert.IsTrue(coin.Available);
                Assert.IsTrue(coin.Collect(_score, 121f), "collectable again after respawning");
                Assert.AreEqual(20, _score.Points);
            }
            finally
            {
                Object.DestroyImmediate(coinGo);
            }
        }

        [Test]
        public void CoinsPerMinute_CountsOnlyTheRecentWindow()
        {
            for (int i = 0; i < 6; i++)
            {
                _score.RegisterCoin(i * 5f); // coins at 0, 5, ..., 25
            }

            Assert.AreEqual(12f, _score.CoinsPerMinute(30f, 30f), 1e-4f); // all 6 coins within 30 s
            Assert.AreEqual(4f, _score.CoinsPerMinute(50f, 30f), 1e-4f);  // only the coins at 20 s and 25 s remain
        }

        [Test]
        public void CoinsPerMinute_FasterCollectionGivesAHigherRate()
        {
            var slow = new GameObject("slow").AddComponent<CarScore>();
            var fast = new GameObject("fast").AddComponent<CarScore>();
            try
            {
                for (int i = 0; i < 3; i++)
                {
                    slow.RegisterCoin(i * 10f);
                }

                for (int i = 0; i < 9; i++)
                {
                    fast.RegisterCoin(i * 3f);
                }

                Assert.Greater(fast.CoinsPerMinute(28f), slow.CoinsPerMinute(28f));
            }
            finally
            {
                Object.DestroyImmediate(slow.gameObject);
                Object.DestroyImmediate(fast.gameObject);
            }
        }

        [Test]
        public void Coin_NullCollector_IsIgnored()
        {
            var coinGo = new GameObject("coin");
            try
            {
                var coin = coinGo.AddComponent<Coin>();
                Assert.IsFalse(coin.Collect(null, 1f));
                Assert.IsTrue(coin.Available);
            }
            finally
            {
                Object.DestroyImmediate(coinGo);
            }
        }
    }
}

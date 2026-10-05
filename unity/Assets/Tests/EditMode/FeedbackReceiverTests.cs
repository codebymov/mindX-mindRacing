// FeedbackReceiverTests.cs — FeedbackReceiver behaviour with a mock transport.
//
// Pins the participant-facing rules on the Unity side: sham and real samples
// with the same level are indistinguishable (CLAUDE.md sham hard rule), and
// routing follows D8 (shared drives all cars, individual drives its owner,
// unroutable drives none). Engine pitch is the observable: it is a pure
// function of the applied level and doesn't depend on frame time.

using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEngine;

namespace MindX.Tests
{
    public class FeedbackReceiverTests
    {
        private sealed class QueueTransport : IFeedbackTransport
        {
            private readonly Queue<FeedbackSample> _queue = new Queue<FeedbackSample>();

            public void Push(FeedbackSample sample)
            {
                _queue.Enqueue(sample);
            }

            public bool TryGetLatest(out FeedbackSample sample)
            {
                if (_queue.Count == 0)
                {
                    sample = default;
                    return false;
                }

                sample = _queue.Dequeue();
                return true;
            }

            public void Close()
            {
            }
        }

        private static readonly MethodInfo UpdateMethod = typeof(FeedbackReceiver).GetMethod(
            "Update", BindingFlags.Instance | BindingFlags.NonPublic);

        private readonly List<GameObject> _created = new List<GameObject>();

        [TearDown]
        public void TearDown()
        {
            foreach (GameObject go in _created)
            {
                Object.DestroyImmediate(go);
            }

            _created.Clear();
        }

        private (FeedbackReceiver Receiver, AudioSource Engine, QueueTransport Transport)
            MakeCar(int carSubjectIndex)
        {
            var go = new GameObject($"car{carSubjectIndex}");
            _created.Add(go);
            AudioSource engine = go.AddComponent<AudioSource>();
            FeedbackReceiver receiver = go.AddComponent<FeedbackReceiver>();

            var so = new SerializedObject(receiver);
            so.FindProperty("autoConnect").boolValue = false;
            so.FindProperty("carSubjectIndex").intValue = carSubjectIndex;
            so.FindProperty("car").objectReferenceValue = go.transform;
            so.FindProperty("engine").objectReferenceValue = engine;
            so.ApplyModifiedPropertiesWithoutUndo();

            var transport = new QueueTransport();
            receiver.AttachTransport(transport);
            return (receiver, engine, transport);
        }

        private static FeedbackSample Sample(float level, string mode, int subjectIndex)
        {
            return new FeedbackSample
            {
                level = level,
                mode = mode,
                sessionMode = subjectIndex == FeedbackWire.SharedSubjectIndex
                    ? "hyperscanning"
                    : "individual",
                subjectIndex = subjectIndex,
            };
        }

        private static void Tick(FeedbackReceiver receiver)
        {
            UpdateMethod.Invoke(receiver, null);
        }

        [Test]
        public void ShamAndRealWithSameLevelAreIndistinguishable()
        {
            var real = MakeCar(0);
            var sham = MakeCar(0);

            real.Transport.Push(Sample(0.6f, "real", FeedbackWire.SharedSubjectIndex));
            sham.Transport.Push(Sample(0.6f, "sham", FeedbackWire.SharedSubjectIndex));
            Tick(real.Receiver);
            Tick(sham.Receiver);

            Assert.That(sham.Engine.pitch, Is.EqualTo(real.Engine.pitch));
            Assert.That(sham.Engine.volume, Is.EqualTo(real.Engine.volume));
        }

        [Test]
        public void SharedSampleDrivesEveryCar()
        {
            var car0 = MakeCar(0);
            var car1 = MakeCar(1);
            float idlePitch = 0f;

            foreach (var car in new[] { car0, car1 })
            {
                Tick(car.Receiver);
                idlePitch = car.Engine.pitch;
                car.Transport.Push(Sample(1f, "real", FeedbackWire.SharedSubjectIndex));
                Tick(car.Receiver);
                Assert.That(car.Engine.pitch, Is.GreaterThan(idlePitch));
            }
        }

        [Test]
        public void IndividualSampleDrivesOnlyItsOwner()
        {
            var owner = MakeCar(1);
            var other = MakeCar(0);
            Tick(other.Receiver);
            float otherIdle = other.Engine.pitch;
            Tick(owner.Receiver);
            float ownerIdle = owner.Engine.pitch;

            owner.Transport.Push(Sample(1f, "real", 1));
            other.Transport.Push(Sample(1f, "real", 1));
            Tick(owner.Receiver);
            Tick(other.Receiver);

            Assert.That(owner.Engine.pitch, Is.GreaterThan(ownerIdle));
            Assert.That(other.Engine.pitch, Is.EqualTo(otherIdle));
        }

        [Test]
        public void UnroutableSampleDrivesNoCar()
        {
            var car = MakeCar(0);
            Tick(car.Receiver);
            float idle = car.Engine.pitch;

            car.Transport.Push(Sample(1f, "real", FeedbackWire.UnroutableSubjectIndex));
            Tick(car.Receiver);

            Assert.That(car.Engine.pitch, Is.EqualTo(idle));
        }

        [Test]
        public void LevelIsClampedToUnitRange()
        {
            var high = MakeCar(0);
            var one = MakeCar(0);

            high.Transport.Push(Sample(7f, "real", FeedbackWire.SharedSubjectIndex));
            one.Transport.Push(Sample(1f, "real", FeedbackWire.SharedSubjectIndex));
            Tick(high.Receiver);
            Tick(one.Receiver);

            Assert.That(high.Engine.pitch, Is.EqualTo(one.Engine.pitch));
        }
    }
}

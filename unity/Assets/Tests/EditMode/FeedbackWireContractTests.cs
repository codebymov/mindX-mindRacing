// FeedbackWireContractTests.cs — Unity half of the cross-language wire contract.
//
// Decodes the SAME golden cases (contracts/feedback_wire.json) that
// backend/tests/test_wire_contract.py encodes. If either side changes the
// format alone, one of the two suites fails. Also pins car routing, including
// the rule that an unknown subject drives no car.

using System;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;

namespace MindX.Tests
{
    public class FeedbackWireContractTests
    {
        // DTO fields below are assigned by JsonUtility via reflection.
#pragma warning disable CS0649
        [Serializable]
        private class NamedCode
        {
            public string name;
            public float code;
        }

        [Serializable]
        private class StreamSpec
        {
            public string name;
        }

        [Serializable]
        private class WireCase
        {
            public string name;
            public string[] subjects;
            public double tLsl;
            public float level;
            public float rawIns;
            public string mode;
            public string sessionMode;
            public string subject;
            public float[] vector;
            public int[] drivesCars;
        }

        [Serializable]
        private class WireSpec
        {
            public int version;
            public StreamSpec stream;
            public string[] channels;
            public NamedCode[] modeCodes;
            public NamedCode[] sessionModeCodes;
            public int sharedSubjectIndex;
            public int unroutableSubjectIndex;
            public WireCase[] cases;
        }
#pragma warning restore CS0649

        private const float Tolerance = 1e-6f;

        private static WireSpec LoadSpec()
        {
            // Application.dataPath is <repo>/unity/Assets; the spec is at <repo>/contracts.
            string path = Path.GetFullPath(
                Path.Combine(Application.dataPath, "..", "..", "contracts", "feedback_wire.json"));
            Assert.That(File.Exists(path), Is.True, $"Wire spec not found at {path}.");
            return JsonUtility.FromJson<WireSpec>(File.ReadAllText(path));
        }

        [Test]
        public void ConstantsMatchSpec()
        {
            WireSpec spec = LoadSpec();

            Assert.That(FeedbackWire.StreamName, Is.EqualTo(spec.stream.name));
            Assert.That(FeedbackWire.ChannelCount, Is.EqualTo(spec.channels.Length));
            Assert.That(FeedbackWire.SharedSubjectIndex, Is.EqualTo(spec.sharedSubjectIndex));
            Assert.That(FeedbackWire.UnroutableSubjectIndex, Is.EqualTo(spec.unroutableSubjectIndex));
        }

        [Test]
        public void DecoderReproducesGoldenCases()
        {
            WireSpec spec = LoadSpec();
            Assert.That(spec.cases, Is.Not.Empty);

            foreach (WireCase c in spec.cases)
            {
                FeedbackSample s = FeedbackWire.Decode(c.vector, c.tLsl, c.subjects);
                string expectedSubject = string.IsNullOrEmpty(c.subject)
                    || !c.subjects.Contains(c.subject)
                    ? null
                    : c.subject;

                Assert.That(s.tLsl, Is.EqualTo(c.tLsl), c.name);
                Assert.That(s.level, Is.EqualTo(c.level).Within(Tolerance), c.name);
                Assert.That(s.rawIns, Is.EqualTo(c.rawIns).Within(Tolerance), c.name);
                Assert.That(s.mode, Is.EqualTo(c.mode), c.name);
                Assert.That(s.sessionMode, Is.EqualTo(c.sessionMode), c.name);
                Assert.That(s.subject, Is.EqualTo(expectedSubject), c.name);
            }
        }

        [Test]
        public void CodesDecodeToTheirSpecNames()
        {
            WireSpec spec = LoadSpec();

            foreach (NamedCode m in spec.modeCodes)
            {
                float[] v = { 0f, 0f, m.code, 0f, -1f };
                Assert.That(FeedbackWire.Decode(v, 0.0, new string[0]).mode, Is.EqualTo(m.name));
            }

            foreach (NamedCode m in spec.sessionModeCodes)
            {
                float[] v = { 0f, 0f, 0f, m.code, -1f };
                Assert.That(
                    FeedbackWire.Decode(v, 0.0, new string[0]).sessionMode, Is.EqualTo(m.name));
            }
        }

        [Test]
        public void RoutingMatchesGoldenCases()
        {
            WireSpec spec = LoadSpec();

            foreach (WireCase c in spec.cases)
            {
                int subjectIndex = FeedbackWire.Decode(c.vector, c.tLsl, c.subjects).subjectIndex;
                for (int car = 0; car < c.subjects.Length; car++)
                {
                    bool expected = c.drivesCars.Contains(car);
                    Assert.That(
                        FeedbackWire.Drives(subjectIndex, car),
                        Is.EqualTo(expected),
                        $"{c.name}: car {car}");
                }
            }
        }

        [Test]
        public void DecodeRejectsShortVector()
        {
            Assert.Throws<ArgumentException>(
                () => FeedbackWire.Decode(new float[3], 0.0, new string[0]));
        }

        [Test]
        public void CreateWithoutRegisteredTransportThrows()
        {
            Func<string, IFeedbackTransport> saved = FeedbackTransports.Factory;
            try
            {
                FeedbackTransports.Factory = null;
                Assert.Throws<InvalidOperationException>(
                    () => FeedbackTransports.Create(FeedbackWire.StreamName));
            }
            finally
            {
                FeedbackTransports.Factory = saved;
            }
        }
    }
}

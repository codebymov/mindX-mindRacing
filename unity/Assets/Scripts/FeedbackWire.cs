// FeedbackWire.cs — the Unity half of the backend -> game wire contract (D9).
//
// The format is specified ONCE in contracts/feedback_wire.json at the repo root.
// The Python encoder (backend/mindx_hnf/api/sink.py::encode_feedback) and this
// decoder are both tested against that file's golden cases
// (backend/tests/test_wire_contract.py and
// Assets/Tests/EditMode/FeedbackWireContractTests.cs), so the two languages
// cannot drift silently. Pure C#: no LSL, no MonoBehaviour, testable anywhere.

using System.Collections.Generic;
using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Constants and pure functions for the "mindx_feedback" LSL vector.
    /// </summary>
    public static class FeedbackWire
    {
        /// <summary>Default LSL stream name published by the backend.</summary>
        public const string StreamName = "mindx_feedback";

        /// <summary>Channels per sample: level, raw_ins, mode, session_mode, subject_index.</summary>
        public const int ChannelCount = 5;

        /// <summary>Subject index of the shared dyad signal; drives every car.</summary>
        public const int SharedSubjectIndex = -1;

        /// <summary>Subject index of a sample for an unknown subject; drives no car.</summary>
        public const int UnroutableSubjectIndex = -2;

        /// <summary>
        /// Decodes one wire vector into a <see cref="FeedbackSample"/>.
        /// </summary>
        /// <param name="vector">The raw sample, in channel order.</param>
        /// <param name="tLsl">The sample's LSL timestamp (the backend clock of record).</param>
        /// <param name="subjectIds">Subject ids by index, from the stream's XML description.</param>
        /// <returns>The decoded sample. String fields are for logging only.</returns>
        /// <exception cref="System.ArgumentException">
        /// Thrown when <paramref name="vector"/> has fewer than <see cref="ChannelCount"/> entries.
        /// </exception>
        public static FeedbackSample Decode(
            float[] vector,
            double tLsl,
            IReadOnlyList<string> subjectIds)
        {
            if (vector == null || vector.Length < ChannelCount)
            {
                throw new System.ArgumentException(
                    $"Feedback vector needs {ChannelCount} channels.", nameof(vector));
            }

            int subjectIndex = Mathf.RoundToInt(vector[4]);
            bool knownSubject = subjectIds != null
                && subjectIndex >= 0
                && subjectIndex < subjectIds.Count;
            return new FeedbackSample
            {
                tLsl = tLsl,
                level = vector[0],
                rawIns = vector[1],
                mode = vector[2] < 0.5f ? "real" : "sham",
                sessionMode = vector[3] < 0.5f ? "hyperscanning" : "individual",
                subjectIndex = subjectIndex,
                subject = knownSubject ? subjectIds[subjectIndex] : null,
            };
        }

        /// <summary>
        /// Returns whether a sample should drive the car owned by <paramref name="carSubjectIndex"/>.
        /// </summary>
        /// <param name="sampleSubjectIndex">The sample's decoded subject index.</param>
        /// <param name="carSubjectIndex">The index of the car's owner.</param>
        /// <returns>
        /// True for the shared signal (every car) or the car's own subject; false
        /// otherwise, including the unroutable sentinel. Never depends on real/sham.
        /// </returns>
        public static bool Drives(int sampleSubjectIndex, int carSubjectIndex)
        {
            return sampleSubjectIndex == SharedSubjectIndex
                || (sampleSubjectIndex >= 0 && sampleSubjectIndex == carSubjectIndex);
        }
    }
}

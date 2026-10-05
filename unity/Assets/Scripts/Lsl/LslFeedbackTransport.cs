// LslFeedbackTransport.cs — the Unity end of the backend->game LSL seam.
//
// Subscribes to the "mindx_feedback" LSL stream published by the Python backend
// (backend/mindx_hnf/api/sink.py::LSLOutletSink) and decodes each sample into a
// FeedbackSample. This resolves DECISIONS.md O2 in favour of LSL: the game stays
// on the one clock of record (the sample keeps its backend LSL timestamp), and
// BOTH headsets run their own inlet on the same stream, so both receive the
// identical joint feedback signal.
//
// REQUIRES the LSL4Unity package (com.labstreaminglayer.lsl4unity) + the native
// liblsl binary for each target platform. See docs/LSL_UNITY_SETUP.md. This file
// lives in the MindX.Lsl assembly, which compiles ONLY when that package is
// installed (versionDefines -> MINDX_LSL); without it the rest of the game still
// compiles and FeedbackReceiver idles. Decoding is FeedbackWire.Decode (core).
//
// NOTE ON THE LSL C# NAMESPACE: current LSL4Unity ships the modern bindings in
// namespace `LSL` (class `LSL.LSL`, types `StreamInlet`/`StreamInfo`). Older
// forks expose the same API under `LSL.liblsl`. If you get a namespace error,
// swap `LSL.LSL.resolve_stream` -> `LSL.liblsl.resolve_stream` and the `using`
// accordingly — the logic below is identical across both.

using System;
using System.Collections.Generic;
using LSL;
using UnityEngine;

namespace MindX
{
    /// LSL-backed IFeedbackTransport. Non-blocking: drained from the main thread
    /// in Update via TryGetLatest — feedback is a *level*, not a queue, so we
    /// keep only the newest sample and never let a stale value win.
    public class LslFeedbackTransport : IFeedbackTransport
    {
        /// <summary>
        /// Registers this transport as the factory core components use, before
        /// any scene loads.
        /// </summary>
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        private static void Register()
        {
            FeedbackTransports.Factory = name => new LslFeedbackTransport(name);
        }

        private StreamInlet _inlet;
        private readonly float[] _buf = new float[FeedbackWire.ChannelCount];
        private readonly List<string> _subjectIds = new List<string>(); // index -> subject id
        private FeedbackSample _latest;

        /// Resolves the stream by name and opens an inlet. Throws if the stream
        /// isn't on the network yet (start the backend: `simulate --lsl`).
        public LslFeedbackTransport(string streamName = "mindx_feedback", double resolveTimeout = 5.0)
        {
            StreamInfo[] results = LSL.LSL.resolve_stream("name", streamName, 1, resolveTimeout);
            if (results == null || results.Length == 0)
                throw new Exception(
                    $"LSL stream '{streamName}' not found. Is the backend publishing " +
                    "(python -m mindx_hnf.scripts.simulate --lsl)?");

            _inlet = new StreamInlet(results[0]);
            _inlet.open_stream();
            ReadSubjectMap(_inlet.info());
        }

        /// The outlet self-describes its subject_index -> subject_id map in the
        /// stream's XML <subjects> block, so we can label samples for logging
        /// without knowing the run config. Routing uses the numeric index; this
        /// table is provenance only.
        private void ReadSubjectMap(StreamInfo info)
        {
            _subjectIds.Clear();
            XMLElement subjects = info.desc().child("subjects");
            for (XMLElement c = subjects.first_child(); !c.empty(); c = c.next_sibling())
                _subjectIds.Add(c.child_value());
        }

        public bool TryGetLatest(out FeedbackSample sample)
        {
            bool gotNew = false;
            if (_inlet != null)
            {
                // 0.0 timeout = non-blocking; loop drains the buffer to the newest.
                // pull_sample returns the sample's LSL timestamp (0.0 == none).
                double ts;
                while ((ts = _inlet.pull_sample(_buf, 0.0)) != 0.0)
                {
                    _latest = FeedbackWire.Decode(_buf, ts, _subjectIds);
                    gotNew = true;
                }
            }
            sample = _latest;
            return gotNew;
        }

        public void Close()
        {
            if (_inlet != null)
            {
                _inlet.close_stream();
                _inlet = null;
            }
        }
    }
}

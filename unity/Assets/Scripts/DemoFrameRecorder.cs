// DemoFrameRecorder.cs — saves the Game view as numbered PNG frames while playing.
//
// For making a time-lapse of a demo session (frames are stitched into a GIF outside
// Unity). Add it to any GameObject in Play mode and call Configure. It never runs
// unless configured, and writes only under the folder it is given.

using System.IO;
using UnityEngine;

namespace MindX
{
    /// <summary>
    /// Captures a Game view screenshot every few seconds into a folder.
    /// </summary>
    public class DemoFrameRecorder : MonoBehaviour
    {
        private string _directory;
        private float _interval = 1.5f;
        private int _maxFrames = 400;
        private int _count;
        private float _next;

        /// <summary>
        /// Gets the number of frames requested so far.
        /// </summary>
        public int FrameCount => _count;

        /// <summary>
        /// Starts recording.
        /// </summary>
        /// <param name="directory">Folder for the frames; created if missing.</param>
        /// <param name="intervalSeconds">Seconds between frames.</param>
        /// <param name="maxFrames">Stop after this many frames.</param>
        public void Configure(string directory, float intervalSeconds, int maxFrames)
        {
            _directory = directory;
            _interval = Mathf.Max(0.1f, intervalSeconds);
            _maxFrames = maxFrames;
            _count = 0;
            _next = 0f;
            Directory.CreateDirectory(directory);
        }

        private void Update()
        {
            if (string.IsNullOrEmpty(_directory) || _count >= _maxFrames || Time.unscaledTime < _next)
            {
                return;
            }

            _next = Time.unscaledTime + _interval;
            ScreenCapture.CaptureScreenshot(Path.Combine(_directory, $"frame_{_count:0000}.png"));
            _count++;
        }
    }
}

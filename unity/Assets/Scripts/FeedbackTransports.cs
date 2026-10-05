// FeedbackTransports.cs — how core game code gets a feedback transport without
// referencing LSL.
//
// The LSL transport lives in the optional MindX.Lsl assembly, which compiles only
// when the LSL4Unity package is installed. That assembly registers a factory here
// at startup; core components (FeedbackReceiver, SharedCarAuthority) call Create
// and never name LslFeedbackTransport. Tests can set Factory to a mock.

using System;

namespace MindX
{
    /// <summary>
    /// Registry for the feedback transport factory.
    /// </summary>
    public static class FeedbackTransports
    {
        /// <summary>
        /// Creates a transport for a stream name. Null until a transport assembly
        /// (e.g. MindX.Lsl) registers itself.
        /// </summary>
        public static Func<string, IFeedbackTransport> Factory { get; set; }

        /// <summary>
        /// Creates a transport for <paramref name="streamName"/>.
        /// </summary>
        /// <param name="streamName">The LSL stream to subscribe to.</param>
        /// <returns>A connected transport.</returns>
        /// <exception cref="InvalidOperationException">
        /// Thrown when no transport is registered (LSL4Unity not installed).
        /// </exception>
        public static IFeedbackTransport Create(string streamName)
        {
            if (Factory == null)
            {
                throw new InvalidOperationException(
                    "No feedback transport registered. Install LSL4Unity "
                    + "(docs/LSL_UNITY_SETUP.md) so MindX.Lsl compiles.");
            }

            return Factory(streamName);
        }
    }
}

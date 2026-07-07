namespace MindX
{
    /// A pluggable source of car control. The SOURCE of the drive command —
    /// keyboard (dev), XR thumbstick, neurofeedback signal, or a networked remote
    /// player — is decoupled from how the car actually moves (see CarDriver). This
    /// is what lets the same car be driven by WASD during development and by the
    /// feedback signal at runtime without touching the driver or the scene wiring.
    ///
    /// Implementations: KeyboardCarInput (dev) and later a NetworkCarInput /
    /// ML-Agent for the remote or companion car (DECISIONS.md O6). NOTE: the
    /// *neurofeedback* drive does NOT come through here — speed is proportional
    /// to INS (D7), which maps to velocity, not to an accel-style throttle, so it
    /// is delivered by FeedbackReceiver (the LSL consumer) instead. ICarInput is
    /// for accel/steer-style controllers (human, agent, network).
    public interface ICarInput
    {
        /// Forward / reverse command in [-1, 1].
        float Throttle { get; }

        /// Left / right steering command in [-1, 1].
        float Steer { get; }
    }
}

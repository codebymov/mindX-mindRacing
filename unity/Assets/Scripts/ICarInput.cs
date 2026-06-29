namespace MindX
{
    /// A pluggable source of car control. The SOURCE of the drive command —
    /// keyboard (dev), XR thumbstick, neurofeedback signal, or a networked remote
    /// player — is decoupled from how the car actually moves (see CarDriver). This
    /// is what lets the same car be driven by WASD during development and by the
    /// feedback signal at runtime without touching the driver or the scene wiring.
    ///
    /// Implementations: KeyboardCarInput (dev), NeurofeedbackCarInput (runtime,
    /// added once DECISIONS.md O6 / the INS-vs-individual question is resolved),
    /// and later a NetworkCarInput for the remote player.
    public interface ICarInput
    {
        /// Forward / reverse command in [-1, 1].
        float Throttle { get; }

        /// Left / right steering command in [-1, 1].
        float Steer { get; }
    }
}

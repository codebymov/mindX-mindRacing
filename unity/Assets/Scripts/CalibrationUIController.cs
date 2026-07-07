// CalibrationUIController.cs — guided prompts for co-location (O5, item 4).
//
// Drives the operator/participant through the two-point controller registration
// (ColocationRegistration, D11) with on-screen prompts. Deliberately decoupled
// from any specific UI widget: it emits the current prompt as a UnityEvent<string>
// and exposes CurrentPrompt, so a world-space Canvas Text or TMP_Text can bind it
// in the inspector without this script depending on the TextMeshPro package.

using UnityEngine;
using UnityEngine.Events;

namespace MindX
{
    public class CalibrationUIController : MonoBehaviour
    {
        [SerializeField] private ColocationRegistration registration;

        [Header("Prompts (per calibration step)")]
        [SerializeField] private string needOriginPrompt =
            "Point the controller at the ORIGIN mark on the table and pull the trigger.";
        [SerializeField] private string needForwardPrompt =
            "Now point at the FORWARD mark and pull the trigger.";
        [SerializeField] private string registeredPrompt =
            "Co-location set. You and your partner now share the same track.";

        [Tooltip("Bind a world-space Text / TMP_Text's SetText here to display the prompt.")]
        public UnityEvent<string> PromptChanged;

        public string CurrentPrompt { get; private set; } = "";

        void Awake()
        {
            if (registration == null)
                registration = GetComponent<ColocationRegistration>();
        }

        void OnEnable()
        {
            if (registration != null)
                registration.StepChanged += OnStep;
        }

        void OnDisable()
        {
            if (registration != null)
                registration.StepChanged -= OnStep;
        }

        private void OnStep(ColocationRegistration.Step step)
        {
            CurrentPrompt = step switch
            {
                ColocationRegistration.Step.NeedOrigin => needOriginPrompt,
                ColocationRegistration.Step.NeedForward => needForwardPrompt,
                ColocationRegistration.Step.Registered => registeredPrompt,
                _ => "",
            };
            PromptChanged?.Invoke(CurrentPrompt);
        }
    }
}

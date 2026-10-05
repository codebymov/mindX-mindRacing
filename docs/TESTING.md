# Testing strategy

mindX is a research instrument with a human in a closed loop, written in two
languages (Python backend, C# Unity game). Tests are layered so that each layer
guards something the layer below can't, and so the two languages can't drift
apart silently. Status as of 2026-10-05.

## The layers

| Layer | What it guards | Python (`backend/tests/`) | C# (`unity/Assets/Tests/`) |
|---|---|---|---|
| **Unit** | One function/class in isolation | INS estimators, feedback mapper, session scheduler, sham provider, montage | `FeedbackWire` decode/routing, `FeedbackTransports` |
| **Differential (oracle)** | Our causal/online code computes the same thing as the reference implementation | Every MNE-derived stage vs MNE / MNE-NIRS batch (`test_montage_mbll.py`, `test_causal_preprocessing.py`) | — |
| **Contract (cross-language)** | Python encoder and C# decoder agree on the wire format | `test_wire_contract.py` | `FeedbackWireContractTests.cs` |
| **Component / functional** | A component's participant-facing behaviour | Session modes, sham integrity, safety cap + abort | `FeedbackReceiverTests.cs` (sham indistinguishable, D8 routing, clamping) |
| **Integration** | Stages wired together | Synthetic source → pipeline → INS → feedback (`test_loop_and_safety.py`), INS recovery under systemic noise | — |
| **Transport round-trip** | Real LSL outlet → inlet, timestamp preserved | `test_lsl_outlet.py` (needs pylsl + liblsl) | — |
| **End-to-end** | Backend → LSL → Unity car responds | *Not automated yet* — manual: `simulate --lsl` + Play | *Planned PlayMode test* |
| **Latency budget** | Per-frame processing stays real-time | `test_loop_latency_under_budget` | — |

### The cross-language contract

`contracts/feedback_wire.json` is the **single source of truth** for the
backend → Unity feedback vector: stream name, channel order, numeric codes,
the shared (`-1`) and unroutable (`-2`) subject sentinels, and golden cases.
The Python test encodes each golden case and must reproduce its vector; the C#
tests decode the same vector and must reproduce its fields and car routing. To
change the format: edit the JSON (bump `version`), then both sides, and both
suites must pass.

## Running

**Python** (from `backend/`):

    pip install -r requirements.lock && pip install -e . --no-deps
    pytest -q -rs          # -rs shows skips; oracle tests must NOT be skipped

Oracle tests skip if `mne`/`mne-nirs` are missing. A skipped oracle test is a
hole in the science guarantees, which is why CI installs the lock file and
prints skips.

**Unity EditMode** (needs an activated Unity licence, e.g. Personal, signed in
via Unity Hub):

    Unity.exe -batchmode -nographics -projectPath <repo>/unity ^
      -runTests -testPlatform EditMode -testResults results.xml

or *Window ▸ General ▸ Test Runner ▸ EditMode ▸ Run All* in the Editor.

## Unity assembly layout (why tests can compile without LSL/Ubiq)

| Assembly | Folder | Compiles when |
|---|---|---|
| `MindX.Runtime` | `Assets/Scripts/` | always |
| `MindX.Lsl` | `Assets/Scripts/Lsl/` | LSL4Unity installed (`MINDX_LSL` via `versionDefines`) |
| `MindX.Ubiq` | `Assets/Scripts/Ubiq/` | Ubiq installed (`MINDX_UBIQ`) |
| `MindX.Tests.EditMode` | `Assets/Tests/EditMode/` | Editor + test runner |

Core code never names `LslFeedbackTransport`; it asks `FeedbackTransports.Create`,
which `MindX.Lsl` registers at startup. Before this split, one missing package
broke compilation of every game script.

## CI

`.github/workflows/backend.yml` runs ruff, black, mypy and pytest on Linux and
Windows, Python 3.11 and 3.13, from `requirements.lock`. Unity CI is not set up:
it needs a Unity licence stored as a repository secret (e.g. GameCI).

## Gaps (next)

1. **Run the Unity EditMode suite for real.** It is compile-checked with
   Unity's Roslyn, but no Unity licence is active on the dev machine yet.
2. **Automated E2E**: a PlayMode test that subscribes to `simulate --lsl` and
   asserts the car's speed follows the published level.
3. **Golden-output regression**: freeze a fixed-seed synthetic run's HbO/INS
   output so any unintended numeric change fails.
4. **Unity CI** (GameCI + licence secret) and a coverage report for both sides.

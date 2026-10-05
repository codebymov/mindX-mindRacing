# Session handoff — start here

Read this first in a new Claude Code session (any device), right after
`CLAUDE.md`. It records where the project stands and what to do next. Update it
at the end of every session, in the same commit as the work.

**Last updated:** 2026-10-05 (commits `4ad6f55` … `HEAD` on `main`).

## Where we are

| Area | State |
|---|---|
| Backend real-time loop | Works end-to-end on synthetic data (`simulate`, `simulate --montage configs/montage_demo.yaml`, `simulate --lsl`). |
| MNE online (D10) | Phase 1 (MBLL) + Phase 2 (baseline-frozen OD, causal TDDR, wavelength-paired short-channel regression) **done**, each tested against MNE/MNE-NIRS. See `docs/MNE_ONLINE_SCOPE.md`. |
| Backend → Unity transport (D9) | LSL. Wire format = `contracts/feedback_wire.json`, tested from both languages. |
| Unity | Scripts split into `MindX.Runtime` + optional `MindX.Lsl` / `MindX.Ubiq` + `MindX.Tests.EditMode`. **Compile-checked** with Unity's Roslyn, **never run in the Editor yet**. LSL4Unity and Ubiq are **not installed** in the project. |
| Multiplayer O5 (Ubiq, D11/D12) | Scaffolded only; Ubiq scripts never compiled against Ubiq. |
| Tests | Python: 48 pass, 0 skipped. C# EditMode: 11 tests, written + compiled, not executed. See `docs/TESTING.md`. |
| CI | `.github/workflows/backend.yml` (Linux + Windows, Py 3.11/3.13). No Unity CI. |
| Style | Python: Google style + Google docstrings, enforced by ruff `D`. C#: Microsoft + Unity (`unity/.editorconfig`). |

## Next tasks, in order

1. **Activate a Unity licence** (sign in to Unity Hub, Personal is fine) on the
   machine with Unity 2022.3.5f1, then run the EditMode suite (command in
   `docs/TESTING.md`) and fix anything it finds. Blocked on the user.
2. **Unity Editor pass → "Level A" demo** (synthetic signal driving the car in a
   headset): install LSL4Unity (`docs/LSL_UNITY_SETUP.md`, URL verified), open
   the scene, `simulate --lsl`, confirm the car responds; build to headset.
3. **Automated E2E test**: PlayMode test subscribing to `simulate --lsl`,
   asserting car speed follows the level (`docs/TESTING.md` gaps).
4. **Golden-output regression test**: freeze a fixed-seed synthetic run's
   HbO/INS output.
5. **Remaining MNE items** (small, before first real recording): causal
   signal-quality check (MNE scalp coupling index, during baseline → drop bad
   channels); replace placeholder `_CausalBandpass` with a causal SOS
   Butterworth. **Phase 3** (live NIRSport2 via LSL, `io/sources.py::LSLSource`)
   needs hardware — it is the critical path to a live-brain demo.
6. Ubiq install + first compile of `Assets/Scripts/Ubiq/`, then O5 integration.
7. Open decisions: O7 (per-subject NF feature for Individual mode), O3/O4 (INS
   window / estimator, need pilot data), O6 (second car). See `docs/DECISIONS.md`.

## Demo roadmap (agreed framing)

- **Level A** — synthetic signal → car in VR: ~1 week after the Unity licence.
- **Level B** — one person, live fNIRS, Individual mode: + `LSLSource`, signal
  quality, O7 feature: ~2–4 weeks, hardware-dependent.
- **Level C** — two people, live hyperscanning, co-located: 1–2+ months.
- fNIRS is slow (5–7 s hemodynamic lag, 30 s INS window): set audience
  expectations. EEG is not in the pipeline at all.

## Environment pitfalls (read before running anything)

- The backend venv is a **Windows** venv: from WSL use
  `backend/.venv/Scripts/python.exe` (plain `python` doesn't exist there).
  New device: `pip install -r backend/requirements.lock && pip install -e backend --no-deps`.
- **Never let oracle tests skip silently.** If `mne`/`mne-nirs` are missing they
  skip; always run `pytest -rs`.
- Windows Python writes **CRLF** when opening files with `"w"`; the repo is LF
  (`.gitattributes`). Use `newline="\n"` or fix with `sed -i 's/\r$//'`.
- Every new Unity file/folder needs a committed `.meta` with a stable GUID;
  move scripts with `git mv` together with their `.meta`.
- `unity/Temp/UnityLockfile` from 2026-06-25 is stale, not a running Editor.
- The ruff version is pinned in the lock (0.16.x, stricter defaults than older
  ruff); run ruff from the venv, not a global one.
- Unity C# can be compile-checked without a licence using Unity's bundled
  Roslyn (`Editor/Data/NetCoreRuntime/dotnet.exe` + `DotNetSdkRoslyn/csc.dll`)
  against `Editor/Data/Managed/UnityEngine/*.dll`; that is how the current
  Unity code was verified.

## Housekeeping waiting on a decision

- Stray empty Unity project at the repo root (`/Assets`, `/Library`,
  `/Packages`, `/ProjectSettings`; ignored) — delete after user OK.
- Git LFS not enabled; large binaries (34 MB PNG, 12 MB MP4) in plain history.
- `backend/.venv/Lib/site-packages/~umpy`: leftover pip temp dir, safe to delete.

## Session log

- **2026-10-05** — MNE Phase 2 (`4ad6f55`). Found the venv lacked mne, so the
  Phase 1 oracle tests had been silently skipping. Cross-language wire contract +
  Unity assembly split + EditMode tests + CI + lock file (`0cab246`). Fixed bug:
  an unknown subject drove every car in Individual mode. Google docstrings
  across the backend (`c7192d8`). Found that MNE-NIRS 0.7.3 regresses both
  wavelengths on the 760 nm short channel (we pair by wavelength). Corrected
  LSL4Unity/Ubiq install URLs. Mutation check: changing the channel order, a
  sentinel, or the sham code on the Python side now fails the contract test.
  First CI run (Linux+Windows × Py 3.11/3.13) caught an exact-float assert in
  `test_sham_integrity.py` failing on numpy 2.4 (1e-16); fixed with a 1e-12
  tolerance.

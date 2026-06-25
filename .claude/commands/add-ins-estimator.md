---
description: Add a new INS estimator behind the existing protocol
argument-hint: <estimator-name>
---

Add a new interpersonal-neural-synchrony estimator named "$ARGUMENTS".

Requirements (do not deviate):
- Implement the `INSEstimator` protocol from `backend/mindx_hnf/contracts.py`
  (a `name` attribute, `update(frame) -> INSSample | None`, and `reset()`).
- Put it in `backend/mindx_hnf/ins/` and export it from that package's
  `__init__.py`.
- It must be windowed, causal, and run-time efficient (no future samples).
- Output value clamped to [0, 1].
- Add a test to `backend/tests/test_ins.py` that asserts the estimator's value
  RISES with true coherence, using the existing `_make_frames` ground-truth
  helper. This is the load-bearing check — it must pass.

Then run `pytest backend/tests/test_ins.py -q` and report results. Do not touch
the orchestrator or other stages; the whole point of the protocol is that you
don't have to.

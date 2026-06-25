---
description: Implement a hardware/transport seam (LSL source or sink) against its contract
argument-hint: <source|sink>
---

Implement the "$ARGUMENTS" hardware seam.

Context: the synthetic counterpart already defines the exact output contract.
Your implementation must be drop-in interchangeable with it.

- For `source`: implement `LSLSource.frames()` in
  `backend/mindx_hnf/io/sources.py`. Resolve the per-subject NIRSport2 LSL
  streams from config, dejitter, align all streams on the LSL clock, and emit
  `RawFrame`s identical in shape/semantics to what `SyntheticSource` produces.
- For `sink`: implement `LSLOutletSink` in `backend/mindx_hnf/api/sink.py`,
  matching the `FeedbackSink` protocol and `NullSink`'s behavior.

Rules:
- Lazy-import `pylsl` so the package still imports without hardware installed.
- No blocking calls on the hot path beyond the unavoidable LSL pull/push.
- Keep the LSL clock as the single time base.
- Add a guard/skip-marked test that runs only when pylsl is importable; the
  synthetic-based tests must remain the default CI path.

Report what you changed and confirm the existing `pytest` suite still passes.

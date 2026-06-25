# Architecture

This document explains *why* the system is shaped the way it is. For the rules,
see the root `CLAUDE.md`; for terms, see `GLOSSARY.md`.

## The problem shape

We close a loop through two human brains. Two participants interact; we measure
both brains with fNIRS; we compute how synchronized they are (INS); we show that
synchrony back to them inside a game; they (hopefully) learn to increase it. The
engineering consequence of "human in the loop, in real time" dominates every
decision: **bounded latency and determinism beat throughput and cleverness.**

## Two tracks, decoupled

```
            ┌──────────────── REAL-TIME TRACK (causal, bounded latency) ───────────────┐
 hardware → │ io → preprocessing → ins → feedback → sink(Unity)                        │
            └──────────────────────────────┬───────────────────────────────────────────┘
                                           │ fork (non-blocking)
            ┌──────────────────────────────▼─── PERSISTENCE TRACK (may lag, may fail) ──┐
            │ storage: BIDS write, DataLad commit, Postgres metadata                    │
            └───────────────────────────────────────────────────────────────────────────┘
```

The real-time track is the instrument. The persistence track is the lab
notebook. They must not be coupled: a slow disk or a down database can degrade
the notebook but must never perturb the instrument. This is enforced by the
non-blocking `ArtifactRecorder` (bounded queue, drop-oldest, background thread).

## Typed seams (the "IR")

Stages communicate only through the dataclasses in `contracts.py`
(`RawFrame → HemoFrame → INSSample → FeedbackSample`) and the protocols
(`OnlinePreprocessor`, `INSEstimator`, `FeedbackMapper`, `FeedbackSink`). This is
deliberate: any stage can be reimplemented or swapped (a new INS estimator, a
different transport to Unity) without touching the rest, and each can be tested
in isolation against the contract. New work conforms to a protocol; it does not
reshape the pipeline.

## Why a synthetic source is first-class

Hardware is scarce, slow to set up, and involves human participants under ethics
approval. If development depended on it, iteration would crawl and correctness
would be unverifiable. `SyntheticSource` generates two-subject signals with a
*known* true coherence, so:
- the entire loop runs on a laptop and in CI,
- INS estimators are validated against ground truth (does INS rise when true
  synchrony rises?),
- latency is measured deterministically.

`LSLSource` mirrors its output contract exactly, so swapping to hardware changes
one line of wiring.

## Clocking

There is exactly one clock: the LSL `local_clock`. Two acquisition systems plus
several aux sensors only become a coherent dyad recording if they share a time
base. Mixing in `time.time()` anywhere on the sample path silently corrupts
cross-subject alignment, which silently corrupts INS, which invalidates the
science. Hence the hard rule.

## Sham as a first-class signal path

Sham is the control condition that lets us attribute effects to *synchrony
feedback* rather than to reward, engagement, or practice. For that attribution
to hold, participants must not be able to tell sham from real. So sham is not
noise and not a constant — it is a *real other-dyad trajectory for the same
session/task*, pushed through the identical mapping. In code, the only
difference between real and sham is the source of the raw value; everything a
participant can perceive is byte-identical. Tests enforce this.

## Where the science can break (and what guards it)

| Failure | Guard |
|---------|-------|
| INS doesn't reflect true synchrony | `tests/test_ins.py` (ground-truth tracking) |
| Sham is distinguishable | `tests/test_sham_integrity.py` |
| Loop too slow for real-time | `tests/test_loop_and_safety.py` (latency budget) |
| Session exceeds safe duration | hard cap in `session/protocol.py` + test |
| Run not reproducible | provenance stamp (git SHA + config hash) on artifacts |

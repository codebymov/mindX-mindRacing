# mindX

Technical platform for **multiuser XR-enhanced neuromodulation** — fNIRS-based
Hyperscanning-Neurofeedback (Hyper-NF) for the START-program project *"Technical
foundations for multiuser XR-enhanced neuromodulation in digital healthcare."*

Two participants wear fNIRS caps and an XR headset; their interpersonal neural
synchrony (INS) is computed in near-real-time and fed back to both inside a
cooperative mixed-reality game, to test whether dyads can learn to increase
their neural synchrony and whether it transfers to cooperative behavior.

## Read this first
- **`CLAUDE.md`** — orientation for Claude Code: architecture, data flow, the
  hard rules. Start here.
- **`docs/ARCHITECTURE.md`** — why the system is shaped this way.
- **`docs/GLOSSARY.md`**, **`docs/PROTOCOL.md`**, **`docs/DECISIONS.md`**.

## Run it (no hardware)
```bash
cd backend && pip install -e ".[dev]"
python -m mindx_hnf.scripts.simulate   # full closed loop on synthetic data
pytest                                  # INS / sham / latency / safety tests
```

## Repo map
- `backend/` — Python real-time backend (the primary codebase).
- `unity/` — Unity XR "mind racing" game (C#); consumes feedback via a thin contract.
- `analysis/` — offline Bayesian analysis (WP5); strictly decoupled from the loop.
- `docs/` — architecture, glossary, protocol/compliance, decisions.
- `.claude/` — Claude Code config and slash commands.

## The five rules (full version in CLAUDE.md §4)
1. Real-time track is causal and non-blocking.
2. One clock of record: the LSL clock.
3. Sham is indistinguishable from real at the participant-facing layer.
4. Every run is reproducible from config + raw recording + git SHA.
5. Sessions are time-capped (~30 min) and abortable at any moment.

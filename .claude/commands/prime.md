---
description: Prime context on the mindX Hyper-NF project before starting work
---

Read these in order and give me a 5-bullet summary of the architecture and the
hard rules, then ask what I want to work on:

1. `CLAUDE.md` (root) — system overview, data flow, invariants
2. `docs/ARCHITECTURE.md` — why the system is shaped this way
3. `docs/GLOSSARY.md` — domain terms
4. `backend/mindx_hnf/contracts.py` — the typed seams everything conforms to
5. `docs/DECISIONS.md` — what's decided and what's open

Do NOT propose changes yet. Confirm you understand the two-track (real-time vs
persistence) split, the one-clock rule, and the sham-integrity rule.

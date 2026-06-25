# Glossary

Domain terms used throughout the codebase, for engineers without a neuroscience
background (and for Claude Code).

**fNIRS** — functional near-infrared spectroscopy. Measures brain activity via
changes in blood oxygenation using near-infrared light. Sits between EEG (high
time, low spatial resolution) and fMRI (high spatial, low time) and tolerates
movement well, which makes it suitable for naturalistic social interaction and
for children/adolescents.

**Hyperscanning** — recording two or more brains simultaneously during
interaction.

**INS (Interpersonal Neural Synchrony)** — the degree to which two interacting
people's brain activities are synchronized. Our single joint feedback feature.

**Hyper-NF** — Hyperscanning-Neurofeedback. Neurofeedback computed from the
*joint* (two-brain) signal rather than one person's amplitude.

**Neurofeedback (NF)** — training people to self-regulate their brain activity
by showing them a signal derived from it in near-real-time.

**HbO / HbR** — oxygenated / deoxygenated hemoglobin concentration changes; the
quantities fNIRS estimates after converting raw light intensity.

**OD (optical density)** — log-ratio of measured light intensity to a reference;
intermediate step from raw intensity to HbO/HbR.

**MBLL** — modified Beer-Lambert law; converts OD to HbO/HbR concentrations.

**TDDR** — temporal derivative distribution repair; an fNIRS motion-correction
method. We need a *causal* (online) variant on the real-time track.

**Short channel / short-distance regression** — short source-detector channels
capture scalp/systemic physiology (heart rate, etc.) rather than brain activity;
regressing them out improves the brain signal.

**rTPJ / PFC** — right temporoparietal junction / prefrontal cortex; target
brain regions for this study, selected from a meta-analysis.

**Dyad** — the pair of participants recorded together. Pseudonymized as
`dyad-NN`; individuals as `sub-NN`.

**Wavelet coherence** — a time-frequency measure of how consistently two signals
track each other in a frequency band; our INS estimator.

**Sham feedback** — control condition: participants receive a realistic but
non-contingent feedback signal (a replayed real signal from another dyad), so we
can separate true synchrony-learning from reward/engagement effects.

**Transfer task** — a screen-based neuroeconomic exchange game played before and
after training to test whether learned cooperation transfers without feedback.

**LSL (LabStreamingLayer)** — middleware for time-synchronized streaming of data
from multiple acquisition devices. Provides our single clock of record.

**BIDS** — Brain Imaging Data Structure; a standard layout for neuroimaging data
that makes datasets shareable and analysis-tool-compatible.

**DataLad** — git-based version control for data/artifacts.

**XR** — extended reality (umbrella over VR/AR/MR). Here, a mixed-reality headset
with color pass-through so participants see each other while a virtual racing
track is projected on the table between them.

**KPI examples from the proposal** — SUS (System Usability Scale, target avg >68),
PSSUQ (Post-Study System Usability Questionnaire, target avg ≤3), CRED-nf
(reporting checklist for neurofeedback studies).

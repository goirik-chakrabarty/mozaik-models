# CLAUDE.md — mozaik-models/experanto (P1 project working agreement)

Architecture/detail for P1 (MOZAIK simulation → Experanto export) lives in the **root**
`../../CLAUDE.md` (P1 reference section) and `../../docs/`. This file is the *working agreement*.

## What this project is
Convert MOZAIK V1 spiking-network output (`SelfSustainedPushPull`) into Experanto-format spike +
screen shards for neural-foundation-model training. If a task does not serve that sentence, it is out of scope.

## Non-negotiable rules
1. **Never edit vendored/pinned deps** — `mozaik/` (simulator), `experanto/` lib, and NEST run
   inside the Apptainer image `../../mozaik-sif/mozaik-opt.sif`. New code goes in `experanto/` here.
2. **No silent runs.** Every result-bearing run appends to `experiments/LOG.md` (template there);
   stamp its run dir with `../../scripts/stamp_run.py`.
3. **Non-destructive.** Never overwrite a prior datastore/export/run; new runs write to new paths.
   Simulation-output dirs (`*_TEST3_EXPT/`, `SelfSustainedPushPull_*`) are gitignored — never commit them.
4. **Pre-register** reads + stop conditions before running (see `../../docs/plan/PLAN_P1_determinism.md`
   as the worked example). Do not move a threshold after seeing the numbers.
5. **Sanity-gate the pipeline.** Before/after any change touching the sim or export, re-run the P1
   golden (`bash ../../scripts/sanity/run_all.sh P1`) and confirm GREEN. Reproduction QC:
   `analysis/verify_p1_reproduction.py` (in-container).
6. **Provenance = commit-tuple.** A P1 result pins `mozaik` + `mozaik-models` + `experanto` +
   the SIF image. Record all in the run's `provenance.json`.

## Key facts
- Seeds: `mozaik_seed=1023`, `pynn_seed=5`, `noise_seed = trial*1000` (per-trial noise; connectivity invariant).
- Determinism is **proven** (bit-identical spikes under fixed seeds) — safe to refactor against the P1 golden.
- `spikes.npy` unpickling needs `neo` (container only); exported `.npy`/`.json` are plain.

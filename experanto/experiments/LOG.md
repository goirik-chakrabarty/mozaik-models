# Experiment Log — P1 (MOZAIK simulation → Experanto export)

Append one block per run. This is the source of truth for P1 results — no silent runs.
Newest at top. Superseded blocks are annotated, never deleted. Template: `docs/RESEARCH_DIRECTORY_GUIDE.md` §11.1.

---

## 2026-07-02 — P1 reproduce-from-record gate (Week-2 gate #3) 🟢 PASS — record alone reproduces the metric
- **Goal:** Prove the ledger works — re-execute the P1 reproduction result using *only* the logged
  record (commit-tuple + config + command + data paths), and match the recorded metric. This is the
  decisive Week-2 sanity gate (`docs/plan/week-2-ledger.md` gate #3).
- **Commit-tuple (now valid for P1):** mozaik `005de9b`, mozaik-models `25809dd`, experanto `327c3a0`
  (all clean, committed this session); container `mozaik-opt.sif` (2026-02-09). Vendored
  neuralpredictors/sensorium still dirty but not P1 deps.
- **Method:** ran the command recorded in the prior run's `config.json`, output redirected to a fresh
  gate dir (record untouched), then diffed against the recorded `metrics.json`.
- **Result:** 🟢 PASS. trial0/1/2 = 42/42 segments identical, spikes 10,333,593 / 10,349,230 /
  10,385,555 — exact match to the record. The record is self-sufficient to reproduce the result.
- **Caveats:** the reproduced verify re-reads the same on-disk datastores, so this validates the
  *ledger→metric* loop and P1's now-clean pins; the fresh-simulation reproduction was separately
  proven (14602650 vs 1_TEST3_EXPT, entry below).
- **Run dir:** `experiments/2026-07-02_p1-reproduce-from-record/` (provenance.json, result.json, run.log)
- **Artifacts:** `analysis/verify_p1_reproduction.py`; `scripts/stamp_run.py` (overlay).

## 2026-07-02 — P1 reproduction (test3, same-seed determinism) 🟢 PASS — simulation is bit-reproducible
- **Goal:** Prove the MOZAIK simulation is bit-reproducible under fixed seeds — the Week-0 P1
  *reproduction* golden the handoff left blocked (`docs/plan/week-0-preflight.md`). Establishes the
  "same input → same output" baseline required before any simulation refactor.
- **Config:** `experiments/2026-07-02_p1-reproduction_test3/config.json` (test3: 3 stimuli × 3 trials)
- **Seeds:** mozaik_seed=1023, pynn_seed=5, noise_seed=trial*1000
- **Commit-tuple:** mozaik `e836c42` (dirty), mozaik-models `04f2951` (dirty), experanto `2d1fdee` (dirty);
  container `mozaik-sif/mozaik-opt.sif` (2026-02-09). ⚠️ trees dirty — see `docs/plan/audit/baseline-commits.md`.
- **Dataset:** fresh re-sim (SLURM `14602650`, medium96s, array 0-2, COMPLETED 2026-07-02 ~10:59) at
  the experanto root, vs reference `mozaik-models/experanto/1_TEST3_EXPT` (2026-06-02).
- **Method:** load every `Segment*.pickle` from fresh + reference datastore; compare `.spiketrains`
  neuron-by-neuron (count · per-neuron shape · `np.array_equal` on spike times). Byte-diff of pickles
  is NOT used — Neo embeds nondeterministic memo/object ids (all 42 pickles byte-differ despite
  identical spike data).
- **Metrics:** all 3 trials IDENTICAL, 42/42 segments each. Spikes fresh==ref per trial:
  trial0=10,333,593 · trial1=10,349,230 · trial2=10,385,555.
- **Runtime:** ~20 min single-core in `mozaik-opt.sif` (reconstructs ~37,500 spiketrains × 42 segments
  × 2 × 3 trials). CPU-bound; no GPU.
- **Result / decision:** 🟢 PASS. Fresh re-run reproduces the June-2 reference exactly at the datastore
  level. Determinism baseline established. Since export is a deterministic transform, the exported
  `spikes_sha256` in `docs/plan/audit/golden/P1.json` is implied to reproduce too (not separately re-run).
- **Caveats / honesty:** (1) datastore spike counts (~10.3M/trial, all recorded spiketrains) differ
  from P1.json's export n_spikes (~1.48M/trial, exported subset) — different representations, both
  internally consistent, each fresh==ref. (2) Export-level hash equality was inferred, not executed;
  run the export on the fresh datastores if a literal shard-hash match is wanted. (3) Commit-tuple is
  dirty, so provenance is under-pinned until Week-1 baseline commits.
- **Run dir:** `experiments/2026-07-02_p1-reproduction_test3/`
- **Artifacts:** reproducer `analysis/verify_p1_reproduction.py`; golden `docs/plan/audit/golden/P1_reproduction.json`;
  gate golden `docs/plan/audit/golden/P1.json` + `capture_p1_export.py`.

## 2026-06-02 — P1 test3 simulation + Experanto export (BACKFILLED / reconstructed) 🟢 output on disk
- **Goal:** the original test3 sim→export whose shard is the basis of the P1 gate golden. Backfilled
  from on-disk artifacts (no live LOG existed yet) — reconstructed, not an authoritative logged run.
- **Commit-tuple (reconstructed, pre-Week-0 dirty baseline):** mozaik `e836c42`-dirty ·
  mozaik-models `04f2951`-dirty · experanto `2d1fdee`-dirty (see `docs/plan/audit/baseline-commits.md`).
  ⚠️ pins under-specified (trees were dirty at run time).
- **Config / seed:** test3 = 3 stimuli × 3 trials; mozaik_seed=1023, pynn_seed=5, noise_seed=trial*1000.
- **Data:** datastores `1_TEST3_EXPT/` → export `/mnt/vast-react/projects/neural_foundation_model/mozaik_data_test3/trial{0,1,2}`.
- **Metrics (from `docs/plan/audit/golden/P1.json`):** per-trial exported n_spikes 1,480,099 / 1,496,296 /
  1,491,426; spikes_sha256 e06b79dc… / e823f6ad… / 1bd89176…; end_time 12.446 s; all export-fidelity checks pass.
- **Result / decision:** 🟢 the frozen reference export; all P1 gate checks green and reproducible.
- **Caveats / honesty:** reconstructed row — provenance rebuilt after the fact; commit-tuple was dirty.
- **Run dir:** n/a (predates run-dir convention); reference output at the mozaik_data_test3 path above.
- **Artifacts:** `docs/plan/audit/golden/P1.json`, `capture_p1_export.py`.

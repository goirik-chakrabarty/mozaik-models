# Experiment Log — P1 (MOZAIK simulation → Experanto export)

Append one block per run. This is the source of truth for P1 results — no silent runs.
Newest at top. Superseded blocks are annotated, never deleted. Template: `docs/RESEARCH_DIRECTORY_GUIDE.md` §11.1.

---

## 2026-07-02 — NTASKS scaling sweep (P1 sim) 🟢 DONE — optimum @ NTASKS=12; severe negative scaling beyond
- **Goal:** measure how MOZAIK sim wall-time scales with MPI tasks. Sweep `NTASKS ∈ {4,8,12,16,24}`,
  everything else fixed (`CPUS_PER_TASK=4`, `OMP=4` ⇒ cores = NTASKS×4; identical workload = copy of `0_0.json`).
- **Result (all started 23:35:24, each own full node, AllocCPUS=192):**
  | NTASKS | 4 | 8 | **12** | 16 | 24 |
  |---|---|---|---|---|---|
  | Elapsed | 40:51 | 21:08 | **16:55** | 1:16:52 | **>150 min (TIMEOUT)** |
  | vs nt12 | 2.4× | 1.25× | **1.0×** | 4.5× | ≥8.9× |
  jobs: nt4=14614500 · nt8=14614501 · nt12=14614503 · nt16=14614504 · nt24=14614505(TIMEOUT).
- **Finding:** **U-shaped curve, optimum at NTASKS=12; adding ranks past ~12 makes the sim dramatically
  SLOWER** (nt16 4.5×, nt24 never finished). Not the expected flat curve — it's actively negative.
- **Root cause (from nt12 baseline `.err` 14602650):** only ~9% of wall is NEST `sim.run`; ~88% is
  per-presentation `sheet.get_data()` (spike→Neo + **MPI gather to root**, `mozaik/models/__init__.py:180-189`).
  Gather cost grows with rank count ⇒ more ranks inflate the 88% faster than they shrink the 9%.
  Tell: blank presentations `took 76 s, of which 0 s simulation` (×22; no file read, ~49 ms run) — pure
  get_data. Config `reset:False`, `null_stimulus_period:0.0`.
- **Consequence (answered a user question):** environment/apptainer/BLAS/thread tuning **cannot**
  meaningfully speed this up (Amdahl ceiling ≈1.1×). Run production at **NTASKS≈12**. Real speedups are
  code-level: reduce recorded neurons (`to_record`); avoid `get_data` on blanks (~28% of runtime).
- **Pre-registered stop condition (honored):** `TIME=02:30:00`; nt24 hit it → recorded ">150 min".
- **Isolation (non-destructive):** each arm read an identical copy of `0_0.json` from
  `/data/MOZAIK/mozaik_chunk_scaling/{N}_0.json`; array index = N ⇒ distinct output
  `SelfSustainedPushPull_trial{N}_chunk0` (existing test3 trials 0/1/2 untouched).
- **Configs:** `mozaik/cluster/experiments/ntasks-scaling/sim-scale-nt{4,8,12,16,24}.conf`
  (new per-experiment subfolder convention — see `cluster/README.md`).
- **Commit-tuple:** mozaik **`fb85e2e`** (dirty: sweep confs + README) · mozaik-models `4224a6b` (clean) ·
  experanto `327c3a0` (clean) · container `mozaik-opt.sif`.
- **Gate:** `capture_gate.py` re-run after adding confs → all 6 standard scenarios byte-identical (PASS).
- **Run dir:** `experiments/2026-07-02_ntasks-scaling/` (design, `sacct_results.txt`, results table + root-cause).

---

## 2026-07-02 — REFACTOR-02: consolidate `run-*.sbatch` into a config-driven launcher 🟢 PASS — behavior-preserving, committed
- **Goal:** Remove the `mozaik/cluster/` launcher duplication (test33 §6). Reading the 12 `run-*.sbatch`
  showed 7 live in 3 families (sim/export/psth) sharing ~30 lines of boilerplate + 5 legacy (4 launch
  interactive `jupyter lab` via the old `compose.sh`; 1 non-apptainer pyenv). Plan:
  `docs/plan/PLAN_REFACTOR_sbatch_consolidation.md`.
- **Change (mozaik `csng`):** 6 live sim/export launchers → `cluster/experiments/{sim,export}-{prod,test3,test33}.conf`
  (human-readable, single source of truth) + `cluster/submit.sh` (conf → `sbatch` directives) +
  `cluster/run_job.sh` (bodiless; sources conf → `compose-{array,export}.sh`) + `cluster/README.md`.
  5 legacy → `cluster/legacy/`. `run-psth-datastore.sbatch` left as-is.
- **Commit-tuple (clean, pin_valid=True):** mozaik **`fb85e2e`** (csng); mozaik-models `3131034`; experanto
  `327c3a0`; container `mozaik-opt.sif`.
- **Pre-registered stop condition (NOT moved):** behavior-preserving ⇒ succeeds only if, for every one of
  the 6 live scenarios, the new launcher reproduces the old exactly on (A) effective `#SBATCH` directives
  and (B) the composed `apptainer exec` argv. Any diff ⇒ REVERT.
- **Gate:** `cluster/_gate/capture_gate.py` captures both axes via a **stub apptainer (bash function** — wins
  over the module-loaded PATH; never runs the real pipeline). Baseline golden captured from the OLD
  launchers → `docs/plan/audit/golden/P1_launch.json` (deterministic: re-capture identical). New
  config+wrapper vs golden: **all 6 byte-identical** (`sim/export × prod/test3/test33`). P1 export golden
  (`run_all.sh P1`) GREEN (unaffected).
- **Preserved quirks (not fixed here):** `sim-prod` ARRAY=0-23 (nominal 20×12 would be 0-239); `export-test33`
  omits `DATASTORE_PREFIX` where `export-test3` sets it — both reproduced verbatim, logged as follow-ups.
- **Incident (honest):** the first gate harness used a PATH-based apptainer stub; because `module load
  apptainer` (the alloc pre-loads apptainer; launchers reload it) re-prepends the real binary, the real sim
  actually ran and its runner's `rm -rf "$DIR_NAME"` **destroyed the reusable `trial1` scratch datastore**
  (REFACTOR-01 result unaffected — committed; trial0/trial2 intact; `1_TEST3_EXPT` reference untouched).
  Fixed by stubbing apptainer as an exported bash function (beats PATH) + a parent+child guard that aborts
  unless the stub provably wins. trial1 can be regenerated from the held alloc if needed.
- **Result / decision:** 🟢 PASS → committed. REFACTOR-02 exit criteria met.
- **Run dir:** `experiments/2026-07-02_refactor-02_sbatch-consolidation/` (provenance.json, pin_valid=True).
- **Artifacts:** `mozaik/cluster/_gate/capture_gate.py`; golden `docs/plan/audit/golden/P1_launch.json`;
  plan `PLAN_REFACTOR_sbatch_consolidation.md`; `mozaik/cluster/README.md`.

---

## 2026-07-02 — REFACTOR-01: post-blank 49 ms → `POST_BLANK_MS` constant 🟢 PASS — behavior-preserving, committed
- **Goal:** Remove the 49 ms post-blank magic number (≥4 bare literals across sim + export) by
  extracting named constants, and document the sim↔export timeline invariant that keeps them equal.
  Plan: `docs/plan/PLAN_REFACTOR_postblank_constant.md`.
- **Change:** `mozaik/experiments/vision.py` — `POST_BLANK_MS = 49` (int) replaces the two `49`
  literals in `RandomizedExperanto`'s `InternalStimulus`. `mozaik-models/experanto/mozaik2experanto.py`
  — `POST_BLANK_MS = 49.0` (float) replaces the three `49.0` literals in `MozaikScreenExporter`. Both
  carry a comment stating the sim↔export invariant.
- **Commit-tuple (P1 repos clean, pin_valid=True):** mozaik `30ff0e3` (csng), mozaik-models `1bf8648`
  (main), experanto `327c3a0` (clean-spikeinterpolator); container `mozaik-opt.sif` (2026-02-09).
  (The vendored top-level `sensorium/` — previously the only dirty tree — was deleted this session;
  the P2/P3 copy `latent_space_model/sensorium` remains. sensorium is not a P1 dep.)
- **Pre-registered stop condition (NOT moved):** behavior-preserving ⇒ succeeds only if the re-run is
  bit-identical; any difference ⇒ REVERT (a typo broke value-preservation).
- **Verification — BOTH gates GREEN:**
  - **Sim:** fresh on-node test3 re-sim (alloc `14603006`/`c0065`, mpirun -n 12) with the refactored
    `mozaik` → `verify_p1_reproduction.py` vs `1_TEST3_EXPT` = **42/42 segments identical × 3 trials**;
    datastore spikes 10,333,593 / 10,349,230 / 10,385,555 == ref.
  - **Export:** re-export of the fresh datastores with the refactored `mozaik2experanto.py` to a fresh
    prefix (`mozaik_data_test3_REFACTOR_VERIFY`, non-destructive) → `capture_p1_export.py` fingerprint =
    **all 3 trials `spikes_sha256` MATCH `docs/plan/audit/golden/P1.json`** (n_spikes 1,480,099 /
    1,496,296 / 1,491,426; entry_modalities MATCH; every gate check passes). `IDENTICAL_ALL_PASS`.
    This also closes the prior reproduction entry's caveat that export-hash equality was "inferred,
    not executed" — it is now executed on refactored-code output.
- **Companion (noise_seed correctness, requested):** `verify_noise_seed_trials.py` on the same fresh
  datastores, trial0(ns=0) vs trial1(ns=1000): connectivity PASS (param hash minus noise_seed identical,
  `bb08d8fb8af5`); noise-varies PASS (**42/42 segments differ**). Confirms identical network + fully
  decorrelated per-trial noise.
- **Result / decision:** 🟢 PASS both gates → committed per repo (mozaik `30ff0e3`, mozaik-models
  `1bf8648`). REFACTOR-01 exit criteria met; invariant documented in both constants' comments.
- **Run dir:** `experiments/2026-07-02_refactor-01_postblank-constant/` (provenance.json, pin_valid=True).
- **Artifacts:** `analysis/verify_p1_reproduction.py`; `analysis/verify_noise_seed_trials.py`;
  `docs/plan/audit/golden/capture_p1_export.py` + `P1.json`; plan `PLAN_REFACTOR_postblank_constant.md`.

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

# Experiment Log — P1 (MOZAIK simulation → Experanto export)

Append one block per run. This is the source of truth for P1 results — no silent runs.
Newest at top. Superseded blocks are annotated, never deleted. Template: `docs/RESEARCH_DIRECTORY_GUIDE.md` §11.1.

---

## 2026-08-04 — single-chunk sim + INLINE export on csng (workflow 2, three-seed migration) 🟢 PASS
- **Goal:** validate (a) the three-stream seed migration of `param/defaults` (so sims run on
  `csng-mozaik-update`) and (b) the new inline export path in `run.py` (`--export`) that simulates one
  chunk and exports a full Experanto shard next to the datastore in the same process.
- **Commit-tuple:** mozaik **`csng-mozaik-update @ 9de2c35`** (seed_refactor + #5 + #6) · mozaik-models
  `main-mozaik-update` with `param/defaults` **migrated in place** to `model_seed=1023`/`simulation_seed=1`/
  `experiment_seed=0` (old `{pynn_seed,mozaik_seed,lgn_stepcurrentsource_noise_seed}` kept as a comment) and
  `run.py` `--export` added (uncommitted) · experanto (sibling `goirik/experanto`) · SIF
  `mozaik-opt-qpatch_2026-07-14.sif`.
- **Config:** compute node c0013, direct `mpirun -n 12 --bind-to none --oversubscribe python -u run.py nest 12
  param/defaults results_dir '\''/data/_inline_sim_test_26-08-04/'\'' simulation_seed 1000
  trial0_chunk0_3seed_inline --export`. TRIAL=0/CHUNK=0, `CHUNK_DIR=/data/MOZAIK/mozaik_chunk_test3`, OMP=1.
  test3 = 2 img + 1 video. Sim run time 583 s; inline export +~25 s (rank 0).
- **Non-destructive:** output to a **fresh** `/data/_inline_sim_test_26-08-04/` scratch path; no datastore or
  export overwritten. The Jun-2 reference `/data/mozaik_data_test3/` used only for comparison.
- **Reads (pre-registered):** (a) sim runs on csng (no seed `KeyError`); (b) inline shard structure matches
  the reference (same stimuli/network); (c) timeline invariant holds; (d) spikes DIFFER from the reference
  (different `simulation_seed` → different noise, same network).
- **Metrics:** shard at `<datastore>/experanto/{responses,screen}`. Structure vs reference: n_signals 37500 ✓,
  CSR spike_indices 37501 ✓, stimuli_order ✓, timestamps 307 frames EXACT ✓, combined_meta 8 entries ✓,
  screen pixels 3 files EXACT ✓. Invariant: spike end_time == screen[-1] == 12.446 s ✓. Noise: 1 523 360 new
  vs 1 480 099 ref spikes, not identical ✓ (as designed).
- **Result / decision:** 🟢 PASS. Seed migration lets csng simulate; workflow 2 produces a correct full shard
  inline. **Not** a byte-equivalence to the old scheme (expected — `seed_refactor` changes noise bit-for-bit).
- **Caveats / honesty:** (1) `simulation_seed` overridden to 1000 (nonzero; NEST rejects 0). (2) The cluster
  **sim runner still passes `lgn_stepcurrentsource_noise_seed`** — must be repointed to `simulation_seed`
  before workflow 1's sim step runs on csng via `submit.sh` (follow-up). (3) Only `param/defaults` migrated;
  `defaults_2024` + `params/param_*` still old. (4) csng lacks perf's get_data speedups (ToDo reconcile).
- **Run dir:** `/data/_inline_sim_test_26-08-04/SelfSustainedPushPull_trial0_chunk0_3seed_inline_____simulation_seed:1000/`
  (datastore + `experanto/` shard + `launch.sh` + `sim.log`).

---

## 2026-08-04 — test3 full export end-to-end on `csng-mozaik-update` (export-path validation) 🟢 PASS
- **Goal:** validate the DataStore→Experanto **export** end-to-end after switching the live `mozaik/`
  checkout from `perf` to `csng-mozaik-update` (the branch with review #6's relocated exporter
  `mozaik/tools/experanto_export.py`). Confirms the earlier import-only fix holds through a full run, and
  that the relocated/parametrized exporter reproduces the pre-#6 output. Handoff:
  `../../docs/handoffs/26-08-04_12-29_HANDOFF_EXPORT_IMPORT_BREAK_MOZAIK_ON_CSNG.md`.
- **Commit-tuple:** mozaik **`csng-mozaik-update @ 9de2c35`** (seed_refactor + #5 + #6) · mozaik-models
  `main-mozaik-update` (export shim `0430987` → `mozaik.tools.experanto_export`) · experanto (sibling
  `goirik/experanto`) · SIF `mozaik-opt-qpatch_2026-07-14.sif` (neo 0.14.4).
- **Config:** ran on a compute node directly via `cluster/apptainer-compose-export.sh` (not sbatch),
  replicating `run_job.sh`'s export branch with `export-test3.conf` values (`N_CHUNKS=1`, `CHUNK 0`,
  `BATCH_SIZE=1`, `DATASTORE_PREFIX=1_TEST3_EXPT`, `CHUNK_DIR=/data/MOZAIK/mozaik_chunk_test3`), for
  `TRIAL ∈ {0,1,2}`. Input datastores use the **old** `noise_seed:{0,1000,2000}` naming — export's glob is
  scheme-agnostic and matched them. OMP=4. ~26 s/trial (load-bound; csng lacks perf's get_data speedups, but
  test3 is tiny so immaterial).
- **Non-destructive:** wrote to a **fresh** path `OUTPUT_PREFIX=/data/mozaik_data_test3_csng_26-08-04/trial`;
  the prior `/data/mozaik_data_test3` (Jun-2 reference) was left untouched and used as the comparison target.
- **Reads (pre-registered):** (a) export completes for all 3 trials; (b) timeline invariant holds
  (spike `end_time` == `screen/timestamps.npy[-1]`); (c) output byte-identical to the Jun-2 reference export
  (same input datastores) — validates #6's relocation/parametrization is behaviour-preserving.
- **Metrics:** all 3 trials 37500 units, 7 segments (3 stim / 4 blank), 307 frames, end_time 12.446 s.
  Invariant holds all 3. **EXACT match to reference:** spikes (1 480 099 / 1 496 296 / 1 491 426), CSR
  `spike_indices` (37501), `timestamps.npy`, `combined_meta.json` (8 entries), screen pixel arrays (3 files).
- **Result / decision:** 🟢 PASS. The export runs and reproduces the reference exactly on `csng-mozaik-update`;
  the import break is fully resolved end-to-end.
- **Caveats / honesty:** (1) qpatch SIF used via explicit `SIF_IMAGE` override — csng's compose default
  reverted to `mozaik-opt.sif`. (2) Reads from `/data` only; the `/ws` WORKSPACE bind + S32000 launchers are
  perf-only (ToDo reconcile). (3) Export needs no seeds, so the pending three-seed migration doesn't gate it.
- **Run dir:** output `/data/mozaik_data_test3_csng_26-08-04/trial{0,1,2}`; compare script
  `analysis/_compare_test3_csng_vs_ref.py` (one-off).

---

## 2026-07-30 — test3 `simulation_seed` variability on `seed_refactor` (mechanism verification) 🟢 PASS
- **Goal:** verify Tibor Rózsa's `seed_refactor` three-seed scheme (`model`/`simulation`/`experiment`)
  gives the trial-variability property at full model scale: same network, different noise per trial when
  only `simulation_seed` varies. Companion to `../../docs/audits/26-07-30_SEED_REFACTOR_VS_NEST_SEED_RENAME.md`.
- **Commit-tuple:** mozaik `seed_refactor @ 72b4cd1` (Tibor's refactor, replaces our
  `lgn_stepcurrentsource_noise_seed`) · mozaik-models: **isolated scratch copy** of `main-mozaik-update @
  962825b` (code+param+or_map) with `param/defaults` seeds migrated to the 3-seed schema — NOT committed
  (scratch verification) · experanto `clean-spikeinterpolator` · SIF `mozaik-opt-qpatch_2026-07-14.sif` (neo 0.14.4).
- **Config / seed:** `param/defaults` migrated → `model_seed=1023`, `experiment_seed=0`,
  `simulation_seed ∈ {1000, 2000, 3000}` (one per trial). test3 = 2 img + 1 video; TRIAL=0/1/2 select the
  three chunk files (identical stimuli), CHUNK=0. 12 MPI ranks, OMP=1. sbatch array `15103074_[0-2]`,
  medium96s/sapphirerapids, ~12 min/run in parallel (WALL 739/736/742 s).
- **Reads (pre-registered):** (a) connectivity params identical across trials once `simulation_seed` is
  excluded; (b) per-segment spikes differ across trials. Stimuli confirmed identical across the three
  chunk files; `RandomizedExperanto` ignores the chunk `noise_seed` field (only `simulation_seed` drives noise).
- **Metrics:** connectivity `parameters.json` (seed excluded) **identical** across all 3 (`model_seed=1023`,
  hash `88e188e8f583`). Spikes: **42/42 segments differ, 0 identical** (e.g. Segment0 46 685 / 47 207 / 47 012).
- **Result / decision:** 🟢 PASS. `simulation_seed` on `seed_refactor` yields identical connectivity +
  different noise per trial, at full test3 scale. Mechanism confirmed viable.
- **Caveats / honesty:** (1) ⚠️ `simulation_seed=0` is a **hard NEST error** (`rng_seed ∈ (0, 2^32-1)`);
  the old `noise_seed = trial*1000+chunk` gives 0 for trial0/chunk0 → migration must add a nonzero base.
  (2) Old `mozaik_seed`+`pynn_seed` collapse to one `model_seed` → network identity differs from the old
  scheme; **do not mix schemes within a dataset** (S32000 repair stays on old `perf` code). (3) Scratch
  run — datastores in session scratchpad, not permanent; not a dataset-production run.
- **Run dir:** scratch `.../scratchpad/SR_TEST3/` (isolated project copy + `run`/`sbatch`/`compare` scripts).
- **Artifacts:** `../../docs/audits/26-07-30_SEED_REFACTOR_VS_NEST_SEED_RENAME.md` §3b; sbatch
  `sbatch_seedrefactor_test3.sbatch`; compare `compare_seedrefactor_trials.py`.

## 2026-07-14 — S32000-all-videos ONE FULL TRIAL (P1 sim → export, ceph-ssd) 🟠 PRE-REGISTERED / launching
- **Goal:** produce ONE full trial (trial 0) of the S32000-all-videos Experanto dataset — 41,723 stimuli
  (31,706 img + 10,017 unique vid) presented to LSV1M V1 — end-to-end, and validate it before committing to
  all 3 trials (~465–500k core-h). Plan: `docs/plan/plan-for-running-full-dataset.md`; sizing audit:
  `docs/plan/audit/26-07-14_S32000_FULL_RUN_SIZING.md`.
- **Commit-tuple:** mozaik `perf/neo14-getdata-speedup @ 5811092` (RESULTS_DIR/WORKSPACE redirect) ·
  mozaik-models `main-mozaik-update @ b7d9916` (generate_chunks per-frame video cost; this LOG entry
  uncommitted at pre-reg) · experanto `clean-spikeinterpolator` · SIF `mozaik-opt-qpatch_2026-07-14.sif` (neo 0.14.4).
- **Config / seed:** `param/defaults` (mozaik_seed=1023, pynn_seed=5); trial 0, noise_seed=trial*1000+chunk
  = chunk (0..63). Datastore redirected to ceph-ssd via RESULTS_DIR=/ws/S32000_full/datastores (WORKSPACE
  bound to /ws). 12 ranks (12×4), OMP=4, node-exclusive medium96s/sapphirerapids. Conf
  `cluster/experiments/S32000/sim-S32000-full.conf` (ARRAY=0-63, N_CHUNKS=64).
- **Reads (pre-registered):** input_screen materialized (41,723 yml+npy, 37 GB, 120 sessions, frame
  byte-match spot-check PASS); 64 time-balanced chunks (per-frame cost, all ~43.9 h est, 636–669 stim/chunk,
  total 41,723). Gate `capture_gate.py --cmp` PASS (golden byte-identical). Runtime argv verified:
  RESULTS_DIR + /ws bind present; S500 (`/project` trial0/1/2) protected because rm/write target /ws.
- **Stop conditions (pre-registered):** (1) each chunk sim finishes < 48 h (target ~44 h); (2) 64/64
  datastores present on /ws (~4.3 TB); (3) export validation — responses `end_time` == screen
  `timestamps[-1]`, 35 ms video frames, per-image 497+49 ms, tier/modality counts, CSR `spike_indices`
  well-formed. Falsification logged honestly.
- **Result / decision:** _(pending — update on completion)_. Expected ~155–168k core-h, export ~232 GB.
- **Artifacts:** confs `cluster/experiments/S32000/{sim,export}-S32000-full.conf`; launchers
  `mozaik/slurm_s32000_full/`; run root ceph-ssd `S32000_full/{input_screen,chunks,datastores,export}`.

## 2026-07-14 — S32000-all-videos PILOT (P1 sim → export, ceph-ssd) 🟢 DONE — full-run numbers collected
- **Goal:** de-risk + measure the S32000-all-videos pipeline before committing to the full run. First
  end-to-end exercise of the **VIDEO export path** (`movie_frame_duration_ms=35`, untested at S500), and
  collect hard numbers (sim wall, raw GB, export GB, core-hours) to size the full 3-trial run.
- **Commit-tuple:** mozaik `perf/neo14-getdata-speedup` @ `f7eeba8` · mozaik-models `main` (dirty:
  `materialize_subset_screen.py` `--selection-json`; this LOG entry) · experanto `clean-spikeinterpolator` ·
  SIF `mozaik-sif/mozaik-opt-qpatch_2026-07-14.sif` (production, neo 0.14.4).
- **Config / seed:** pilot chunk = **30 images + 9 videos** (4 Clip@300f, 1 DotSeq@450f, 2 Monet2@900f,
  2 Trippy@900f) = **99 presentations** (39 stim + 60 blank), **212.2 s** timeline (**87% video** — matches
  the full run's ~90%). `param/defaults` (mozaik_seed=1023, pynn_seed=5); TRIAL=7/noise_seed=7000 for the
  sim (collision-avoidance vs S500 trial0); 12 ranks (12×4), OMP=4, node-exclusive.
- **Storage:** ceph-ssd workspace `/mnt/ceph-ssd/workspaces/ws/nix00014/u18196-mozaik_s32000/S32000_pilot/`
  (mirrors final-run I/O; NOT project vast). Input read + datastore write + export all on ceph-ssd.
- **Sim metrics (job 14858445):** wall **8862 s** (setup 178 s + mozaik-reported 8681 s). NEST simulator
  **1481 s (17%)**, **Mozaik overhead 7201 s (82%)** — wall is dominated by per-presentation get_data, NOT
  NEST. Per-presentation wall: **image/blank ≈ 52 s**, **video ≈ 0.55 s/frame + ~48 s base** (300f→~205 s,
  900f→~570 s). Raw datastore **4.9 GB** (23.1 MB/sim-s). **177.6 core-hours** (72 billed cores × 2.47 h).
- **Export metrics (job 14860177):** wall **340 s** (99% = datastore load, the neo14 get_data path).
  Output **267 MB**: responses **221 MB** (spikes.npy 220 MB, 37500 units) + screen **47 MB** (9216 B/frame,
  f32 36×64). Input screen **47 MB**.
- **VIDEO export path VERIFIED 🟢:** timeline aligned (responses `end_time`=212.191 s == screen
  `timestamps[-1]`=212.191 s == export total 212191 ms); video frames at **35 ms** (5250 @ 0.0350 s);
  per-image **497 ms + 49 ms post-blank**; frame counts 4×300/1×450/4×900 exact; tiers train=35/val=4;
  modalities 30 img + 9 vid + 61 blank.
- **FULL-RUN PROJECTION (per trial: 31,706 img + 10,017 vid = 41,723 stim; 4,253,182 video frames; ~46 h
  timeline = ~780× pilot):** **core-hours ≈ 140k/trial → ~420k for 3 trials** (presentation-model cross-check
  agrees). NOTE: predecessor handoff's 42,021 / 4,521,382 / 48.8 h used the *non-deduped* 10,315 videos;
  correct deduped figures (10,017 unique) are ~5–6% smaller — projections above use the corrected values.
  Raw datastore **~4 TB/trial** transient (~10 GB/chunk @ ~350 chunks; stream-delete).
  Export **~225 GB/trial** (spikes ~183 GB + screen ~42 GB) → **~675 GB for 3 trials**. Input screen
  (once) **~42 GB**. Chunking: per-trial serial wall ~2037 h → **~370 chunks/trial @ ~5.5 h/chunk** (~1110
  array tasks for 3 trials).
- **Result / decision:** 🟢 pipeline + video export validated on ceph-ssd; numbers collected. **Storage is
  cheap (~675 GB export); the cost driver is ~440k core-hours** — surfaced to user before committing to the
  full 3-trial run (see Open Question re: 1-trial fallback).
- **Caveats / honesty:** (1) Export needed a **pilot-only fix** — chunk `7_0.json` is trial-0 content
  (records carry trial=0) run under sim TRIAL=7; export.py filters segments by `stim_params['trial']==TRIAL`,
  so first attempt (TRIAL=7, job 14860163) matched 0 segments and crashed in `finalize()`. Fixed by a symlink
  `datastores/…trial0…:0 → …trial7…:7000` + re-run as TRIAL=0. The **full run has no such mismatch**
  (generate_chunks stamps each record's trial to match its file/sim trial). (2) Projections extrapolate one
  video-heavy chunk linearly by timeline; the pilot's 87%-video mix closely matches the full run, but true
  per-chunk variance is unmeasured. (3) Commit-tuple has uncommitted changes (materialize `--selection-json`).
- **Run dir / artifacts:** launchers `mozaik/slurm_s32000_pilot/26-07-14_pilot_{sim,export}_cephssd.sbatch`
  + `pilot_{run,export}_cephssd.sh`; confs `mozaik/cluster/experiments/{sim,export}-S32000-pilot.conf`
  (superseded by ceph-ssd launchers); output on ceph-ssd `S32000_pilot/export/trial0/`.

## 2026-07-14 — P1 sim speedup BEYOND golden: quantities registry-memo patch (lever B) 🟢 DONE — 741s < golden 1015s
- **Goal:** make the P1 test3 sim faster than the neo12 golden without breaking correctness
  (`docs/audits/26-07-13_P1_SIM_SPEEDUP_BEYOND_GOLDEN.md` §1). Follows the neo `_contains` O(1) fix (CP2).
- **Commit-tuple:** mozaik `perf/neo14-getdata-speedup` (this checkpoint) · mozaik-models `main` (LOG entry only) ·
  experanto `clean-spikeinterpolator` · SIF `mozaik-sif/mozaik-opt-neopatch_2026-07-13.sif` + quantities
  `patches/quantities-0.16.4/registry.py` bind-mounted (baked SIF: `mozaik-opt-qpatch_2026-07-14.sif`).
- **Method / lever:** re-profiled the patched sim (perf1, nt12, rank-0 cProfile). After `_contains` O(1),
  the top addressable cost is quantities unit-hashing: `Dimensionality.__hash__` (4.55M calls / 184s) calls
  `hash(unit_registry['dimensionless'])` on every hash, and `UnitRegistry.__getitem__` re-runs a full
  ast.parse+compile+eval each call (`print_callers`: **all** 4.55M lookups are label `'dimensionless'`).
  Fix = memoize bare-name registry lookups (identity-stable singletons only; compound exprs fall through).
- **Config / seed:** test3 chunk (2 img + 1 video), nt12 (12×4), `OMP=4`, nomultithread, node-exclusive,
  plain mpirun (golden conditions); `param/defaults` (`mozaik_seed=1023`, `pynn_seed=5`); isolated
  `RUN_NAME=sb_qpatch NOISE_SEED=999985`, direct `run.py`, no `rm -rf` (S500 untouched).
- **Metrics (faithful sbatch, job 14844209):** wall **741s** vs neopatch-only **913s** (−19%) vs golden
  **1015s / 16:55 (−27%)**. 84 "Finished simulating" lines = 12 ranks × 7 presentations = full golden
  workload; `run.py exit: 0`.
- **Correctness gate (job 14844214, neopatch SIF + quantities patch):** **30/30** `tests/full_model`
  green — `test_models.py` 20 passed + `test_models_stepcurrentmodule.py` 10 passed (spikes + voltages).
- **Behavior-equivalence:** `patches/quantities-0.16.4/test_registry_equiv.py` byte-identical patched vs
  unpatched (dimensionality strings, magnitudes, identity-stability incl. compound `m/s`/`g/cc`, cross-
  equality, neo spiketrain roundtrip; cache-exercising repeats).
- **Result / decision:** 🟢 goal met — 27% below golden, 30/30 green. Banked (commit + tag
  `neo14-perf-qpatch-26-07-14`, `docs/ROLLBACK.md`, new-name SIF). Baked SIF
  `mozaik-opt-qpatch_2026-07-14.sif` re-certified 30/30 directly (no bind-mount, job 14847923).
- **Artifacts:** `mozaik/patches/quantities-0.16.4/` (patch+diff+README+equiv test); sbatch
  `mozaik/slurm_neo14_pytest/26-07-14_{qpatch_test3,prof_qpatch,qpatch_gate}_sbatch.sbatch`; def
  `mozaik/mozaik-opt-neo14_2026-07_qpatch.def`; profiles `getdata_rank0{,_qpatch}.prof`.
- **Caveats / honesty:** lever B is the low-risk algorithmic win; the biggest remaining lever (A = skip
  get_data on the 22/84 zero-sim blanks, ~28%) is output-changing and left for explicit sign-off. Faithful
  numbers are the node-exclusive sbatch; inline runs are ~40% inflated (relative A/B only).

## 2026-07-13 — S500 dataset creation (P1 sim → export) 🟠 PRE-REGISTERED / in progress
- **Goal:** produce a new Experanto dataset by presenting the **P4 S500 subset (500 images)** to the LSV1M V1 model
  over **3 trials** and exporting to Experanto. First use of a multi-session P4-subset input dataset for P1.
- **Commit-tuple:** mozaik `5359cfc` (`csng-mozaik-update`, dirty: base_path env + compose BASE_PATH plumbing) ·
  mozaik-models `f75f108` (`main-mozaik-update`, dirty: new `materialize_subset_screen.py`) ·
  experanto `327c3a0` (`clean-spikeinterpolator`) · SIF `mozaik-sif/mozaik-opt_2026-07-10.sif` (neo 0.14.4).
- **Config / seed:** `mozaik_seed=1023`, `pynn_seed=5` (from `experanto/param/defaults`); per (trial,chunk)
  `noise_seed = TRIAL*1000 + CHUNK` (runner convention); 3 trials × 6 chunks = 18 sim array tasks (~83–84 img/chunk).
- **Input:** P4 `subset_S500.json` (fps_seed=42, first 500 of `fps_order`; all `image`; 19 source sessions) →
  materialized to `MOZAIK/S500_3trial/input_screen/` (500 yml+npy, `(36,64) f32`) by `materialize_subset_screen.py`.
  Chunks: `MOZAIK/S500_3trial/chunks/{0..2}_{0..5}.json`.
- **Outputs (pre-registered, new paths):** sim datastores under `mozaik-models/experanto/` (gitignored);
  export → `/mnt/vast-react/projects/neural_foundation_model/MOZAIK/S500_3trial/export/`.
- **Stop conditions / success bar (pre-registered):** all 18 sim tasks exit 0:0 + datastores written; export produces
  spike+screen shards for **500 stimuli × 3 trials** with timeline alignment holding
  (`responses/meta.yml:end_time == screen/timestamps.npy[-1]`).
- **Confs:** `mozaik/cluster/experiments/{sim-S500.conf, export-S500.conf}`. Launch: `./cluster/submit.sh <conf>`.
- **Run dir:** `experiments/2026-07-13_s500-dataset/` (provenance.json to be stamped on completion).
- **Result / decision:** _pending — sim + export in progress; this block to be updated with metrics on completion._

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

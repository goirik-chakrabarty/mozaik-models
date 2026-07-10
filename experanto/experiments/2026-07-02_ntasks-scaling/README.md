# 2026-07-02 — NTASKS scaling sweep (P1 simulation)

**Question:** how does MOZAIK sim wall-time change with the number of MPI tasks (`NTASKS`),
holding the workload and per-rank threading fixed?

## Design
- **Baseline (on disk):** `sim-test3` @ NTASKS=12 → **~15.5 min** wall (`sacct` job 14602650: 00:15:26).
  Note from `.err`: per stimulus "took ~82 s, of which ~5 s was simulation time" → only ~6% of wall is
  NEST compute, so expect a **flat-ish** curve, not 1/NTASKS.
- **Swept variable:** `NTASKS ∈ {4, 8, 12, 16, 24}` (mpirun -n / SLURM ntasks).
- **Held fixed:** `CPUS_PER_TASK=4`, `OMP_NUM_THREADS=4` (so physical cores = NTASKS×4, ceiling
  NTASKS=24 = 96 cores = full medium96s node); identical workload (chunk `0_0.json`).
- **Isolation (non-destructive):** each arm reads an identical copy of `0_0.json` from a dedicated
  chunk dir `/data/MOZAIK/mozaik_chunk_scaling/{N}_0.json`, and writes a distinct output dir
  (array index = N ⇒ TRIAL=N ⇒ `SelfSustainedPushPull_trial{N}_chunk0_____noise_seed:{N}000`).
  Nothing existing (test3 trials 0/1/2) is touched.
- **Timeout:** `TIME=02:30:00` (150 min). Arms that hit the wall are recorded as **> 150 min**.

## Configs
`mozaik/cluster/experiments/ntasks-scaling/sim-scale-nt{4,8,12,16,24}.conf`

## Results (all started 2026-07-02 23:35:24, each on its own full node)
| NTASKS | cores | SLURM job | State | Elapsed | vs nt12 |
|--------|-------|-----------|-------|---------|---------|
| 4  | 16 | 14614500 | COMPLETED | 40:51 | 2.4× |
| 8  | 32 | 14614501 | COMPLETED | 21:08 | 1.25× |
| **12** | **48** | **14614503** | **COMPLETED** | **16:55** | **1.0× (optimum)** |
| 16 | 64 | 14614504 | COMPLETED | 1:16:52 | 4.5× |
| 24 | 96 | 14614505 | **TIMEOUT** | **> 150 min** (killed at 02:30 wall cap) | ≥ 8.9× |

**Finding: U-shaped curve, optimum at NTASKS=12; severe *negative* scaling beyond it.** nt16 is 4.5×
slower than nt12 and nt24 never finished (hit the 150-min cap). Adding MPI ranks past ~12 makes the sim
dramatically *slower*, not faster.

**Why (root-cause, from the nt12 baseline `.err`):** only ~9% of wall is NEST `sim.run`; ~88% is
per-presentation overhead dominated by `sheet.get_data()` (spike→Neo serialization + **MPI gather to
root**) in `mozaik/mozaik/models/__init__.py:180-189`. The gather cost grows with rank count, so more
ranks inflate the 88% faster than they shrink the 9%. Diagnostic: blank presentations log
`took 76 s, of which 0 s was simulation time` (×22) — a stimulus that runs the net ~49 ms and reads no
file still costs 76 s, all in `get_data`. Config: `reset:False`, `null_stimulus_period:0.0`.

**Consequence:** environment/apptainer/BLAS/thread tuning cannot meaningfully speed this up (Amdahl
ceiling ≈ 1.1× since NEST is ~9%). Run production at **NTASKS≈12**; real speedups require reducing
per-presentation `get_data` cost (record fewer neurons; don't retrieve on blanks — ~28% of runtime).

## Collect timings when done
```bash
sacct -j 14614500,14614501,14614503,14614504,14614505 \
  --format=JobID%18,JobName%18,NTasks,AllocCPUS,State,Elapsed,Start,End
```
`State=TIMEOUT` ⇒ record "> 150 min".

## Commit-tuple
mozaik `fb85e2e` (dirty: new sweep confs + README) · mozaik-models `4224a6b` (clean) ·
experanto `327c3a0` (clean) · container `mozaik-sif/mozaik-opt.sif`.

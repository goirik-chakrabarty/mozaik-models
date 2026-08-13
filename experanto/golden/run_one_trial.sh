#!/bin/bash
# Runs INSIDE the mozaik container (one SLURM array task = one test3 trial).
# Simulates one test3 chunk with the three-seed schema and inline multi-sheet export (run.py --export),
# writing the datastore + Experanto shard under /project/test3_ms_golden/ (== mozaik-models/experanto/,
# gitignored via *SelfSustainedPushPull*). Self-contained: no output leaves the repo tree.
#
# Env (from the sbatch): TRIAL, SIMSEED, CHUNK, CHUNK_DIR, NTASKS, OMP_NUM_THREADS.
# Optional: RESULTS_DIR (default test3_ms_golden/) — override to a fresh dir for determinism re-checks.
set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-test3_ms_golden/}"

# The `parameters` package crashes on import if HTTP_PROXY is set (references an unimported HTTPHandler).
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY no_proxy NO_PROXY || true

cd /project
echo "[run_one_trial] TRIAL=$TRIAL SIMSEED=$SIMSEED CHUNK=${CHUNK:-0} CHUNK_DIR=$CHUNK_DIR NTASKS=$NTASKS OMP=$OMP_NUM_THREADS"

# CLI override values are eval()'d by mozaik.cli.parse_workflow_args:
#   results_dir "'test3_ms_golden/'"  -> a string literal (trailing slash: root = results_dir + ddir)
#   simulation_seed "$SIMSEED"        -> an int (nonzero; NEST rejects rng_seed=0)
# model_seed=1023 / experiment_seed=0 come from param/defaults (fixed network identity + stimulus order).
# --export triggers the inline multi-sheet export (SHEET_NAMES unset -> ALL recorded sheets).
mpirun -n "$NTASKS" --bind-to none --oversubscribe \
    -x OMP_NUM_THREADS -x MKL_NUM_THREADS -x OPENBLAS_NUM_THREADS \
    -x PYTHONPATH -x TRIAL -x CHUNK -x CHUNK_DIR \
    python -u run.py nest "$NTASKS" param/defaults \
        results_dir "'${RESULTS_DIR}'" simulation_seed "$SIMSEED" \
        "trial${TRIAL}_chunk0" --export

echo "[run_one_trial] DONE trial=$TRIAL -> /project/${RESULTS_DIR}SelfSustainedPushPull_trial${TRIAL}_chunk0_____simulation_seed:${SIMSEED}/experanto/"

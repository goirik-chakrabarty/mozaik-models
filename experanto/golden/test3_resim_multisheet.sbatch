#!/bin/bash
# Fresh test3 re-sim + inline MULTI-SHEET export, self-contained in the repo.
# 3 trials (array 0-2), one test3 chunk each (2 images + 1 video). Output (datastore + Experanto shard)
# lands under mozaik-models/experanto/test3_ms_golden/ (gitignored via *SelfSustainedPushPull*).
# Produces the reference for re-blessing the P1 export golden (docs/plan/audit/golden/P1.json), now
# all-sheets (n_signals 108150).
#
#   sbatch mozaik-models/experanto/golden/test3_resim_multisheet.sbatch   # run from the mozaik/ dir
#
#SBATCH --job-name=test3-ms-golden
#SBATCH --partition=medium96s
#SBATCH --constraint=sapphirerapids
#SBATCH --nodes=1
#SBATCH --ntasks=12
#SBATCH --cpus-per-task=1
#SBATCH --mem=250G
#SBATCH --time=00:45:00
#SBATCH --array=0-2
#SBATCH --output=./slurm_test3_ms_golden/%x-%A_%a.out
#SBATCH --error=./slurm_test3_ms_golden/%x-%A_%a.err
set -euo pipefail

module load apptainer 2>/dev/null || true

WS=/mnt/vast-nhr/projects/nix00014/goirik/MOZAIK-new
SIF="$WS/mozaik-sif/mozaik-opt-qpatch_2026-07-14.sif"

# Per-trial three-seed values: fixed network (model_seed=1023, experiment_seed=0 from param/defaults);
# per-trial NEST noise via simulation_seed = (trial+1)*1000 -> {1000,2000,3000} (nonzero; matches the
# 2026-07-30 seed_refactor test3 convention).
export TRIAL="$SLURM_ARRAY_TASK_ID"
export CHUNK=0
export SIMSEED=$(( (SLURM_ARRAY_TASK_ID + 1) * 1000 ))
export NTASKS=12
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

echo "=== test3-ms-golden: trial=$TRIAL simulation_seed=$SIMSEED on $(hostname) ==="

apptainer exec \
    --cleanenv \
    --env OMPI_MCA_orte_tmpdir_base=/tmp \
    --env PYTHONPATH=/mozaik \
    --env TRIAL="$TRIAL" \
    --env CHUNK="$CHUNK" \
    --env SIMSEED="$SIMSEED" \
    --env NTASKS="$NTASKS" \
    --env CHUNK_DIR=/data/MOZAIK/mozaik_chunk_test3 \
    --env OMP_NUM_THREADS="$OMP_NUM_THREADS" \
    --env MKL_NUM_THREADS="$MKL_NUM_THREADS" \
    --env OPENBLAS_NUM_THREADS="$OPENBLAS_NUM_THREADS" \
    --bind "$WS/mozaik:/mozaik" \
    --bind "$WS/mozaik-models/experanto:/project" \
    --bind "/mnt/vast-nhr/projects/nix00014/goirik/experanto:/experanto" \
    --bind "/mnt/vast-react/projects/neural_foundation_model:/data" \
    "$SIF" \
    bash /project/golden/run_one_trial.sh

echo "=== test3-ms-golden: trial=$TRIAL COMPLETE ==="

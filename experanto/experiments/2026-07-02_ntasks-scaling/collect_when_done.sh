#!/bin/bash
# Watcher: poll the 5 NTASKS-sweep jobs until all reach a terminal state, then dump final timings.
# Launched in the background; on exit the results are in sacct_results.txt and printed to stdout.
IDS="14614500,14614501,14614503,14614504,14614505"
RUNDIR="/mnt/vast-nhr/projects/nix00014/goirik/MOZAIK-new/mozaik-models/experanto/experiments/2026-07-02_ntasks-scaling"
OUT="$RUNDIR/sacct_results.txt"
ACTIVE='PENDING|RUNNING|COMPLETING|SUSPENDED|REQUEUED|RESIZING|CONFIGURING'

for i in $(seq 1 360); do   # up to ~6 h (60 s cadence); jobs cap at 150 min wall each
  states=$(sacct -X -j "$IDS" --format=State -n -P 2>/dev/null)
  if [ -n "$states" ] && ! echo "$states" | grep -qE "$ACTIVE"; then
    echo "All jobs terminal after $i poll(s)."
    break
  fi
  sleep 60
done

{
  echo "# NTASKS sweep — final timings, collected $(date +'%Y-%m-%d %H:%M:%S')"
  sacct -X -j "$IDS" \
    --format=JobID%16,JobName%18,AllocCPUS,State,Elapsed,Start,End -P
} | tee "$OUT"

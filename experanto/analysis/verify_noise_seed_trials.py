"""Verify NOISE_SEED correctness across trials (corrected + parameterized).

Two properties, per the NOISE_SEED design (REPORT_NOISE_SEED.md):
  1. CONNECTIVITY INVARIANT — every trial shares identical network structure. Checked by hashing
     `parameters.json` **with `noise_seed` removed** (the old compare_test3_trials.py hashed the
     full JSON, which *contains* noise_seed, so it always reported "parameters differ" — a false
     alarm; see docs/plan/audit/simulation-quality-test33.md §2.B).
  2. NOISE VARIES — spike trains differ across trials. Checked by hashing per-segment spike times.

The connectivity check is pure JSON (no deps). The spike check needs `neo` to unpickle Segments,
so it runs inside the simulation container; without neo it is skipped with a clear notice.

Usage:
    python verify_noise_seed_trials.py [--base-dir DIR] [--n-trials N] [--noise-step 1000]
Exit code 0 iff every enabled check passes.
"""
import argparse
import hashlib
import json
import os
import sys


def _h(obj):
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def _strip_noise_seed(params):
    p = json.loads(json.dumps(params))
    p.pop("noise_seed", None)  # top-level; noise_seed is the only per-trial-varying key
    return p


def trial_dir(base_dir, trial, noise_step):
    return os.path.join(
        base_dir, f"SelfSustainedPushPull_trial{trial}_chunk0_____noise_seed:{trial * noise_step}"
    )


def check_connectivity(dirs):
    """PASS iff parameters.json (minus noise_seed) is identical across all trials."""
    hashes = []
    for d in dirs:
        params = json.load(open(os.path.join(d, "parameters.json")))
        hashes.append(_h(_strip_noise_seed(params))[:12])
    ok = len(set(hashes)) == 1
    print(f"[connectivity] param hashes (noise_seed removed): {hashes}")
    print(f"[connectivity] {'PASS — identical across trials' if ok else 'FAIL — network differs beyond noise_seed'}")
    return ok


def check_noise_varies(dirs):
    """PASS iff spike times differ across trials for every segment. Needs neo."""
    try:
        import pickle

        import numpy as np
    except Exception as e:  # pragma: no cover
        print(f"[noise] SKIPPED — {e}")
        return None
    seg_files = sorted(
        f for f in os.listdir(dirs[0]) if f.startswith("Segment") and f.endswith(".pickle")
    )
    if not seg_files:
        print("[noise] SKIPPED — no Segment pickles found")
        return None
    identical = different = 0
    for seg_name in seg_files:
        hashes = []
        for d in dirs:
            try:
                seg = pickle.load(open(os.path.join(d, seg_name), "rb"))  # needs neo installed
            except ModuleNotFoundError as e:
                print(f"[noise] SKIPPED — cannot unpickle Segment ({e}); run inside the container")
                return None
            sts = seg.spiketrains
            times = (
                np.concatenate([np.array(st) for st in sts if len(st) > 0])
                if sum(len(st) for st in sts) > 0
                else np.array([])
            )
            hashes.append(hashlib.md5(times.tobytes()).hexdigest())
        if len(set(hashes)) == 1:
            identical += 1
        else:
            different += 1
    ok = identical == 0
    print(f"[noise] segments: {len(seg_files)} | identical across trials: {identical} | different: {different}")
    print(f"[noise] {'PASS — every segment differs across trials' if ok else 'FAIL — some segments identical (noise_seed not varying)'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default=os.environ.get("BASE_DIR", os.path.dirname(os.path.abspath(__file__))))
    ap.add_argument("--n-trials", type=int, default=int(os.environ.get("N_TRIALS", "3")))
    ap.add_argument("--noise-step", type=int, default=int(os.environ.get("NOISE_STEP", "1000")))
    args = ap.parse_args()

    dirs = [trial_dir(args.base_dir, t, args.noise_step) for t in range(args.n_trials)]
    missing = [d for d in dirs if not os.path.isdir(d)]
    if missing:
        print("MISSING trial dirs:")
        for d in missing:
            print(f"  {d}")
        return 2
    print(f"Verifying {len(dirs)} trials under {args.base_dir}\n")

    conn = check_connectivity(dirs)
    print()
    noise = check_noise_varies(dirs)

    enabled = [c for c in (conn, noise) if c is not None]
    ok = all(enabled)
    print(f"\nVERDICT: {'PASS' if ok else 'FAIL'}"
          + ("" if noise is not None else "  (spike check skipped — no neo; connectivity only)"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

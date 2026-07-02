"""P1 reproduction verify: a fresh re-simulation vs a reference datastore (same-seed determinism).

This is the P1 *reproduction* golden (heavier periodic QC), complementary to the cheap deterministic
P1 *gate* (`docs/plan/audit/golden/capture_p1_export.py`). It proves the MOZAIK simulation is
bit-reproducible under fixed seeds: re-running the identical config (mozaik_seed, pynn_seed, per-trial
noise_seed) must reproduce the exact same spike trains.

For each trial (one fixed noise_seed) it loads every Segment*.pickle from both the fresh and the
reference datastore and compares spike trains neuron-by-neuron. Pickle *bytes* differ trivially (Neo
embeds memo order / object ids), so we compare the DATA — per-neuron spike times — not raw bytes.

Runs inside the sim container (needs `neo` to unpickle Segments). Spike-extraction method matches
`verify_noise_seed_trials.py`; that script compares across trials (noise varies), this one compares
fresh-vs-reference at the same trial/seed (reproducibility).

Usage (inside container):
    python verify_p1_reproduction.py --fresh-base DIR --ref-base DIR [--n-trials 3] [--json OUT]
Exit code 0 iff every trial is bit-identical.
"""
import argparse
import hashlib
import json
import os
import pickle

import numpy as np


def seg_files(d):
    return sorted(
        (f for f in os.listdir(d) if f.startswith("Segment") and f.endswith(".pickle")),
        key=lambda s: int(s[len("Segment"):-len(".pickle")]),
    )


def spiketrain_times(seg):
    """List of per-neuron spike-time arrays (float64), in stored order."""
    return [np.asarray(st, dtype=np.float64) for st in seg.spiketrains]


def compare_trial(fresh_dir, ref_dir):
    fresh_segs = seg_files(fresh_dir)
    ref_segs = seg_files(ref_dir)
    res = {
        "n_seg_fresh": len(fresh_segs),
        "n_seg_ref": len(ref_segs),
        "seg_set_equal": fresh_segs == ref_segs,
        "seg_identical": 0,
        "seg_differ": 0,
        "differing_segments": [],
        "total_spikes_fresh": 0,
        "total_spikes_ref": 0,
    }
    if not res["seg_set_equal"]:
        res["error"] = f"segment file sets differ: fresh={fresh_segs} ref={ref_segs}"
        return res
    for name in fresh_segs:
        f_sts = spiketrain_times(pickle.load(open(os.path.join(fresh_dir, name), "rb")))
        r_sts = spiketrain_times(pickle.load(open(os.path.join(ref_dir, name), "rb")))
        res["total_spikes_fresh"] += sum(a.size for a in f_sts)
        res["total_spikes_ref"] += sum(a.size for a in r_sts)
        same = (
            len(f_sts) == len(r_sts)
            and all(a.shape == b.shape for a, b in zip(f_sts, r_sts))
            and all(np.array_equal(a, b) for a, b in zip(f_sts, r_sts))
        )
        if same:
            res["seg_identical"] += 1
        else:
            res["seg_differ"] += 1
            if len(f_sts) != len(r_sts):
                reason = f"n_spiketrains {len(f_sts)} vs {len(r_sts)}"
            else:
                nf = sum(a.size for a in f_sts)
                nr = sum(b.size for b in r_sts)
                reason = f"spike counts {nf} vs {nr}" if nf != nr else "same counts, different times"
            res["differing_segments"].append({"segment": name, "reason": reason})
    res["all_identical"] = res["seg_differ"] == 0
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh-base", required=True, help="dir holding fresh SelfSustained... trial dirs")
    ap.add_argument("--ref-base", required=True, help="dir holding reference trial dirs (e.g. 1_TEST3_EXPT)")
    ap.add_argument("--n-trials", type=int, default=3)
    ap.add_argument("--noise-step", type=int, default=1000)
    ap.add_argument("--json", dest="json_out", default=None, help="write machine-readable result here")
    args = ap.parse_args()

    def tdir(base, t):
        return os.path.join(base, f"SelfSustainedPushPull_trial{t}_chunk0_____noise_seed:{t * args.noise_step}")

    print("P1 reproduction verify (datastore spike-train level)")
    print(f"  fresh: {args.fresh_base}")
    print(f"  ref  : {args.ref_base}\n")

    trials = {}
    overall_ok = True
    for t in range(args.n_trials):
        fd, rd = tdir(args.fresh_base, t), tdir(args.ref_base, t)
        if not os.path.isdir(fd) or not os.path.isdir(rd):
            print(f"trial{t}: MISSING (fresh={os.path.isdir(fd)}, ref={os.path.isdir(rd)})")
            overall_ok = False
            trials[f"trial{t}"] = {"missing": True}
            continue
        r = compare_trial(fd, rd)
        ok = r.get("all_identical", False)
        overall_ok &= ok
        trials[f"trial{t}"] = r
        print(f"trial{t} (noise_seed={t*args.noise_step}): "
              f"{'IDENTICAL' if ok else 'DIFFERS'} | "
              f"segments {r['seg_identical']}/{r['n_seg_fresh']} identical | "
              f"spikes fresh={r['total_spikes_fresh']} ref={r['total_spikes_ref']}")
        if r.get("error"):
            print(f"    ERROR: {r['error']}")
        for ds in r["differing_segments"][:10]:
            print(f"    DIFFER {ds['segment']}: {ds['reason']}")

    verdict = "PASS — simulation is bit-reproducible under fixed seeds" if overall_ok \
        else "FAIL — fresh re-sim diverges from reference"
    print(f"\nVERDICT: {verdict}")

    if args.json_out:
        result = {
            "pipeline": "P1",
            "what": "MOZAIK simulation reproduction — fresh re-sim vs reference datastore (spike-train level)",
            "fresh_base": args.fresh_base,
            "ref_base": args.ref_base,
            "n_trials": args.n_trials,
            "trials": trials,
            "all_identical": overall_ok,
            "verdict": verdict,
        }
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nwrote {args.json_out}")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

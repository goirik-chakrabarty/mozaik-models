#!/usr/bin/env python
"""Compare two Experanto P1 exports at the environment/model level (mozaik-update migration).

This is the Leg-1/Leg-2 comparison from docs/plan/updating-mozaik/PLAN_MOZAIK_UPDATE.md. It does
NOT assert bit-identity (the upstream update changes outputs by design). It reports:

  Tier A - structural invariants (MUST pass; mirrors docs/plan/audit/golden/P1.json):
    CSR N+1 / starts 0 / ends len(spikes) / monotonic; end_time == screen timestamps[-1];
    spikes finite and within [0, end]; n_signals == 37500.
  Tier B - statistical equivalence (drift expected; thresholds pre-registered):
    * total spike count per trial: |delta| <= SPIKE_COUNT_TOL (default 0.15)
    * per-neuron mean firing rate: median relative diff <= RATE_MEDIAN_TOL (default 0.10)
    * population PSTH correlation (per stimulus, then mean): Pearson r >= PSTH_R_MIN (default 0.90)

Works purely on the exported files (responses/spikes.npy + meta.yml, screen/timestamps.npy +
combined_meta.json) - no neo / datastore / container needed. Neuron order is assumed identical
between the two exports (fixed connectivity via mozaik_seed/pynn_seed), which per-neuron-rate
comparison relies on; PSTH does not.

Usage:
    python compare_p1_environments.py --old OLD_DIR --new NEW_DIR [--trials trial0 trial1 trial2]
                                      [--bin-ms 10] [--out report.json] [--label "Leg 1"]

OLD_DIR/NEW_DIR may be a parent dir containing trial* subdirs, or a single export dir (a dir that
directly contains responses/ and screen/).
"""
import argparse
import json
import math
import os
import sys

import numpy as np
import yaml

# --- pre-registered thresholds (PLAN_MOZAIK_UPDATE.md sec.6); change ONLY before running -----------
PSTH_R_MIN = 0.90        # population-PSTH Pearson r, per stimulus then mean
RATE_MEDIAN_TOL = 0.10   # median per-neuron mean-rate relative difference
SPIKE_COUNT_TOL = 0.15   # total spike-count relative difference per trial
N_SIGNALS_EXPECTED = 37500


def _load_export(d):
    """Load one export dir -> dict of arrays/meta. Raises on missing files."""
    meta = yaml.safe_load(open(os.path.join(d, "responses", "meta.yml")))
    spikes = np.load(os.path.join(d, "responses", "spikes.npy"))
    csr = np.asarray(meta["spike_indices"], dtype=np.int64)
    ts = np.load(os.path.join(d, "screen", "timestamps.npy"))
    combined = json.load(open(os.path.join(d, "screen", "combined_meta.json")))
    return {
        "dir": d,
        "spikes": spikes,
        "csr": csr,
        "end_time": float(meta["end_time"]),
        "n_signals": int(meta["n_signals"]),
        "timestamps": ts,
        "combined": combined,
    }


def _tier_a(e):
    """Structural invariants. Returns (all_pass, checks dict)."""
    spikes, csr, end = e["spikes"], e["csr"], e["end_time"]
    ts = e["timestamps"]
    c = {
        "csr_len_is_n_plus_1": len(csr) == e["n_signals"] + 1,
        "csr_starts_at_0": csr[0] == 0,
        "csr_ends_at_len_spikes": csr[-1] == len(spikes),
        "csr_monotonic": bool(np.all(np.diff(csr) >= 0)),
        "timeline_end_eq_last_timestamp": math.isclose(end, float(ts[-1]), rel_tol=0, abs_tol=1e-6),
        "timestamps_monotonic": bool(np.all(np.diff(ts) >= 0)),
        "spikes_finite": bool(np.all(np.isfinite(spikes))),
        "spikes_within_0_end": bool((spikes.size == 0) or (spikes.min() >= 0 and spikes.max() <= end + 1e-6)),
        "n_signals_expected": e["n_signals"] == N_SIGNALS_EXPECTED,
    }
    return all(c.values()), c


def _per_neuron_rates(e):
    counts = np.diff(e["csr"]).astype(np.float64)
    return counts / max(e["end_time"], 1e-9)


def _stimulus_windows(e):
    """List of (name, t_start, t_end) for each screen entry, from combined_meta + timestamps."""
    ts = e["timestamps"]
    entries = [e["combined"][k] for k in sorted(e["combined"].keys())]
    ffi = [int(x["first_frame_idx"]) for x in entries]
    wins = []
    for i, ent in enumerate(entries):
        t0 = float(ts[ffi[i]])
        t1 = float(ts[ffi[i + 1]]) if i + 1 < len(ffi) else float(ts[-1])
        wins.append((ent.get("modality", "image"), t0, t1))
    return wins


def _population_psth(spikes, t0, t1, bin_ms):
    if t1 <= t0:
        return np.zeros(1)
    nbins = max(1, int(round((t1 - t0) * 1000.0 / bin_ms)))
    h, _ = np.histogram(spikes, bins=nbins, range=(t0, t1))
    return h.astype(np.float64)


def _pearson(a, b):
    if a.size != b.size or a.size < 2:
        return float("nan")
    if a.std() == 0 or b.std() == 0:
        return 1.0 if np.allclose(a, b) else 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _tier_b(old, new, bin_ms):
    n_old, n_new = len(old["spikes"]), len(new["spikes"])
    spike_count_delta = abs(n_new - n_old) / max(n_old, 1)

    r_old, r_new = _per_neuron_rates(old), _per_neuron_rates(new)
    n = min(len(r_old), len(r_new))
    r_old, r_new = r_old[:n], r_new[:n]
    denom = np.where(r_old > 1e-9, r_old, np.nan)
    rel = np.abs(r_new - r_old) / denom
    rate_median_rel = float(np.nanmedian(rel))
    rate_mean_rel = float(np.nanmean(rel))

    # population PSTH per stimulus window (image/video), then mean r; also whole-trial r
    end = min(old["end_time"], new["end_time"])
    whole_r = _pearson(_population_psth(old["spikes"], 0.0, end, bin_ms),
                        _population_psth(new["spikes"], 0.0, end, bin_ms))
    per_stim = []
    for name, t0, t1 in _stimulus_windows(old):
        if name == "blank" or t1 > end:
            continue
        r = _pearson(_population_psth(old["spikes"], t0, t1, bin_ms),
                     _population_psth(new["spikes"], t0, t1, bin_ms))
        if not math.isnan(r):
            per_stim.append({"modality": name, "t0": round(t0, 3), "t1": round(t1, 3), "r": round(r, 4)})
    psth_mean_r = float(np.mean([s["r"] for s in per_stim])) if per_stim else float("nan")

    passed = (spike_count_delta <= SPIKE_COUNT_TOL
              and rate_median_rel <= RATE_MEDIAN_TOL
              and (not math.isnan(psth_mean_r)) and psth_mean_r >= PSTH_R_MIN)
    return passed, {
        "n_spikes_old": n_old, "n_spikes_new": n_new,
        "spike_count_rel_delta": round(spike_count_delta, 4),
        "per_neuron_rate_median_rel_diff": round(rate_median_rel, 4),
        "per_neuron_rate_mean_rel_diff": round(rate_mean_rel, 4),
        "psth_whole_trial_r": round(whole_r, 4),
        "psth_per_stimulus_mean_r": round(psth_mean_r, 4) if not math.isnan(psth_mean_r) else None,
        "psth_per_stimulus": per_stim,
        "thresholds": {"PSTH_R_MIN": PSTH_R_MIN, "RATE_MEDIAN_TOL": RATE_MEDIAN_TOL,
                       "SPIKE_COUNT_TOL": SPIKE_COUNT_TOL},
    }


def _resolve_trials(base, trials):
    if trials:
        return [(t, os.path.join(base, t)) for t in trials]
    # single export dir?
    if os.path.isdir(os.path.join(base, "responses")):
        return [(os.path.basename(base.rstrip("/")), base)]
    subs = sorted(d for d in os.listdir(base) if d.startswith("trial")
                  and os.path.isdir(os.path.join(base, d, "responses")))
    return [(t, os.path.join(base, t)) for t in subs]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old", required=True, help="OLD (reference) export base dir")
    ap.add_argument("--new", required=True, help="NEW export base dir")
    ap.add_argument("--trials", nargs="*", default=None, help="trial subdir names (default: auto-detect trial*)")
    ap.add_argument("--bin-ms", type=float, default=10.0, help="PSTH bin width (ms)")
    ap.add_argument("--label", default="", help="label for this comparison (e.g. 'Leg 1 env-equivalence')")
    ap.add_argument("--out", default=None, help="write JSON report here")
    args = ap.parse_args()

    old_trials = dict(_resolve_trials(args.old, args.trials))
    new_trials = dict(_resolve_trials(args.new, args.trials))
    common = [t for t in old_trials if t in new_trials]
    if not common:
        print(f"ERROR: no common trials between {args.old} and {args.new}", file=sys.stderr)
        sys.exit(2)

    report = {"label": args.label, "old": args.old, "new": args.new, "bin_ms": args.bin_ms, "trials": {}}
    overall_pass = True
    print(f"=== compare_p1_environments {('['+args.label+']') if args.label else ''} ===")
    print(f"OLD={args.old}\nNEW={args.new}\n")
    for t in common:
        eo, en = _load_export(old_trials[t]), _load_export(new_trials[t])
        a_pass, a = _tier_a(en)          # Tier A validates the NEW export's structure
        b_pass, b = _tier_b(eo, en, args.bin_ms)
        trial_pass = a_pass and b_pass
        overall_pass = overall_pass and trial_pass
        report["trials"][t] = {"tier_a_pass": a_pass, "tier_a": a,
                               "tier_b_pass": b_pass, "tier_b": b, "pass": trial_pass}
        print(f"[{t}] {'PASS' if trial_pass else 'FAIL'}  "
              f"TierA={'ok' if a_pass else 'BROKEN'}  "
              f"spikes {b['n_spikes_old']}->{b['n_spikes_new']} (Δ{b['spike_count_rel_delta']*100:.1f}%)  "
              f"rate_medΔ={b['per_neuron_rate_median_rel_diff']*100:.1f}%  "
              f"PSTH r(stim)={b['psth_per_stimulus_mean_r']}  r(whole)={b['psth_whole_trial_r']}")
        if not a_pass:
            print("    Tier-A FAILURES:", [k for k, v in a.items() if not v])

    report["overall_pass"] = overall_pass
    print(f"\n=== VERDICT: {'PASS (statistically equivalent)' if overall_pass else 'FAIL / investigate'} ===")
    print(f"thresholds: PSTH r>={PSTH_R_MIN}, rate medianΔ<={RATE_MEDIAN_TOL*100:.0f}%, "
          f"spike-countΔ<={SPIKE_COUNT_TOL*100:.0f}%")
    if args.out:
        json.dump(report, open(args.out, "w"), indent=2)
        print(f"wrote {args.out}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()

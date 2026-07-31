"""
Compute PSTHs from Mozaik DataStore for the top-20 neurons (selected by Experanto notebook).
Saves results as .npz for comparison in verify_psth_experanto.ipynb.

Usage (inside container):
    python -u compute_psth_datastore.py

Reads:
    - results/psth_test33/top20_neuron_indices.npy (from notebook cell 4)
    - SelfSustainedPushPull_trial{0-50}_chunk0_____/ (DataStore dirs)

Writes:
    - results/psth_test33_datastore/datastore_psths.npz
"""

import ast
import gc
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from mozaik.storage.datastore import PickledDataStore
from mozaik.storage.queries import param_filter_query
from parameters import ParameterSet
from tqdm import tqdm

# ── Configuration ────────────────────────────────────────────────────────
N_TRIALS = int(os.environ.get("N_TRIALS", "51"))  # override to match the Experanto notebook's trial count (avoids the 51-vs-50 PSTH discrepancy)
BIN_SIZE_MS = 10
PRE_STIM_MS = 100
POST_STIM_MS = 100
SHEET_NAME = os.environ.get("SHEET_NAME", "V1_Exc_L2/3")
ST_NAME = os.environ.get("ST_NAME", "PixelMovieExperanto")

# All paths overridable via env so this works for any export (defaults = test33).
INPUT_DIR = Path(os.environ.get("DATASTORE_DIR", "."))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "results/psth_test33_datastore"))
NEURON_INDICES_FILE = Path(
    os.environ.get("NEURON_INDICES_FILE", "results/psth_test33/top20_neuron_indices.npy")
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def resolve_datastore(trial):
    """Locate the datastore dir for a trial by globbing the stable run prefix, so this is
    agnostic to the sim's seed scheme (old ``noise_seed:<n>`` / ``lgn_stepcurre_<sha1>:<n>`` or
    new ``simulation_seed:<n>``). Falls back to the historical noise_seed name."""
    import glob as _glob

    pref = f"SelfSustainedPushPull_trial{trial}_chunk0_____"
    matches = sorted(_glob.glob(str(INPUT_DIR / (pref + "*"))))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise RuntimeError(f"Ambiguous datastore for trial{trial}: {matches}")
    return str(INPUT_DIR / f"{pref}noise_seed:{trial * 1000}")  # backward-compat fallback


def parse_stimulus(stim_str):
    """Parse stimulus annotation string to dict."""
    if isinstance(stim_str, str):
        return ast.literal_eval(stim_str)
    return stim_str


def get_stim_id(stim_params):
    """Generate a stimulus ID matching the Experanto notebook convention."""
    movie_name = stim_params.get("movie_name")
    if movie_name is None:
        return "blank"
    # Check if it's a video (movie names like '00005.npy' are images,
    # longer names or paths with 'clip' indicate videos)
    # Actually just use movie_name as-is for matching
    return movie_name


def main():
    t_start_total = time.time()

    # Load neuron indices (positional indices, same as Experanto CSR order)
    neuron_indices = np.load(NEURON_INDICES_FILE)
    n_neurons = len(neuron_indices)
    print(f"Loaded {n_neurons} neuron indices: {neuron_indices.tolist()}")

    # ── Process all trials ───────────────────────────────────────────────
    # For each trial, we collect per-neuron spike histograms for each stimulus.
    # Structure: stim_order_idx -> list of (n_neurons, n_bins) arrays across trials

    # First pass: determine stimulus order and bin counts from trial 0
    print("\n=== Trial 0: determining stimulus structure ===")
    ds0 = PickledDataStore(
        load=True,
        parameters=ParameterSet(
            {
                "root_directory": resolve_datastore(0),
                "store_stimuli": False,
            }
        ),
        replace=False,
    )
    dsv0 = param_filter_query(ds0, st_name=ST_NAME, sheet_name=SHEET_NAME)
    segs0 = dsv0.get_segments()

    # Parse and sort chronologically
    seg_info = []
    for seg in segs0:
        sp = parse_stimulus(seg.annotations["stimulus"])
        seg_info.append(
            {
                "segment": seg,
                "stim_params": sp,
                "movie_name": sp.get("movie_name"),
                "duration_ms": sp["duration"],
                "t_start": float(seg.t_start.rescale("ms").magnitude),
                "t_stop": float(seg.t_stop.rescale("ms").magnitude),
            }
        )
    seg_info.sort(key=lambda x: x["t_start"])

    # Build stimulus table (matches Experanto notebook ordering)
    stim_table = []
    for si in seg_info:
        duration_ms = si["t_stop"] - si["t_start"]
        n_bins = int(np.ceil((duration_ms + PRE_STIM_MS + POST_STIM_MS) / BIN_SIZE_MS))
        stim_table.append(
            {
                "movie_name": si["movie_name"],
                "duration_ms": duration_ms,
                "n_bins": n_bins,
            }
        )

    n_stimuli = len(stim_table)
    print(f"Found {n_stimuli} stimulus segments in trial 0")
    for i, st in enumerate(stim_table[:5]):
        print(
            f"  [{i}] {st['movie_name']}: {st['duration_ms']:.1f}ms, {st['n_bins']} bins"
        )

    # Build stim_ids matching the Experanto notebook convention
    # Load Experanto combined_meta to get image_id / condition_hash for matching
    experanto_meta_path = os.environ.get(
        "EXPERANTO_META", "/data/mozaik_data_test33/trial0/screen/combined_meta.json"
    )
    with open(experanto_meta_path) as f:
        combined_meta = json.load(f)

    # Extract non-blank entries in order
    exp_stim_ids = []
    for key in sorted(combined_meta.keys(), key=lambda x: int(x)):
        entry = combined_meta[key]
        if entry["modality"] == "blank":
            continue
        if entry["modality"] == "image":
            exp_stim_ids.append(f"img_{int(entry['image_id'])}")
        elif entry["modality"] == "video":
            exp_stim_ids.append(f"vid_{entry['condition_hash'][:8]}")

    assert (
        len(exp_stim_ids) == n_stimuli
    ), f"Mismatch: {len(exp_stim_ids)} Experanto stimuli vs {n_stimuli} DataStore segments"
    print(f"\nStimulus ID mapping (first 5):")
    for i in range(min(5, n_stimuli)):
        print(
            f"  [{i}] DataStore: {stim_table[i]['movie_name']} -> Experanto: {exp_stim_ids[i]}"
        )

    # Pre-allocate: per-stimulus, per-trial, per-neuron counts
    # all_counts[stim_idx] = (n_neurons, n_trials, n_bins)
    all_counts = {}
    bin_edges = {}
    for si, st in enumerate(stim_table):
        all_counts[si] = np.zeros((n_neurons, N_TRIALS, st["n_bins"]))
        bin_edges[si] = np.arange(st["n_bins"] + 1) * BIN_SIZE_MS - PRE_STIM_MS

    del ds0, dsv0, segs0, seg_info
    gc.collect()

    # ── Main loop: process each trial ────────────────────────────────────
    for trial in range(N_TRIALS):
        trial_t0 = time.time()
        print(f"\n=== Trial {trial} ===", flush=True)

        ds = PickledDataStore(
            load=True,
            parameters=ParameterSet(
                {
                    "root_directory": resolve_datastore(trial),
                    "store_stimuli": False,
                }
            ),
            replace=False,
        )
        dsv = param_filter_query(ds, st_name=ST_NAME, sheet_name=SHEET_NAME)
        segs = dsv.get_segments()

        # Parse and sort chronologically
        parsed = []
        for seg in segs:
            sp = parse_stimulus(seg.annotations["stimulus"])
            parsed.append((seg, sp, float(seg.t_start.rescale("ms").magnitude)))
        parsed.sort(key=lambda x: x[2])

        assert (
            len(parsed) == n_stimuli
        ), f"Trial {trial}: expected {n_stimuli} segments, got {len(parsed)}"

        for stim_idx, (seg, sp, t_start_ms) in enumerate(
            tqdm(parsed, desc=f"Trial {trial}")
        ):
            t_stop_ms = float(seg.t_stop.rescale("ms").magnitude)

            # Load spiketrains (this is the bottleneck: ~17s/segment)
            spiketrains = seg.get_spiketrains()

            for ni, neuron_pos in enumerate(neuron_indices):
                st = spiketrains[neuron_pos]
                spike_ms = st.rescale("ms").magnitude

                # Spikes relative to segment start (= stimulus onset), in ms
                rel_ms = spike_ms - t_start_ms

                # Histogram with pre/post window
                counts, _ = np.histogram(rel_ms, bins=bin_edges[stim_idx])
                all_counts[stim_idx][ni, trial, :] = counts

            # Release memory
            try:
                seg.release()
            except Exception:
                pass

        del ds, dsv, segs, parsed
        gc.collect()
        print(f"  Trial {trial} done in {time.time() - trial_t0:.0f}s", flush=True)

    # ── Compute mean and SEM, save ───────────────────────────────────────
    print("\n=== Saving results ===")
    bin_size_s = BIN_SIZE_MS / 1000.0

    save_dict = {
        "neuron_indices": neuron_indices,
        "stim_ids": np.array(exp_stim_ids),
    }

    for si in range(n_stimuli):
        sid = exp_stim_ids[si]
        mean_counts = np.mean(all_counts[si], axis=1)
        psth = mean_counts / bin_size_s  # Hz
        sem_counts = np.std(all_counts[si], axis=1, ddof=1) / np.sqrt(N_TRIALS)
        sem = sem_counts / bin_size_s

        save_dict[f"{sid}_psth"] = psth
        save_dict[f"{sid}_sem"] = sem
        save_dict[f"{sid}_bins"] = bin_edges[si]

    np.savez(OUTPUT_DIR / "datastore_psths.npz", **save_dict)

    total_time = time.time() - t_start_total
    print(f"\nDone! Total time: {total_time/3600:.1f}h ({total_time:.0f}s)")
    print(f"Saved to {OUTPUT_DIR / 'datastore_psths.npz'}")


if __name__ == "__main__":
    main()

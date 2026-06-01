"""
Compute and save PSTHs (Peri-Stimulus Time Histograms) for a random subset of neurons.
Saves both .npy arrays and combined PNG grid plots per condition.
"""

import matplotlib

matplotlib.use("Agg")
import ast
import os
import random
from collections import defaultdict
from functools import lru_cache

import matplotlib.pyplot as plt
import numpy as np
from mozaik.storage.datastore import PickledDataStore
from mozaik.storage.queries import param_filter_query
from parameters import ParameterSet
from tqdm import tqdm

# ── Configuration ──────────────────────────────────────────────────────
SEED = 42
N_NEURONS = 20  # number of random neurons to sample
BIN_SIZE_MS = 10  # PSTH bin width in milliseconds
SHEET_NAME = "V1_Exc_L2/3"
ST_NAME = "PixelMovieExperanto"
OUTPUT_DIR = "results/psth_100trials"

# Conditions to process
AA_CONDITIONS = [
    # "AA_null35",
    # "AA_null1035",
    # "AA_null9035",
    # "AA_1sec",
    # "AA_9sec",
    # "AA_1sec_200trials",
    "AA_2sec_200trials",
    # "AA_3sec_200trials",
    # "AA_5sec_200trials",
    # "AA_9sec_200trials",
]

AB_CONDITIONS = [
    # "AB_null35",
    # "AB_null1035",
    # "AB_null9035",
    # "AB_1sec",
    # "AB_9sec",
    # "AB_1sec_100trials",
    # "AB_1sec_100trials-standard",
    "AB_2sec_100trials",
    # "AB_3sec_100trials",
    # "AB_5sec_100trials",
    # "AB_9sec_100trials",
]

ALL_CONDITIONS = AA_CONDITIONS + AB_CONDITIONS

np.random.seed(SEED)
random.seed(SEED)


@lru_cache(maxsize=128)
def parse_stimulus(stimulus_str):
    """Cache parsed stimulus annotations."""
    return ast.literal_eval(stimulus_str)


def collect_neuron_ids(segments):
    """Return sorted list of all unique neuron IDs across segments."""
    ids = set()
    for seg in segments:
        for st in seg.spiketrains:
            ids.add(st.annotations.get("source_id", st.name))
    return sorted(ids)


def compute_psth(segments, neuron_ids, bin_size_ms=BIN_SIZE_MS):
    """
    Compute PSTH for the given neuron IDs across all segments (trials).

    Parameters
    ----------
    segments : list of Neo Segments
        Each segment is one trial (same stimulus).
    neuron_ids : list
        Neuron IDs to include.
    bin_size_ms : float
        Bin width in milliseconds.

    Returns
    -------
    psth_dict : dict  {neuron_id: 1-D array of mean firing rate (Hz) per bin}
    bin_edges_ms : 1-D array of bin edges in ms relative to segment start
    """
    bin_size_s = bin_size_ms / 1000.0
    neuron_set = set(neuron_ids)

    # Use first segment to determine time extent
    seg0 = segments[0]
    t_start_s = float(seg0.t_start.rescale("s").magnitude)
    t_stop_s = float(seg0.t_stop.rescale("s").magnitude)
    duration_s = t_stop_s - t_start_s
    n_bins = int(np.ceil(duration_s / bin_size_s))

    # Accumulate spike counts: {neuron_id: (n_trials, n_bins)}
    spike_counts = {uid: [] for uid in neuron_ids}

    for seg in tqdm(segments, desc="Computing PSTH", leave=False):
        seg_t_start = float(seg.t_start.rescale("s").magnitude)

        # Build a quick lookup for this segment's spiketrains
        for st in seg.spiketrains:
            uid = st.annotations.get("source_id", st.name)
            if uid not in neuron_set:
                continue
            spikes_s = (
                st.rescale("s").magnitude - seg_t_start
            )  # relative to segment start
            counts, _ = np.histogram(
                spikes_s, bins=n_bins, range=(0.0, n_bins * bin_size_s)
            )
            spike_counts[uid].append(counts)

    # Average across trials → firing rate in Hz
    psth_dict = {}
    for uid in neuron_ids:
        if spike_counts[uid]:
            mean_counts = np.mean(spike_counts[uid], axis=0)  # mean spike count per bin
            psth_dict[uid] = mean_counts / bin_size_s  # convert to Hz
        else:
            psth_dict[uid] = np.zeros(n_bins)

    bin_edges_ms = (
        np.arange(n_bins + 1) * bin_size_ms
    )  # in ms, relative to segment start
    return psth_dict, bin_edges_ms


def corrected_compute_psth(segments, neuron_ids, bin_size_ms=BIN_SIZE_MS):
    bin_size_s = bin_size_ms / 1000.0
    neuron_set = set(neuron_ids)
    n_trials = len(segments)

    # 1. Determine time extent and bin count from the first segment
    seg0 = segments[0]
    t_start_s = float(seg0.t_start.rescale("s").magnitude)
    t_stop_s = float(seg0.t_stop.rescale("s").magnitude)
    duration_s = t_stop_s - t_start_s
    n_bins = int(np.ceil(duration_s / bin_size_s))

    # 2. PRE-ALLOCATE: (Number of Neurons, Number of Trials, Number of Bins)
    # This ensures that if a neuron doesn't fire in a trial, it stays 0.
    all_counts = np.zeros((len(neuron_ids), n_trials, n_bins))

    # Create a mapping for quick index lookup
    id_to_idx = {uid: i for i, uid in enumerate(neuron_ids)}

    # 3. Fill the array
    for trial_idx, seg in enumerate(tqdm(segments, desc="Computing PSTH", leave=False)):
        seg_t_start = float(seg.t_start.rescale("s").magnitude)

        for st in seg.spiketrains:
            uid = st.annotations.get("source_id", st.name)
            if uid in neuron_set:
                neuron_idx = id_to_idx[uid]
                spikes_s = st.rescale("s").magnitude - seg_t_start

                # Bin the spikes for this specific neuron in this specific trial
                counts, _ = np.histogram(
                    spikes_s, bins=n_bins, range=(0.0, n_bins * bin_size_s)
                )
                all_counts[neuron_idx, trial_idx, :] = counts

    # 4. Average across trials (axis 1) and normalize to Hz
    # Resulting shape: (len(neuron_ids), n_bins)
    psth_matrix = np.mean(all_counts, axis=1) / bin_size_s
    sem_matrix = (np.std(all_counts, axis=1, ddof=1) / np.sqrt(n_trials)) / bin_size_s

    # Convert back to a dictionary to match your original return format
    psth_dict = {uid: psth_matrix[i, :] for i, uid in enumerate(neuron_ids)}
    sem_dict = {uid: sem_matrix[i, :] for i, uid in enumerate(neuron_ids)}

    bin_edges_ms = np.arange(n_bins + 1) * bin_size_ms
    return psth_dict, sem_dict, bin_edges_ms


def compute_population_psth(segments, neuron_ids, bin_size_ms=BIN_SIZE_MS):
    """
    Compute Population PSTH averaged across all specified neurons and trials.

    Returns
    -------
    population_psth : 1-D array (n_bins,)
        Mean firing rate (Hz) across the population.
    population_sem : 1-D array (n_bins,)
        Standard error of the mean across neurons.
    bin_edges_ms : 1-D array (n_bins+1,)
        Bin edges in milliseconds.
    """
    bin_size_s = bin_size_ms / 1000.0
    neuron_set = set(neuron_ids)
    n_trials = len(segments)

    # 1. Determine time extent and bin count from the first segment
    seg0 = segments[0]
    t_start_s = float(seg0.t_start.rescale("s").magnitude)
    t_stop_s = float(seg0.t_stop.rescale("s").magnitude)
    duration_s = t_stop_s - t_start_s
    n_bins = int(np.ceil(duration_s / bin_size_s))

    # 2. PRE-ALLOCATE: (Number of Neurons, Number of Trials, Number of Bins)
    all_counts = np.zeros((len(neuron_ids), n_trials, n_bins))

    # Create a mapping for quick index lookup
    id_to_idx = {uid: i for i, uid in enumerate(neuron_ids)}

    # 3. Fill the array
    for trial_idx, seg in enumerate(
        tqdm(segments, desc="Computing Pop. PSTH", leave=False)
    ):
        seg_t_start = float(seg.t_start.rescale("s").magnitude)

        for st in seg.spiketrains:
            uid = st.annotations.get("source_id", st.name)
            if uid in neuron_set:
                neuron_idx = id_to_idx[uid]
                spikes_s = st.rescale("s").magnitude - seg_t_start
                counts, _ = np.histogram(
                    spikes_s, bins=n_bins, range=(0.0, n_bins * bin_size_s)
                )
                all_counts[neuron_idx, trial_idx, :] = counts

    # 4. Average across trials first directly
    mean_across_trials = (
        np.mean(all_counts, axis=1) / bin_size_s
    )  # Shape: (N_neurons, N_bins)

    # 5. Then average across neurons to get population response
    population_psth = np.mean(mean_across_trials, axis=0)
    population_sem = np.std(mean_across_trials, axis=0, ddof=1) / np.sqrt(
        len(neuron_ids)
    )

    bin_edges_ms = np.arange(n_bins + 1) * bin_size_ms
    return population_psth, population_sem, bin_edges_ms


def save_psth_npy(
    psth_dict, sem_dict, bin_edges_ms, neuron_ids, condition_name, output_dir
):
    """
    Save PSTH data as .npy files.

    Saves:
      - <condition>_psth.npy     : (N_neurons, N_bins) array of firing rates (Hz)
      - <condition>_sem.npy      : (N_neurons, N_bins) array of standard error
      - <condition>_bins_ms.npy  : (N_bins+1,) array of bin edges in ms
      - <condition>_neuron_ids.npy : (N_neurons,) array of neuron IDs
    """
    rates = np.array([psth_dict[uid] for uid in neuron_ids])
    sems = np.array([sem_dict[uid] for uid in neuron_ids])
    ids = np.array(neuron_ids)

    np.save(os.path.join(output_dir, f"{condition_name}_psth.npy"), rates)
    np.save(os.path.join(output_dir, f"{condition_name}_sem.npy"), sems)
    np.save(os.path.join(output_dir, f"{condition_name}_bins_ms.npy"), bin_edges_ms)
    np.save(os.path.join(output_dir, f"{condition_name}_neuron_ids.npy"), ids)
    print(f"  Saved .npy files for {condition_name}  shape={rates.shape}")


def plot_psth_grid(
    psth_dict, bin_edges_ms, neuron_ids, condition_name, output_dir, n_cols=10
):
    """
    Plot a grid of PSTHs (one subplot per neuron) and save as PNG.
    """
    n_neurons = len(neuron_ids)
    n_rows = int(np.ceil(n_neurons / n_cols))
    bin_centres_ms = (bin_edges_ms[:-1] + bin_edges_ms[1:]) / 2.0

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(2.0 * n_cols, 1.8 * n_rows), sharex=True, sharey=False
    )
    axes = np.atleast_2d(axes)

    for idx, uid in enumerate(neuron_ids):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]
        ax.bar(
            bin_centres_ms,
            psth_dict[uid],
            width=bin_edges_ms[1] - bin_edges_ms[0],
            color="steelblue",
            edgecolor="none",
            alpha=0.8,
        )
        ax.set_title(f"N{uid}", fontsize=6, pad=2)
        ax.tick_params(labelsize=5)

    # Hide unused subplots
    for idx in range(n_neurons, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row, col].set_visible(False)

    fig.suptitle(
        f"PSTH — {condition_name}  (bin={bin_edges_ms[1]:.0f} ms)", fontsize=12
    )
    fig.supxlabel("Time (ms)", fontsize=9)
    fig.supylabel("Firing rate (Hz)", fontsize=9)
    fig.tight_layout(rect=[0.02, 0.02, 1, 0.96])

    save_path = os.path.join(output_dir, f"{condition_name}_psth_grid.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"  Saved plot: {save_path}")


# ── Main ───────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 1. Load all datasets ──────────────────────────────────────────
    print("Loading datasets...")
    datasets = {}
    for cond in ALL_CONDITIONS:
        datasets[cond] = PickledDataStore(
            load=True,
            parameters=ParameterSet(
                {
                    "root_directory": f"SelfSustainedPushPull_test:{cond}_____",
                    "store_stimuli": False,
                }
            ),
            replace=False,
        )

    # ── 2. Parse & sort segments per condition ────────────────────────
    print("Parsing segments...")
    segment_cache = {}
    for cond, ds in datasets.items():
        dsv = param_filter_query(ds, st_name=ST_NAME, sheet_name=SHEET_NAME)
        segs = dsv.get_segments()
        parsed = [(seg, parse_stimulus(seg.annotations["stimulus"])) for seg in segs]
        parsed.sort(key=lambda x: x[1]["trial"])
        segment_cache[cond] = parsed

    # ── 3. Pick N random neurons (consistent across conditions) ───────
    # Use the first AA condition to discover all neuron IDs, then sample
    first_cond = AA_CONDITIONS[0]
    # all_segments = [seg for seg, _ in segment_cache[first_cond][0:2]]
    # all_ids = collect_neuron_ids(all_segments)
    # print(f"Total neurons found: {len(all_ids)}")

    # sampled_ids = sorted(random.sample(all_ids, min(N_NEURONS, len(all_ids))))
    sampled_ids = [
        85971,
        63880,
        72079,
        68291,
        64346,
        75298,
        67768,
        62474,
        95713,
        82913,
        97242,
        91886,
        86240,
        71573,
        80214,
        84893,
        91687,
        63649,
        83677,
        98398,
    ]
    print(f"Sampled {len(sampled_ids)} neurons for PSTH")
    print("Sampled neuron IDs:", sampled_ids)

    # Save the sampled neuron IDs once
    np.save(os.path.join(OUTPUT_DIR, "sampled_neuron_ids.npy"), np.array(sampled_ids))

    # Identify the A movie name from the first AA condition (needed for AB filtering)
    movie_A_name = segment_cache[first_cond][0][1]["movie_name"]
    print(f"Movie A identified as: {movie_A_name}")

    # ── 4. Compute & save PSTHs for AA conditions ─────────────────────
    for cond in AA_CONDITIONS:
        print(f"\nAA Condition: {cond}")
        parsed = segment_cache[cond]

        # Even segments (stimulus A presentation)
        even_segs = [seg for seg, _ in parsed[0::2]]
        print(f"  Even segments (A): {len(even_segs)} trials")
        psth_even, sem_even, bins = corrected_compute_psth(
            even_segs, sampled_ids, bin_size_ms=BIN_SIZE_MS
        )
        save_psth_npy(
            psth_even, sem_even, bins, sampled_ids, f"{cond}_even", OUTPUT_DIR
        )
        plot_psth_grid(psth_even, bins, sampled_ids, f"{cond}_even", OUTPUT_DIR)

        # Odd segments (stimulus A' / repeat presentation)
        odd_segs = [seg for seg, _ in parsed[1::2]]
        print(f"  Odd segments (A'): {len(odd_segs)} trials")
        psth_odd, sem_odd, bins = corrected_compute_psth(
            odd_segs, sampled_ids, bin_size_ms=BIN_SIZE_MS
        )
        save_psth_npy(psth_odd, sem_odd, bins, sampled_ids, f"{cond}_odd", OUTPUT_DIR)
        plot_psth_grid(psth_odd, bins, sampled_ids, f"{cond}_odd", OUTPUT_DIR)

    # ── 5. Compute & save PSTHs for AB conditions ─────────────────────
    #    AB datasets have interleaved A and B movies.
    #    Filter by movie_name to separate A-movie and B-movie segments.
    for cond in AB_CONDITIONS:
        print(f"\nAB Condition: {cond}")
        parsed = segment_cache[cond]

        # Separate segments by movie identity
        A_from_AB = [seg for seg, stim in parsed if stim["movie_name"] == movie_A_name]
        B_from_AB = [seg for seg, stim in parsed if stim["movie_name"] != movie_A_name]

        print(f"  A-movie segments: {len(A_from_AB)} trials")
        if A_from_AB:
            psth_a, sem_a, bins = corrected_compute_psth(
                A_from_AB, sampled_ids, bin_size_ms=BIN_SIZE_MS
            )
            save_psth_npy(psth_a, sem_a, bins, sampled_ids, f"{cond}_A", OUTPUT_DIR)
            plot_psth_grid(psth_a, bins, sampled_ids, f"{cond}_A", OUTPUT_DIR)

        print(f"  B-movie segments: {len(B_from_AB)} trials")
        if B_from_AB:
            psth_b, sem_b, bins = corrected_compute_psth(
                B_from_AB, sampled_ids, bin_size_ms=BIN_SIZE_MS
            )
            save_psth_npy(psth_b, sem_b, bins, sampled_ids, f"{cond}_B", OUTPUT_DIR)
            plot_psth_grid(psth_b, bins, sampled_ids, f"{cond}_B", OUTPUT_DIR)

    print("\nDone! All PSTHs saved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()

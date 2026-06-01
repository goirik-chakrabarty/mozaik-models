"""
Plot 4 PSTH conditions (AA_even, AA_odd, A_from_AB, B_from_AB) overlaid
on the same subplot for each neuron, for matching AA/AB condition pairs.

Assumes compute_psth.py has already been run and .npy files exist in PSTH_DIR.
"""

import matplotlib

matplotlib.use("Agg")
import os

import matplotlib.pyplot as plt
import numpy as np

# ── Configuration ──────────────────────────────────────────────────────
PSTH_DIR = (
    "results/psth_100trials"  # where the .npy files from compute_psth.py are stored
)
OUTPUT_DIR = "results/psth_100trials/comparison"
N_COLS = 5  # columns in the neuron grid

# Matching AA ↔ AB condition pairs (same timing parameter)
CONDITION_PAIRS = [
    ("AA_1sec_200trials", "AB_1sec_100trials"),
    ("AA_1sec_200trials", "AB_2sec_100trials"),
    ("AA_1sec_200trials", "AB_3sec_100trials"),
    ("AA_1sec_200trials", "AB_5sec_100trials"),
    ("AA_1sec_200trials", "AB_9sec_100trials"),
    ("AA_2sec_200trials", "AB_1sec_100trials"),
    ("AA_2sec_200trials", "AB_2sec_100trials"),
    ("AA_2sec_200trials", "AB_3sec_100trials"),
    ("AA_2sec_200trials", "AB_5sec_100trials"),
    ("AA_2sec_200trials", "AB_9sec_100trials"),
    ("AA_3sec_200trials", "AB_1sec_100trials"),
    ("AA_3sec_200trials", "AB_2sec_100trials"),
    ("AA_3sec_200trials", "AB_3sec_100trials"),
    ("AA_3sec_200trials", "AB_5sec_100trials"),
    ("AA_3sec_200trials", "AB_9sec_100trials"),
    ("AA_5sec_200trials", "AB_1sec_100trials"),
    ("AA_5sec_200trials", "AB_2sec_100trials"),
    ("AA_5sec_200trials", "AB_3sec_100trials"),
    ("AA_5sec_200trials", "AB_5sec_100trials"),
    ("AA_5sec_200trials", "AB_9sec_100trials"),
    ("AA_9sec_200trials", "AB_1sec_100trials"),
    ("AA_9sec_200trials", "AB_2sec_100trials"),
    ("AA_9sec_200trials", "AB_3sec_100trials"),
    ("AA_9sec_200trials", "AB_5sec_100trials"),
    ("AA_9sec_200trials", "AB_9sec_100trials"),
    # ("AA_1sec_200trials",     "AB_1sec_100trials"),
    # ("AA_2sec_200trials",     "AB_2sec_100trials"),
    # ("AA_3sec_200trials",     "AB_3sec_100trials"),
    # ("AA_5sec_200trials",     "AB_5sec_100trials"),
    # ("AA_9sec_200trials",     "AB_9sec_100trials"),
]

# Visual settings for each trace
TRACE_STYLES = {
    "AA even": {"color": "steelblue", "alpha": 0.8, "linestyle": "-"},
    "AA odd": {"color": "green", "alpha": 0.8, "linestyle": "-"},
    "AB → A": {"color": "firebrick", "alpha": 0.8, "linestyle": "-"},
    "AB → B": {"color": "black", "alpha": 0.8, "linestyle": "-"},
}


def load_psth(prefix):
    """Load PSTH array, optional SEM, and bin edges for a given file prefix."""
    psth_path = os.path.join(PSTH_DIR, f"{prefix}_psth.npy")
    sem_path = os.path.join(PSTH_DIR, f"{prefix}_sem.npy")
    bins_path = os.path.join(PSTH_DIR, f"{prefix}_bins_ms.npy")

    psth = np.load(psth_path) if os.path.exists(psth_path) else None
    bins = np.load(bins_path) if os.path.exists(bins_path) else None
    sem = np.load(sem_path) if os.path.exists(sem_path) else None
    return psth, sem, bins


def _plot_psth_traces(ax, bin_centres, traces, linewidth=1.0):
    """Helper to plot an overlaid set of PSTH traces."""
    for label, psth_arr, sem_arr in traces:
        style = TRACE_STYLES[label]
        ax.plot(
            bin_centres,
            psth_arr,
            label=label,
            color=style["color"],
            alpha=style["alpha"],
            linestyle=style["linestyle"],
            linewidth=linewidth,
        )

        if sem_arr is not None:
            ax.fill_between(
                bin_centres,
                psth_arr - sem_arr,
                psth_arr + sem_arr,
                color=style["color"],
                alpha=0.2,
                edgecolor="none",
            )


def plot_comparison(aa_name, ab_name, neuron_ids, output_dir, n_cols=N_COLS):
    """
    For one AA/AB pair, overlay 4 PSTHs per neuron on a grid.

    Parameters
    ----------
    aa_name : str   e.g. "midAA_null35"
    ab_name : str   e.g. "midAB_null35"
    neuron_ids : 1-D array of neuron IDs (ordering matches row axis of .npy)
    output_dir : str
    n_cols : int
    """
    os.makedirs(output_dir, exist_ok=True)
    # Load all 4 PSTHs
    psth_aa_even, sem_aa_even, bins = load_psth(f"{aa_name}_even")
    psth_aa_odd, sem_aa_odd, _ = load_psth(f"{aa_name}_odd")
    psth_ab_a, sem_ab_a, _ = load_psth(f"{ab_name}_A")
    psth_ab_b, sem_ab_b, _ = load_psth(f"{ab_name}_B")

    bin_centres = (bins[:-1] + bins[1:]) / 2.0
    n_neurons = len(neuron_ids)
    n_rows = int(np.ceil(n_neurons / n_cols))

    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(3.2 * n_cols, 2.4 * n_rows), sharex=True, sharey=False
    )
    axes = np.atleast_2d(axes)

    traces = [
        ("AA even", psth_aa_even, sem_aa_even),
        # ("AA odd",  psth_aa_odd, sem_aa_odd),
        ("AB → A", psth_ab_a, sem_ab_a),
        # ("AB → B",  psth_ab_b, sem_ab_b),
    ]

    corr_list = []
    for idx in range(n_neurons):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]

        # Calculate correlation cleanly properly indexing for the 1D arrays
        corr = np.corrcoef(traces[0][1][idx], traces[1][1][idx])[0, 1]
        corr_list.append(corr)

        # Calculate standard error of the correlation
        n_bins = len(bin_centres)
        corr_se = np.sqrt((1 - corr**2) / (n_bins - 2)) if n_bins > 2 else 0

        # Build list of 1D traces for just this neuron
        neuron_traces = []
        for label, psth_arr, sem_arr in traces:
            if psth_arr is not None:
                neuron_traces.append(
                    (
                        label,
                        psth_arr[idx],
                        sem_arr[idx] if sem_arr is not None else None,
                    )
                )

        _plot_psth_traces(ax, bin_centres, neuron_traces)

        ax.set_title(
            f"N{neuron_ids[idx]} (r={corr:.4f})", fontsize=7, pad=2
        )  #  ± {corr_se:.4f}
        ax.tick_params(labelsize=5)

    # Hide unused subplots
    for idx in range(n_neurons, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row, col].set_visible(False)

    # Shared legend (from first subplot)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", fontsize=8, framealpha=0.9)

    pair_label = f"{aa_name} / {ab_name}"
    fig.suptitle(
        f"PSTH Comparison — {pair_label}  (bin={bins[1]:.0f} ms) - Mean: {np.mean(corr_list):.4f} +/- {np.std(corr_list):.4f}",
        fontsize=12,
    )
    fig.supxlabel("Time (ms)", fontsize=9)
    fig.supylabel("Firing rate (Hz)", fontsize=9)
    fig.tight_layout(rect=[0.02, 0.02, 0.95, 0.95])

    save_path = os.path.join(output_dir, f"psth_comparison_{aa_name}_{ab_name}.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {save_path}")
    return np.mean(corr_list), np.std(corr_list)


def plot_population_comparison(aa_name, ab_name, neuron_ids, output_dir):
    """
    Plot the population-averaged PSTH comparison across all sampled neurons for the pairs.
    """
    os.makedirs(output_dir, exist_ok=True)
    psth_aa_even, _, bins = load_psth(f"{aa_name}_even")
    psth_aa_odd, _, _ = load_psth(f"{aa_name}_odd")
    psth_ab_a, _, _ = load_psth(f"{ab_name}_A")
    psth_ab_b, _, _ = load_psth(f"{ab_name}_B")

    n_neurons = len(neuron_ids)
    bin_centres = (bins[:-1] + bins[1:]) / 2.0

    # Calculate population means and SEMs (across neurons)
    def get_pop_stats(psth_arr):
        if psth_arr is None:
            return None, None
        pop_mean = np.mean(psth_arr, axis=0)
        pop_sem = np.std(psth_arr, axis=0, ddof=1) / np.sqrt(n_neurons)
        return pop_mean, pop_sem

    traces = [
        ("AA even", *get_pop_stats(psth_aa_even)),
        # ("AA odd",  *get_pop_stats(psth_aa_odd)),
        ("AB → A", *get_pop_stats(psth_ab_a)),
        # ("AB → B",  *get_pop_stats(psth_ab_b)),
    ]

    # Filter out None arrays if any are missing
    valid_traces = [(lbl, m, s) for lbl, m, s in traces if m is not None]

    fig, ax = plt.subplots(figsize=(8, 4))

    corr_str = ""
    if len(valid_traces) >= 2:
        corr = np.corrcoef(valid_traces[0][1], valid_traces[1][1])[0, 1]

        if psth_aa_odd is not None and psth_ab_a is not None:
            n_bootstraps = 1000
            boot_corrs = []
            for _ in range(n_bootstraps):
                # Resample neurons with replacement
                b_idx = np.random.choice(n_neurons, size=n_neurons, replace=True)
                mean_A = np.mean(psth_aa_odd[b_idx], axis=0)
                mean_B = np.mean(psth_ab_a[b_idx], axis=0)
                boot_corrs.append(np.corrcoef(mean_A, mean_B)[0, 1])

            corr_err = np.std(boot_corrs)
            corr_str = f"  (r={corr:.4f} ± {corr_err:.4f})"
        else:
            corr_str = f"  (r={corr:.4f})"

    _plot_psth_traces(ax, bin_centres, valid_traces, linewidth=1.5)

    ax.set_title(
        f"Population PSTH Comparison: {aa_name} / {ab_name}{corr_str}", fontsize=12
    )
    ax.set_xlabel("Time (ms)", fontsize=10)
    ax.set_ylabel("Mean Firing Rate (Hz)", fontsize=10)
    ax.legend(loc="upper right", fontsize=10)
    fig.tight_layout()

    save_path = os.path.join(
        output_dir, f"population_psth_comparison_{aa_name}_{ab_name}.png"
    )
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {save_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load the shared neuron IDs (saved by compute_psth.py)
    neuron_ids = np.load(os.path.join(PSTH_DIR, "sampled_neuron_ids.npy"))
    print(f"Loaded {len(neuron_ids)} neuron IDs")

    mean_list = []
    std_list = []
    for aa_name, ab_name in CONDITION_PAIRS:
        print(f"\nPlotting: {aa_name}  vs  {ab_name}")
        mean, std = plot_comparison(
            aa_name, ab_name, neuron_ids, OUTPUT_DIR + "/AA0_vs_ABA"
        )
        mean_list.append(mean)
        std_list.append(std)
        # plot_population_comparison(aa_name, ab_name, neuron_ids, OUTPUT_DIR + "/pop-AA0_vs_AA1")

    # Plot a scatter of mean correlations as y-axis seconds as x-axis and stadard deviations as error bars
    plt.figure(figsize=(6, 4))
    x_vals = [
        float(aa.split("_")[1][:-3]) for aa, _ in CONDITION_PAIRS
    ]  # extract timing from AA name
    plt.errorbar(
        x_vals,
        mean_list,
        yerr=std_list,
        fmt="o",
        color="steelblue",
        ecolor="lightgray",
        capsize=5,
    )
    plt.xlabel("Blank (s)", fontsize=10)
    plt.ylabel("Mean Correlation (r)", fontsize=10)
    plt.title("Mean PSTH Correlation vs Blank - AA0_vs_ABA", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    summary_path = os.path.join(
        OUTPUT_DIR, "AA0_vs_ABA", "correlation_summary_AA0_vs_ABA_test.png"
    )
    plt.savefig(summary_path, dpi=150)
    plt.close()
    print(f"Saved summary plot: {summary_path}")


if __name__ == "__main__":
    main()

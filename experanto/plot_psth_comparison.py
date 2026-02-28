"""
Plot 4 PSTH conditions (AA_even, AA_odd, A_from_AB, B_from_AB) overlaid
on the same subplot for each neuron, for matching AA/AB condition pairs.

Assumes compute_psth.py has already been run and .npy files exist in PSTH_DIR.
"""
import matplotlib
matplotlib.use('Agg')
import numpy as np
import matplotlib.pyplot as plt
import os

# ── Configuration ──────────────────────────────────────────────────────
PSTH_DIR = "results/psth_AB"
OUTPUT_DIR = "results/psth_AB/comparison"
N_COLS = 5  # columns in the neuron grid

# Matching AA ↔ AB condition pairs (same timing parameter)
CONDITION_PAIRS = [
    ("midAA_null35",   "midAB_null35"),
    ("midAA_null1035", "midAB_null1035"),
    ("midAA_null9035", "midAB_null9035"),
    ("midAA_1sec",     "midAB_1sec"),
    ("midAA_9sec",     "midAB_9sec"),
]

# Visual settings for each trace
TRACE_STYLES = {
    "AA even":   {"color": "steelblue",  "alpha": 0.8, "linestyle": "-"},
    "AA odd":    {"color": "cornflowerblue", "alpha": 0.7, "linestyle": "--"},
    "AB → A":    {"color": "firebrick",  "alpha": 0.8, "linestyle": "-"},
    "AB → B":    {"color": "salmon",     "alpha": 0.7, "linestyle": "--"},
}


def load_psth(prefix):
    """Load PSTH array and bin edges for a given file prefix."""
    psth = np.load(os.path.join(PSTH_DIR, f"{prefix}_psth.npy"))       # (N_neurons, N_bins)
    bins = np.load(os.path.join(PSTH_DIR, f"{prefix}_bins_ms.npy"))    # (N_bins+1,)
    return psth, bins


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
    # Load all 4 PSTHs
    psth_aa_even, bins = load_psth(f"{aa_name}_even")
    psth_aa_odd,  _    = load_psth(f"{aa_name}_odd")
    psth_ab_a,    _    = load_psth(f"{ab_name}_A")
    psth_ab_b,    _    = load_psth(f"{ab_name}_B")

    bin_centres = (bins[:-1] + bins[1:]) / 2.0
    n_neurons = len(neuron_ids)
    n_rows = int(np.ceil(n_neurons / n_cols))

    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.2 * n_cols, 2.4 * n_rows),
                             sharex=True, sharey=False)
    axes = np.atleast_2d(axes)

    traces = [
        ("AA even", psth_aa_even),
        ("AA odd",  psth_aa_odd),
        # ("AB → A",  psth_ab_a),
        # ("AB → B",  psth_ab_b),
    ]
    corr_list = []
    for idx in range(n_neurons):
        row, col = divmod(idx, n_cols)
        ax = axes[row, col]
        corr = np.corrcoef(traces[0][1], traces[1][1])[idx, 20+idx]
        corr_list.append(corr)
        for label, psth_arr in traces:
            style = TRACE_STYLES[label]
            ax.plot(bin_centres, psth_arr[idx],
                    label=label,
                    color=style["color"],
                    alpha=style["alpha"],
                    linestyle=style["linestyle"],
                    linewidth=1.0)

        ax.set_title(f"N{neuron_ids[idx]} (r={corr:.4f})", fontsize=7, pad=2)
        ax.tick_params(labelsize=5)

    # Hide unused subplots
    for idx in range(n_neurons, n_rows * n_cols):
        row, col = divmod(idx, n_cols)
        axes[row, col].set_visible(False)

    # Shared legend (from first subplot)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", fontsize=8, framealpha=0.9)

    pair_label = f"{aa_name} / {ab_name}"
    fig.suptitle(f"PSTH Comparison — {pair_label}  (bin={bins[1]:.0f} ms) - Mean: {np.mean(corr_list):.4f}", fontsize=12)
    fig.supxlabel("Time (ms)", fontsize=9)
    fig.supylabel("Firing rate (Hz)", fontsize=9)
    fig.tight_layout(rect=[0.02, 0.02, 0.95, 0.95])

    save_path = os.path.join(output_dir, f"psth_comparison_{aa_name}_{ab_name}.png")
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {save_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load the shared neuron IDs (saved by compute_psth.py)
    neuron_ids = np.load(os.path.join(PSTH_DIR, "sampled_neuron_ids.npy"))
    print(f"Loaded {len(neuron_ids)} neuron IDs")

    for aa_name, ab_name in CONDITION_PAIRS:
        print(f"\nPlotting: {aa_name}  vs  {ab_name}")
        plot_comparison(aa_name, ab_name, neuron_ids, OUTPUT_DIR)

    print(f"\nDone! Comparison plots saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

import matplotlib
matplotlib.use('Agg')
import numpy as np
import random
import matplotlib.pyplot as plt
import json
import ast
from tqdm import tqdm
from mozaik.storage.datastore import PickledDataStore
from parameters import ParameterSet
from mozaik.storage.queries import param_filter_query
from collections import defaultdict
from functools import lru_cache

np.random.seed(42)
random.seed(42)

# Cache for parsed stimulus metadata
@lru_cache(maxsize=128)
def parse_stimulus(stimulus_str):
    """Cache parsed stimulus annotations."""
    return ast.literal_eval(stimulus_str)

# ==========================================
# 3. Calculate Mean Firing Rates (Optimized & Windowed)
# ==========================================
def calculate_rates(segments, window_start_sec=0.0, window_duration_sec=None):
    """
    Returns a dictionary {neuron_id: mean_firing_rate_hz} averaged across trials.
    Optimized with defaultdict and vectorized operations.
    If window_duration_sec is provided, only spikes within [start, start+duration] are counted.
    """
    unit_rates = defaultdict(list)
    
    for seg in tqdm(segments):
        seg_t_start = seg.t_start.rescale('s').magnitude
        seg_t_stop = seg.t_stop.rescale('s').magnitude
        
        # Determine the actual time window for counting spikes
        t_start = seg_t_start + window_start_sec
        if window_duration_sec is not None:
            t_stop = min(t_start + window_duration_sec, seg_t_stop)
        else:
            t_stop = seg_t_stop
            
        actual_duration = t_stop - t_start
        if actual_duration <= 0:
            continue
            
        for st in seg.spiketrains:
            uid = st.annotations.get('source_id', st.name)
            # Count spikes within the specific time window
            spikes = st.rescale('s').magnitude
            spike_count = np.sum((spikes >= t_start) & (spikes < t_stop))
            rate = spike_count / actual_duration
            unit_rates[uid].append(rate)
    
    # Convert to dict and compute means
    return {k: np.mean(v) for k, v in unit_rates.items()}

def plot_corr(series1, series2, save_path):
    corr = np.corrcoef(series1, series2)[0, 1]
    print(f"Correlation between conditions: {corr:.4f}")
    
    # Plot
    plt.figure(figsize=(10, 5))
    
    # Scatter
    plt.subplot(1, 2, 1)
    plt.scatter(series1, series2, alpha=0.6, edgecolors='none')
    plt.plot([0, max(series1)], [0, max(series1)], 'k--', label="Identity")
    # plt.xlabel("Rate in AA (Single Input)")
    # plt.ylabel("Rate in AA1 (First of Pair)")
    plt.title(f"Response Comparison (Corr: {corr:.4f})")
    plt.legend()
    
    # Histogram of differences
    plt.subplot(1, 2, 2)
    diffs = np.array(series2) - np.array(series1)
    plt.hist(diffs, bins=20, color='gray', edgecolor='black')
    # plt.xlabel("Rate Difference (AA1 - AA)")
    plt.ylabel("Count")
    plt.title("Difference Distribution")
    
    plt.tight_layout()
    plt.savefig(save_path)
    # plt.show()
    plt.close('all')
    return corr


AA_list = ["AA_null35", "AA_null1035", "AA_null3035", "AA_null9035", "AA_1sec", "AA_3sec", "AA_9sec"]
AA1_list = ["AA_null35", "AA_null1035", "AA_null3035", "AA_null9035", "AA_1sec", "AA_3sec", "AA_9sec"]

# AA_list = ["test12"]
# AA1_list = ["test12"]

data = {y:{x:0 for x in AA_list} for y in AA1_list}

# Pre-load all datasets
datasets_mid = {}
for aa_name in AA_list:
    datasets_mid[aa_name] = PickledDataStore(
        load=True,
        parameters=ParameterSet({"root_directory": f"SelfSustainedPushPull_test:{aa_name}_____", "store_stimuli": False}),
        replace=False
    )

# Pre-parse and cache stimulus information
segment_cache_mid = {}

for dataset_name, ds in datasets_mid.items():
    dsv = param_filter_query(ds, st_name="PixelMovieExperanto", sheet_name="V1_Exc_L2/3")
    segs = dsv.get_segments()
    
    # Pre-parse stimulus info
    parsed_stimuli = []
    for seg in segs:
        stim_dict = parse_stimulus(seg.annotations['stimulus'])
        parsed_stimuli.append((seg, stim_dict))
    
    # Sort once
    parsed_stimuli.sort(key=lambda x: x[1]['trial'])
    segment_cache_mid[dataset_name] = parsed_stimuli

# Pre-compute all rates once (avoids redundant recomputation in the NxN loop)
print("Pre-computing rates for even segments (AA)...")
rates_even_cache = {}
for name, parsed in segment_cache_mid.items():
    print(f"  Computing rates for {name} (even segments)...")
    even_segs = [seg for seg, _ in parsed[0::2]]
    rates_even_cache[name] = calculate_rates(even_segs, window_duration_sec=1.0)

print("Pre-computing rates for odd segments (AA1)...")
rates_odd_cache = {}
for name, parsed in segment_cache_mid.items():
    print(f"  Computing rates for {name} (odd segments)...")
    odd_segs = [seg for seg, _ in parsed[1::2]]
    rates_odd_cache[name] = calculate_rates(odd_segs, window_duration_sec=1.0)

# Run comparisons using cached rates
for i, AA in enumerate(AA_list):
    for j, AA1 in enumerate(AA1_list):
        rates_A = rates_even_cache[AA]
        rates_A1 = rates_odd_cache[AA1]
        
        common_ids = sorted(set(rates_A.keys()) & set(rates_A1.keys()))
        print("Length of intersection of neuron ids:", len(common_ids))
        print("Length of union - intersection of neuron ids:", len(set(rates_A.keys()) ^ set(rates_A1.keys())))
        
        values_A = [rates_A[uid] for uid in common_ids]
        values_A1 = [rates_A1[uid] for uid in common_ids]

        print(f"results/response_comparison_{AA}_{AA1}.png")
        corr = plot_corr(values_A, values_A1, f"results/AB_time_comp_correct/response_comparison_{AA}_{AA1}.png")
        data[AA1][AA] = corr
        
with open('corr.json', 'w') as f:
    json.dump(data, f, indent=2)

# # 1. Load the correlation data
# with open('corr.json', 'r') as f:
#     data = json.load(f)

# 2. Define labels (ensure they match the order in your JSON)
# Since you used these lists in your previous cell:
aa_labels = AA_list #["AA1sec", "AA3sec", "AA5sec", "AA7sec", "AA9sec", "AA15sec", "AA25sec"]
ab_labels = [x for x in reversed(AA1_list)] # ["AB1sec", "AB3sec", "AB5sec", "AB7sec", "AB9sec", "AB15sec", "AB25sec"]

# 3. Convert the nested dictionary into a 2D matrix
# Row index: AB, Column index: AA
matrix = np.zeros((len(ab_labels), len(aa_labels)))

for i, ab in enumerate(ab_labels):
    for j, aa in enumerate(aa_labels):
        matrix[i, j] = data[ab][aa]

# 4. Create the Plot
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(matrix, cmap='viridis') # You can use 'magma', 'coolwarm', etc.

# Add colorbar
cbar = ax.figure.colorbar(im, ax=ax)
cbar.ax.set_ylabel("Correlation", rotation=-90, va="bottom")

# Set ticks and labels
ax.set_xticks(np.arange(len(aa_labels)))
ax.set_yticks(np.arange(len(ab_labels)))
ax.set_xticklabels(aa_labels)
ax.set_yticklabels(ab_labels)

# Rotate the tick labels and set their alignment.
plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

# 5. Add text annotations (showing the correlation values in each cell)
for i in range(len(ab_labels)):
    for j in range(len(aa_labels)):
        text = ax.text(j, i, f"{matrix[i, j]:.2f}",
                       ha="center", va="center", color="w" if matrix[i, j] < 0.5 else "black")

ax.set_title("Correlation Heatmap: AA vs AB Stimuli Responses")
ax.set_xlabel("AA Stimulus Condition")
ax.set_ylabel("AB Stimulus Condition")

plt.tight_layout()
plt.savefig('correlation_heatmap.png')
# plt.show()
from mozaik.storage.datastore import PickledDataStore
from parameters import ParameterSet
from mozaik.storage.queries import param_filter_query
from mozaik.tools.distribution_parametrization import load_parameters
import logging
import sys
from mozaik.storage.queries import *
from mozaik.analysis.analysis import *
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
from mozaik.storage.datastore import DataStoreView
import matplotlib.pyplot as plt
import numpy as np
import ast

# Path to the experiment DataStore
# Substitute this path with the path of your own simulation run!
# path = "SelfSustainedPushPull_test_____"
path = "SelfSustainedPushPull_test:fullbig32_32_____"

data_store = PickledDataStore(
    load=True,
    parameters=ParameterSet({"root_directory": path, "store_stimuli": False}),
    replace=False,
)

data_store.print_content()

dsv = param_filter_query(
        data_store, st_name="PixelMovieExperanto", sheet_name="V1_Exc_L2/3"
    )
dsv.print_content()
segs = dsv.get_segments()

print("Sample content of Stimulus annotation:")
print(ast.literal_eval(segs[0].annotations['stimulus']))
print('-'*50)

segs, stims = dsv.get_segments(), dsv.get_stimuli()
for i in range(len(segs)):
    print(f"Segment {i}:", ast.literal_eval(segs[i].annotations['stimulus'])['trial'], ast.literal_eval(segs[i].annotations['stimulus'])['movie_name'], ast.literal_eval(segs[i].annotations['stimulus'])['duration'])
print('-'*50)

# 1. Retrieve data
bin_size = 1 / 8 * 1000

# 2. First Pass: Scan for Metadata
all_movie_names = set()
max_duration = 0.0
max_trial_index = 0

for s in segs:
    params = ast.literal_eval(s.annotations['stimulus'])
    all_movie_names.add(params['movie_name'])
    if params['duration'] > max_duration:
        max_duration = params['duration']
    if int(params['trial']) > max_trial_index:
        max_trial_index = int(params['trial'])

unique_movies = sorted(list(all_movie_names))
movie_to_index = {name: i for i, name in enumerate(unique_movies)}

num_trials = max_trial_index + 1
num_stimuli = len(unique_movies)
num_neurons = len(segs[0].get_spiketrains())
num_bins = int(np.ceil(max_duration / bin_size))

print(f"Array Shape: ({num_trials}, {num_stimuli}, {num_neurons}, {num_bins})")

# 3. Initialize with NaNs (Standard for 'missing' data)
# Note: This forces the array to be float type
spikes_all_stimuli = np.full((num_trials, num_stimuli, num_neurons, num_bins), np.nan)

# 4. Second Pass: Fill the Data
for i, seg in enumerate(segs):
    print(f"Processing Segment {i+1}/{len(segs)}")
    stim_params = ast.literal_eval(seg.annotations['stimulus'])
    
    trial_idx = int(stim_params['trial'])
    stim_idx = movie_to_index[stim_params['movie_name']]
    current_segment_duration = stim_params['duration']
    
    # Calculate how many bins strictly belong to THIS segment
    num_segment_bins = int(np.ceil(current_segment_duration / bin_size))
    
    for k in range(num_neurons):
        spike_times = np.array(seg.get_spiketrains()[k])
        
        # Filter valid spikes
        valid_spikes = spike_times[spike_times < current_segment_duration]
        
        # Calculate indices
        spike_indices = (valid_spikes // bin_size).astype(int)
        valid_indices_mask = spike_indices < num_segment_bins
        final_indices = spike_indices[valid_indices_mask]
        
        # Get counts for the valid window only
        counts = np.bincount(final_indices, minlength=num_segment_bins)
        
        # Trim just in case
        counts = counts[:num_segment_bins]
        
        # --- Assignment Logic for NaNs ---
        # We need to handle the existing NaNs. 
        # If the slot is currently NaN, treat it as 0 before adding the new counts.
        
        # 1. Get the slice of the array that corresponds to valid time
        current_data = spikes_all_stimuli[trial_idx, stim_idx, k, :num_segment_bins]
        
        # 2. Replace NaNs with 0 so we can add (if this is the first segment, they are all Nan)
        current_data = np.nan_to_num(current_data, nan=0.0)
        
        # 3. Add the new counts and write back
        spikes_all_stimuli[trial_idx, stim_idx, k, :num_segment_bins] = current_data + counts

print("Final array shape:", spikes_all_stimuli.shape)
print("Example of padding (last 5 bins of first entry):", spikes_all_stimuli[0, 0, 0, -5:])
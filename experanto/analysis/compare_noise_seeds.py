"""Quick comparison of two trials with different noise_seed values.
Loads one PixelMovieExperanto segment from each and compares spike trains.
"""
import sys
sys.path.insert(0, '/mnt/vast-nhr/projects/nix00014/goirik/MOZAIK-new/mozaik')

from mozaik.storage.datastore import PickledDataStore
from parameters import ParameterSet
from mozaik.storage.queries import param_filter_query
import numpy as np

paths = [
    "SelfSustainedPushPull_trial0_chunk0_____noise_seed:0",
    "SelfSustainedPushPull_trial1_chunk0_____noise_seed:1000",
]

for path in paths:
    print(f"\n{'='*60}")
    print(f"Loading: {path}")
    ds = PickledDataStore(
        load=True,
        parameters=ParameterSet({"root_directory": path, "store_stimuli": False}),
        replace=False,
    )

    # Get PixelMovieExperanto segments from V1_Exc_L2/3
    dsv = param_filter_query(ds, st_name="PixelMovieExperanto", sheet_name="V1_Exc_L2/3")
    segs = dsv.get_segments()
    stims = dsv.get_stimuli()
    print(f"  PixelMovieExperanto segments (V1_Exc_L2/3): {len(segs)}")

    # Look at first segment
    seg = segs[0]
    sts = seg.get_spiketrains()
    print(f"  Neurons in segment 0: {len(sts)}")

    # Collect total spikes and show a few active neurons
    total_spikes = sum(len(st) for st in sts)
    print(f"  Total spikes in segment 0: {total_spikes}")

    # Find top-5 most active neurons
    spike_counts = [(i, len(sts[i])) for i in range(len(sts))]
    spike_counts.sort(key=lambda x: -x[1])
    print(f"  Top-5 most active neurons:")
    for idx, count in spike_counts[:5]:
        times = np.array(sts[idx])
        print(f"    neuron {idx}: {count} spikes, times={times[:8]}...")

    # Also get InternalStimulus (blanks) to check those too
    dsv_blank = param_filter_query(ds, st_name="InternalStimulus", sheet_name="V1_Exc_L2/3")
    blank_segs = dsv_blank.get_segments()
    if blank_segs:
        blank_st = blank_segs[0].get_spiketrains()
        blank_total = sum(len(st) for st in blank_st)
        print(f"\n  InternalStimulus segment 0: {blank_total} total spikes")
        blank_counts = [(i, len(blank_st[i])) for i in range(len(blank_st))]
        blank_counts.sort(key=lambda x: -x[1])
        for idx, count in blank_counts[:3]:
            times = np.array(blank_st[idx])
            print(f"    neuron {idx}: {count} spikes, times={times[:8]}...")

print(f"\n{'='*60}")
print("If noise_seed works, spike times should DIFFER between trials.")
print("Connectivity/positions should be IDENTICAL.")

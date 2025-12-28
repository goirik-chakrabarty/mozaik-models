import numpy as np
import yaml
import os
import ast
import gc
import psutil
import shutil
from scipy.ndimage import gaussian_filter1d

def get_process_memory():
    """Returns current process memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

class MozaikTrialExporter:
    """
    Stateful exporter to handle batch processing of Mozaik DataStoreViews
    into a single large output file.
    """
    def __init__(self, output_dir, trial_id, sampling_rate=1000.0, smooth_param=None):
        self.output_dir = output_dir
        self.trial_id = trial_id
        self.sampling_rate = sampling_rate
        self.smooth_param = smooth_param
        
        self.meta_segments = []
        self.all_unit_spike_lists = None # Will initialize on first batch
        self.num_units = 0
        self.total_bins_accumulated = 0
        self.current_time_offset = 0.0
        
        # Temp file for Memmap chunks if needed later, 
        # currently we assume the user primarily needs spikes.npy (1D) for the large file.
        # If a full unified memmap is needed, we'd need to know total size upfront.
        
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"Exporter initialized. Target: {self.output_dir}")

    def process_batch(self, dsv_or_list):
        """
        Process a batch of DSVs. Accumulates spike times in memory lists 
        (or temp files if optimized further) and updates metadata.
        """
        if isinstance(dsv_or_list, (list, tuple)):
            dsvs = dsv_or_list
        else:
            dsvs = [dsv_or_list]
            
        if not dsvs:
            return

        print(f"Processing batch of {len(dsvs)} DSVs... (Mem: {get_process_memory():.2f} MB)")
        
        # 1. Scan Metadata for this batch
        batch_segments = []
        for dsv in dsvs:
            segment_refs = dsv.get_segments()
            for seg in segment_refs:
                try:
                    if isinstance(seg.annotations['stimulus'], str):
                        stim_params = ast.literal_eval(seg.annotations['stimulus'])
                    else:
                        stim_params = seg.annotations['stimulus']
                except (ValueError, SyntaxError):
                     print(f"Warning: Parse error for segment {seg}. Skipping.")
                     continue

                if int(stim_params['trial']) == self.trial_id:
                    batch_segments.append({
                        'segment': seg,
                        'stim_name': stim_params.get('movie_name', stim_params.get('name', 'unknown')),
                        'duration': stim_params['duration']
                    })
        
        # Sort batch by stimulus name to maintain local order
        batch_segments.sort(key=lambda x: x['stim_name'])
        
        if not batch_segments:
            print("No matching segments in this batch.")
            return

        # 2. Initialize Unit Count (On first batch)
        if self.all_unit_spike_lists is None:
            test_seg = batch_segments[0]['segment']
            self.num_units = len(test_seg.get_spiketrains())
            if hasattr(test_seg, 'release'):
                test_seg.release()
            
            # List of lists to hold spikes for each unit
            self.all_unit_spike_lists = [[] for _ in range(self.num_units)]
            print(f"Initialized for {self.num_units} units.")

        bin_size_ms = 1000.0 / self.sampling_rate

        # 3. Stream Process this Batch
        for i, meta in enumerate(batch_segments):
            seg = meta['segment']
            seg_duration = meta['duration']
            num_seg_bins = int(np.ceil(seg_duration / bin_size_ms))
            
            # Store metadata
            self.meta_segments.append(meta['stim_name'])
            
            # --- Smoothing Prep (Optional) ---
            # Even if we don't save the full memmap for the huge file to save IO, 
            # we calculate it here if the user wanted to process it.
            # Currently, to merge Memmaps efficiently, we would need to append to a file.
            # For this 'large file' loop implementation, we prioritize spikes.npy aggregation.
            
            # Load spikes
            spiketrains = seg.get_spiketrains()
            
            limit_units = min(self.num_units, len(spiketrains))
            
            for unit_idx in range(limit_units):
                spikes = np.array(spiketrains[unit_idx])
                
                # Filter valid spikes within duration
                valid_spikes = spikes[spikes < seg_duration]
                
                # Shift by global time offset
                shifted_spikes = valid_spikes + self.current_time_offset
                
                # Append to the unit's master list
                self.all_unit_spike_lists[unit_idx].append(shifted_spikes)

            # Update global offsets
            self.current_time_offset += seg_duration
            self.total_bins_accumulated += num_seg_bins
            
            if hasattr(seg, 'release'):
                seg.release()
        
        print(f"Batch complete. Current Offset: {self.current_time_offset} ms. (Mem: {get_process_memory():.2f} MB)")

    def finalize(self):
        """
        Writes the final spikes.npy and meta.yaml combining all batches.
        """
        print("Finalizing export...")
        print(f"Memory before concat: {get_process_memory():.2f} MB")
        
        final_flat_spikes = []
        unit_indices = [0]
        
        # Flatten the list of lists
        for unit_idx, unit_chunks in enumerate(self.all_unit_spike_lists):
            if unit_chunks:
                unit_arr = np.concatenate(unit_chunks)
            else:
                unit_arr = np.array([])
            
            final_flat_spikes.append(unit_arr)
            unit_indices.append(unit_indices[-1] + len(unit_arr))
            
            # Clear memory of this unit's list as we go
            self.all_unit_spike_lists[unit_idx] = None

        spikes_1d = np.concatenate(final_flat_spikes)
        
        # Save Main Output
        np.save(os.path.join(self.output_dir, 'spikes.npy'), spikes_1d)
        
        # Save Metadata
        meta_data = {
            'num_units': self.num_units,
            'num_timepoints': self.total_bins_accumulated,
            'trial_id': self.trial_id,
            'sampling_rate': self.sampling_rate,
            'spike_indices': unit_indices[:-1],
            'stimuli_order': self.meta_segments,
            'smoothing': self.smooth_param
        }
        
        with open(os.path.join(self.output_dir, 'meta.yaml'), 'w') as f:
            yaml.dump(meta_data, f)
            
        print(f"Export Complete. Total Units: {self.num_units}, Total Time: {self.current_time_offset}ms")
        print(f"Final Memory: {get_process_memory():.2f} MB")


def export_mozaik_trial_streamed(dsv_or_list, output_dir, trial_id, sampling_rate=1000.0, 
                                 smooth_param=None):
    """
    Wrapper function for backward compatibility. 
    Processes the given DSV(s) in one go using the Exporter class.
    """
    exporter = MozaikTrialExporter(output_dir, trial_id, sampling_rate, smooth_param)
    exporter.process_batch(dsv_or_list)
    exporter.finalize()
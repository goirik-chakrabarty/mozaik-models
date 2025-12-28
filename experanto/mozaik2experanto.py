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
    Supports appending to an existing export if append_mode=True.
    """
    def __init__(self, output_dir, trial_id, sampling_rate=1000.0, smooth_param=None, append_mode=False):
        self.output_dir = output_dir
        self.trial_id = trial_id
        self.sampling_rate = sampling_rate
        self.smooth_param = smooth_param
        
        self.meta_segments = []
        self.all_unit_spike_lists = None 
        self.num_units = 0
        self.total_bins_accumulated = 0
        self.current_time_offset = 0.0
        
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Check for existing data if append_mode is active
        if append_mode:
            self._load_existing_state()
        else:
            print(f"Exporter initialized. Target: {self.output_dir} (New Export)")

    def _load_existing_state(self):
        """Attempts to load state from existing meta.yaml and spikes.npy."""
        meta_path = os.path.join(self.output_dir, 'meta.yaml')
        spikes_path = os.path.join(self.output_dir, 'spikes.npy')
        
        if os.path.exists(meta_path) and os.path.exists(spikes_path):
            print(f"Loading existing data from {self.output_dir}...")
            
            # 1. Load Metadata
            with open(meta_path, 'r') as f:
                meta_data = yaml.safe_load(f)
            
            # Verify compatibility
            if meta_data.get('sampling_rate') != self.sampling_rate:
                raise ValueError("Sampling rate mismatch with existing data.")
            if meta_data.get('trial_id') != self.trial_id:
                print(f"Warning: Existing data has trial_id {meta_data.get('trial_id')}, expected {self.trial_id}")

            self.num_units = meta_data['num_units']
            self.total_bins_accumulated = meta_data['num_timepoints']
            self.meta_segments = meta_data.get('stimuli_order', [])
            spike_indices = meta_data['spike_indices']
            
            # Calculate current time offset from accumulated bins
            bin_size_ms = 1000.0 / self.sampling_rate
            self.current_time_offset = self.total_bins_accumulated * bin_size_ms
            
            # 2. Load Spikes and Reconstruct Lists
            # We must load the full array to append to it efficiently in memory
            flat_spikes = np.load(spikes_path)
            
            self.all_unit_spike_lists = []
            
            # Reconstruct list of lists using the indices (CSR-like structure)
            # indices stores the start of each unit's chunk. 
            # We assume the chunks are contiguous and cover the whole array.
            extended_indices = spike_indices + [len(flat_spikes)]
            
            for i in range(self.num_units):
                start = extended_indices[i]
                end = extended_indices[i+1]
                # Copying to list allows appending later
                unit_spikes = flat_spikes[start:end]
                self.all_unit_spike_lists.append([unit_spikes]) 
                
            print(f"Resumed from offset: {self.current_time_offset} ms with {self.num_units} units.")
            del flat_spikes # Free raw buffer
            gc.collect()
        else:
            print("No existing data found to append. Starting fresh.")

    def process_batch(self, dsv_or_list):
        """
        Process a batch of DSVs. Accumulates spike times in memory lists 
        and updates metadata.
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

        # 2. Initialize Unit Count (On first batch if not loaded from disk)
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
        # Note: If we loaded existing data, unit_chunks will contain [old_array, new_array_1, new_array_2...]
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
                                 smooth_param=None, append_mode=False):
    """
    Wrapper function for backward compatibility. 
    Processes the given DSV(s) in one go using the Exporter class.
    """
    exporter = MozaikTrialExporter(output_dir, trial_id, sampling_rate, smooth_param, append_mode)
    exporter.process_batch(dsv_or_list)
    exporter.finalize()
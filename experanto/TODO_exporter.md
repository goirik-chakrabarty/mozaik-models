# TODO: Exporter Bugs to Fix Before Re-export

## 1. Unit mismatch: spike times in milliseconds, screen timestamps in seconds

**File:** `mozaik2experanto.py`, `MozaikTrialExporter`

Spike times are accumulated and stored in **milliseconds** (because `sampling_rate=1000.0`
and the time offset is in ms). The screen timestamps written by the screen exporter are in
**seconds**. This means `SpikeInterpolator` receives query times in seconds but compares
them against spike times in ms — spike counts will always be wrong.

**Fix in `finalize()`:**
```python
# Convert spike times ms -> seconds before saving
spikes_1d /= 1000.0

meta_data = {
    ...
    'start_time': 0.0,
    'end_time': self.current_time_offset / 1000.0,  # ms -> seconds
    ...
}
```
Also divide `self.current_time_offset` by 1000 wherever it is used as a time value.
After re-export, set `interpolation_window: 0.3` in `configs/spikes.yaml`.

---

## 2. spike_indices off-by-one: last unit's end index is missing

**File:** `mozaik2experanto.py`, `MozaikTrialExporter.finalize()`

`unit_indices` is built as `[0, end_0, end_1, ..., end_{N-1}]` (length N+1).
The exporter writes `unit_indices[:-1]`, which drops `end_{N-1}` (the last unit's
end position). The `SpikeInterpolator` (updated to use `n_signals = len(indices)`)
now expects exactly N entries of the form `[end_0, end_1, ..., end_{N-1}]`.

**Fix in `finalize()`:**
```python
# Before (wrong):
'spike_indices': unit_indices[:-1],

# After (correct):
'spike_indices': unit_indices[1:],   # [end_0, end_1, ..., end_{N-1}]
```

---

## 3. Trailing out-of-bounds trial in screen combined_meta.json

**File:** screen exporter / data generation

Trial `02460` (a blank trial) was written to `combined_meta.json` with
`first_frame_idx = 202140`, which equals `len(timestamps)` and is therefore
out of bounds. This caused an `IndexError` in `ChunkDataset._read_trials()`.

**Fix:** before writing a trial entry to `combined_meta.json`, validate that
`first_frame_idx < len(timestamps)`.

As a one-time patch the entry was already removed from the existing dataset at:
`/mnt/vast-react/projects/neural_foundation_model/mozaik_data/dynamic29513-3-5-Video-full-mozaik-trial1/screen/combined_meta.json`

---

## 4. start_time not written to meta.yml

**File:** `mozaik2experanto.py`, `MozaikTrialExporter.finalize()`

`start_time` is not included in the written `meta_data` dict. The
`SpikeInterpolator` requires `meta["start_time"]`. The existing data happens
to have `start_time: 0` from a previous exporter version; new exports will fail.

**Fix in `finalize()`:**
```python
meta_data = {
    ...
    'start_time': 0.0,
    'end_time': self.current_time_offset / 1000.0,
    ...
}
```

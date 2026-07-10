import argparse
import logging
import sys

from mozaik.analysis.analysis import *
from mozaik.storage.datastore import PickledDataStore
from mozaik.storage.queries import *
from mozaik.storage.queries import param_filter_query
from mozaik.tools.distribution_parametrization import load_parameters
from parameters import ParameterSet

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
import ast
import gc
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from mozaik2experanto import (MozaikScreenExporter, MozaikTrialExporter,
                              load_tier_reference)
from mozaik.storage.datastore import DataStoreView
from tqdm import tqdm

sys.path.append("/experanto")
import experanto

"""
  Usage examples:

  # All 12 chunks in one go
  python -u export.py 1 --n-chunks 12

  # Split across two jobs (48h each):
  #   Job 1: chunks 0-5, fresh export
  python -u export.py 1 --n-chunks 12 --chunk-start 0 --chunk-end 6
  #   Job 2: chunks 6-11, appends to previous
  python -u export.py 1 --n-chunks 12 --chunk-start 6 --chunk-end 12

  # 128 chunks split into 4 jobs of 32:
  python -u export.py 0 --n-chunks 128 --chunk-start 0  --chunk-end 32
  python -u export.py 0 --n-chunks 128 --chunk-start 32 --chunk-end 64
  python -u export.py 0 --n-chunks 128 --chunk-start 64 --chunk-end 96
  python -u export.py 0 --n-chunks 128 --chunk-start 96 --chunk-end 128

  # Screen only (timestamps.npy uses all chunk JSONs, no DataStore needed for most)
  python -u export.py 1 --screen-only --n-chunks 12

  # Spikes only, specific trials
  python -u export.py 3 4 5 --spikes-only --n-chunks 12

  # Screen with modality filter
  python -u export.py 1 --screen-only --modality-filter image --n-chunks 12
"""


parser = argparse.ArgumentParser(
    description="Export Mozaik simulation data to Experanto format."
)
parser.add_argument(
    "trials",
    nargs="*",
    type=int,
    default=list(range(1, 20)),
    help="Trial numbers to export (default: 1-19)",
)
parser.add_argument(
    "--screen-only",
    action="store_true",
    help="Export screen data only (skip spike export)",
)
parser.add_argument(
    "--spikes-only",
    action="store_true",
    help="Export spike data only (skip screen export)",
)
parser.add_argument(
    "--modality-filter",
    nargs="+",
    default=None,
    help="Screen modalities to export (e.g. --modality-filter image)",
)
parser.add_argument(
    "--n-chunks",
    type=int,
    default=4,
    help="Total number of chunks per trial (default: 4)",
)
parser.add_argument(
    "--chunk-start",
    type=int,
    default=None,
    help="First chunk index to process (inclusive, default: 0)",
)
parser.add_argument(
    "--chunk-end",
    type=int,
    default=None,
    help="Last chunk index to process (exclusive, default: n-chunks)",
)
parser.add_argument(
    "--batch-size",
    type=int,
    default=4,
    help="Number of chunks to hold in memory before flushing (default: 4)",
)
parser.add_argument(
    "--tier-reference",
    type=str,
    default=None,
    help="Path to a reference combined_meta.json whose tier assignments "
    "should be used (e.g. from the original mouse dataset)",
)
args = parser.parse_args()

export_spikes = not args.screen_only
export_screen = not args.spikes_only
chunk_start = args.chunk_start if args.chunk_start is not None else 0
chunk_end = args.chunk_end if args.chunk_end is not None else args.n_chunks
is_resume = chunk_start > 0

chunk_dir = os.environ.get("CHUNK_DIR", "/data/mozaik_chunk")
output_prefix = os.environ.get(
    "OUTPUT_PREFIX", "/data/mozaik_data_dynamic26872-17-20-Video-mozaik-trial"
)
datastore_prefix = os.environ.get("DATASTORE_PREFIX", "")

# Load tier reference mapping if provided
tier_reference = None
if args.tier_reference:
    print(f"Loading tier reference from {args.tier_reference}")
    tier_reference = load_tier_reference(args.tier_reference)
    print(f"Loaded {len(tier_reference)} condition_hash -> tier mappings")

for trial in tqdm(args.trials):
    experiment_dir = f"{output_prefix}{trial}"
    responses_dir = f"{experiment_dir}/responses/"

    # Initialize spike exporter (append_mode if resuming from a previous chunk range)
    if export_spikes:
        exporter = MozaikTrialExporter(
            responses_dir,
            trial_id=trial,
            sampling_rate=1000.0,
            append_mode=is_resume,
        )

    # Initialize screen exporter with ALL chunk JSONs (needed for correct
    # timestamps.npy even when only processing a subset of chunks for spikes).
    # Screen export is fast — no DataStore loading needed beyond resolving movie_path.
    if export_screen:
        chunk_paths = [f"{chunk_dir}/{trial}_{c}.json" for c in range(args.n_chunks)]
        screen_exporter = MozaikScreenExporter(
            output_dir=experiment_dir,
            chunk_paths=chunk_paths,
            frame_duration_ms=7.0,
            movie_frame_duration_ms=35.0,
            modality_filter=args.modality_filter,
            tier_reference=tier_reference,
        )

    dsv_list = []
    # In screen-only mode we only need one chunk to resolve movie_path
    if args.screen_only:
        chunks_to_load = range(chunk_start, min(chunk_start + 1, chunk_end))
    else:
        chunks_to_load = range(chunk_start, chunk_end)

    # Read the LGN step-current noise seed from first chunk JSON to construct the datastore dir name.
    # The sim appends the modified-parameter key to the dir, so the key is now
    # lgn_stepcurrentsource_noise_seed (renamed from noise_seed; see mozaik commit 9b0d489).
    # Accept the legacy `noise_seed` manifest field too, so pre-rename chunk manifests still work.
    first_chunk_path = f"{chunk_dir}/{trial}_{chunk_start}.json"
    with open(first_chunk_path) as f:
        chunk_meta = json.load(f)
    noise_seed = chunk_meta[0].get(
        "lgn_stepcurrentsource_noise_seed", chunk_meta[0].get("noise_seed", None)
    )

    for i, chunk in enumerate(tqdm(chunks_to_load)):
        if noise_seed is not None:
            path = os.path.join(datastore_prefix, f"SelfSustainedPushPull_trial{trial}_chunk{chunk}_____lgn_stepcurrentsource_noise_seed:{noise_seed}")
        else:
            path = os.path.join(datastore_prefix, f"SelfSustainedPushPull_trial{trial}_chunk{chunk}_____")

        # Load DataStore
        data_store = PickledDataStore(
            load=True,
            parameters=ParameterSet({"root_directory": path, "store_stimuli": False}),
            replace=False,
        )

        # Create View — no st_name filter so blank segments (InternalStimulus)
        # are included, keeping spike timeline aligned with screen timeline
        dsv = param_filter_query(data_store, sheet_name="V1_Exc_L2/3")
        dsv_list.append(dsv)

        # Process in batches to manage memory
        if (i + 1) % args.batch_size == 0:
            if export_spikes:
                exporter.process_batch(dsv_list)
            if export_screen:
                screen_exporter.process_batch(dsv_list)

            dsv_list = []
            del data_store
            gc.collect()

    # Process any remaining items in the list
    if dsv_list:
        if export_spikes:
            exporter.process_batch(dsv_list)
        if export_screen:
            screen_exporter.process_batch(dsv_list)

    # Finalize
    if export_spikes:
        exporter.finalize()
    if export_screen:
        screen_exporter.finalize()

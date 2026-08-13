import argparse
import logging
import os
import sys

# Import side effects: registers analysis classes needed to unpickle datastores, and puts the
# Experanto package on the path (both container-specific — kept in this thin entry point).
from mozaik.analysis.analysis import *  # noqa: F401,F403

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from mozaik.meta_workflow.experanto_export import run_experanto_export
from mozaik.tools.experanto_export import load_tier_reference

sys.path.append("/experanto")
import experanto  # noqa: F401

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

chunk_dir = os.environ.get("CHUNK_DIR", "/data/mozaik_chunk")
output_prefix = os.environ.get(
    "OUTPUT_PREFIX", "/data/mozaik_data_dynamic26872-17-20-Video-mozaik-trial"
)
datastore_prefix = os.environ.get("DATASTORE_PREFIX", "")

# Which sheets to fold into spikes.npy. Unset/empty = every recorded sheet (multi-sheet default).
# Comma-separated (e.g. "V1_Exc_L2/3" or "V1_Exc_L4,V1_Exc_L2/3") restricts to a subset.
_sheet_env = os.environ.get("SHEET_NAMES", "").strip()
sheet_names = [s.strip() for s in _sheet_env.split(",") if s.strip()] or None
print(f"Sheet selection: {sheet_names if sheet_names else 'ALL recorded sheets'}")

# Load tier reference mapping if provided
tier_reference = None
if args.tier_reference:
    print(f"Loading tier reference from {args.tier_reference}")
    tier_reference = load_tier_reference(args.tier_reference)
    print(f"Loaded {len(tier_reference)} condition_hash -> tier mappings")

# Delegate the whole trial/chunk loop (datastore resolution, batching, resume/append, finalize) to
# the generic driver in the mozaik package. Project-specific path patterns stay here as closures:
#   - output_dir_for_trial: where each trial's Experanto shard is written
#   - chunk_paths_for_trial: ALL chunk JSONs for the trial (screen timestamps need every chunk even
#     when only a subset is processed for spikes)
run_experanto_export(
    trials=args.trials,
    n_chunks=args.n_chunks,
    output_dir_for_trial=lambda t: f"{output_prefix}{t}",
    chunk_paths_for_trial=lambda t: [f"{chunk_dir}/{t}_{c}.json" for c in range(args.n_chunks)],
    datastore_prefix=datastore_prefix,
    sheet_names=sheet_names,
    chunk_start=chunk_start,
    chunk_end=chunk_end,
    batch_size=args.batch_size,
    export_spikes=export_spikes,
    export_screen=export_screen,
    modality_filter=args.modality_filter,
    tier_reference=tier_reference,
)

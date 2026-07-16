#!/usr/bin/env python
"""Generate chunk JSON files for RandomizedExperanto experiments.

Reads stimulus metadata from a dataset directory, shuffles stimuli per trial,
and splits them into time-balanced chunks.

Usage:
    python generate_chunks.py \
        --data-root /data/test_upsampling_.../dynamic26872-..._30hz \
        --output-dir /data/mozaik_chunk_test3 \
        --n-trials 3 --n-chunks 1

    # Production (20 trials, 12 chunks each):
    python generate_chunks.py \
        --data-root /data/test_upsampling_.../dynamic26872-..._30hz \
        --output-dir /data/mozaik_chunk \
        --n-trials 20 --n-chunks 12
"""

import argparse
import heapq
import json
import os
import random
import sys

import yaml

# Time cost estimates in seconds (from empirical measurements).
# "first_*" = first presentation of a unique stimulus (cold cache),
# "*" = repeat presentation (warm cache).
TIME_COSTS = {
    "first_image": 80,
    "image": 70,
    "blank": 75,
    # Video cost is PER-FRAME, not flat: measured from the S32000 pilot as ~48 s per-presentation
    # get_data overhead + ~0.55 s/frame. A flat per-video cost badly under-weights long (900-frame)
    # videos in the greedy balancer. See docs/plan/audit/26-07-14_S32000_FULL_RUN_SIZING.md §3.
    "video_base": 48,
    "video_per_frame": 0.55,
}


def scan_metadata(data_root):
    """Read all stimulus metadata YAMLs and return list of (filename, modality, num_frames)."""
    meta_dir = os.path.join(data_root, "screen", "meta")
    if not os.path.isdir(meta_dir):
        print(f"Error: metadata directory not found: {meta_dir}", file=sys.stderr)
        sys.exit(1)

    entries = []
    for fname in sorted(os.listdir(meta_dir)):
        if not fname.endswith(".yml"):
            continue
        with open(os.path.join(meta_dir, fname), "r") as f:
            meta = yaml.safe_load(f)
        modality = meta.get("modality")
        if modality in ("image", "video"):
            entries.append((fname, modality, int(meta.get("num_frames", 1))))
    return entries


def estimate_cost(item, seen_files):
    """Estimate time cost of a stimulus item, including blanks for images."""
    modality = item["modality"]
    filename = item["file"]
    cost = 0

    # Images get pre-blank and post-blank
    if modality == "image":
        cost += TIME_COSTS["blank"] * 2

    is_first = filename not in seen_files
    if modality == "image":
        cost += TIME_COSTS["first_image"] if is_first else TIME_COSTS["image"]
    elif modality == "video":
        # Per-frame cost dominates for long videos; num_frames comes from the yml metadata.
        cost += TIME_COSTS["video_base"] + item["num_frames"] * TIME_COSTS["video_per_frame"]

    seen_files.add(filename)
    return cost


def split_time_balanced(stimuli, n_chunks):
    """Split stimuli into n_chunks with balanced estimated walltime.

    Uses greedy min-heap assignment: each stimulus goes to the chunk
    with the lowest accumulated time so far.
    """
    if n_chunks == 1:
        return [stimuli]

    # heap entries: (total_time, chunk_index)
    heap = [(0.0, i) for i in range(n_chunks)]
    chunks = [[] for _ in range(n_chunks)]
    # Track seen files per chunk for first-vs-repeat cost estimation
    seen_per_chunk = [set() for _ in range(n_chunks)]

    for item in stimuli:
        total_time, idx = heapq.heappop(heap)
        chunks[idx].append(item)
        cost = estimate_cost(item, seen_per_chunk[idx])
        heapq.heappush(heap, (total_time + cost, idx))

    return chunks


def estimate_chunk_time(chunk):
    """Estimate total walltime for a chunk in seconds."""
    seen = set()
    total = 0.0
    for item in chunk:
        total += estimate_cost(item, seen)
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Generate chunk JSON files for RandomizedExperanto experiments."
    )
    parser.add_argument(
        "--data-root",
        required=True,
        help="Path to dataset directory containing screen/meta/*.yml",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write {trial}_{chunk}.json files",
    )
    parser.add_argument(
        "--n-trials", type=int, required=True, help="Number of trials"
    )
    parser.add_argument(
        "--n-chunks", type=int, required=True, help="Number of chunks per trial"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Base random seed (default: 42)"
    )
    args = parser.parse_args()

    # Scan metadata
    print(f"Scanning metadata from: {args.data_root}/screen/meta/")
    entries = scan_metadata(args.data_root)
    n_images = sum(1 for _, m, _ in entries if m == "image")
    n_videos = sum(1 for _, m, _ in entries if m == "video")
    print(f"Found {len(entries)} stimuli ({n_images} images, {n_videos} videos)")

    if not entries:
        print("Error: no stimulus metadata found", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Generate chunks for each trial
    for trial in range(args.n_trials):
        lgn_stepcurrentsource_noise_seed = trial * 1000
        stimuli = [
            {
                "modality": modality,
                "file": fname,
                "trial": trial,
                "lgn_stepcurrentsource_noise_seed": lgn_stepcurrentsource_noise_seed,
                # num_frames is used only for cost balancing; stripped before writing (see below)
                # so the emitted chunk schema stays identical to the sim-validated format.
                "num_frames": num_frames,
            }
            for fname, modality, num_frames in entries
        ]
        rng = random.Random(args.seed + trial)
        rng.shuffle(stimuli)

        chunks = split_time_balanced(stimuli, args.n_chunks)

        print(f"\nTrial {trial}:")
        for chunk_idx, chunk in enumerate(chunks):
            out_path = os.path.join(args.output_dir, f"{trial}_{chunk_idx}.json")
            # Strip the cost-only num_frames field so the emitted record schema is exactly
            # {modality, file, trial, lgn_stepcurrentsource_noise_seed} as the sim expects.
            with open(out_path, "w") as f:
                json.dump(
                    [{k: v for k, v in s.items() if k != "num_frames"} for s in chunk], f
                )

            est_time = estimate_chunk_time(chunk)
            n_img = sum(1 for s in chunk if s["modality"] == "image")
            n_vid = sum(1 for s in chunk if s["modality"] == "video")
            print(
                f"  Chunk {chunk_idx}: {len(chunk)} stimuli "
                f"({n_img} img, {n_vid} vid), "
                f"est. {est_time/3600:.1f}h ({est_time/3600/24:.2f}d) "
                f"-> {out_path}"
            )

    total_files = args.n_trials * args.n_chunks
    print(f"\nDone. Generated {total_files} chunk files in {args.output_dir}/")


if __name__ == "__main__":
    main()

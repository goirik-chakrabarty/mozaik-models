# -*- coding: utf-8 -*-
"""
This is the implementation of the model corresponding to the pre-print `Iso-orientation bias of layer 2/3 connections: the unifying mechanism of spontaneous, visually and optogenetically driven V1 dynamics`
Rózsa, T., Cagnol, R., Antolík, J. (2024).
https://www.biorxiv.org/ TODO: Update
"""

import sys

import matplotlib

matplotlib.use("Agg")

import mozaik
from experiments import create_experiments_video, create_randomized_experanto
# from analysis_and_visualization import perform_analysis_and_visualization_spont
from model import SelfSustainedPushPull
from mozaik.storage.datastore import Hdf5DataStore, PickledDataStore
from mpi4py import MPI
from parameters import ParameterSet

print(">>>>>>>>>>>>>>>>", mozaik.__file__)

import sys

import mozaik.controller
from mozaik.controller import run_workflow, setup_logging
from mpi4py import MPI
from pyNN import nest

mpi_comm = MPI.COMM_WORLD

import nest

nest.Install("stepcurrentmodule")

# --- Workflow 2: optional inline Experanto export for single-chunk runs -------------------------
# `python run.py <sim> <threads> <param> <run_name> --export` simulates one chunk and then, on
# rank 0, exports that datastore to a FULL Experanto shard (spikes + screen) written NEXT TO the
# datastore — no separate export job. Reuses the CSNG-MFF #6 exporter (mozaik.tools.experanto_export).
# Multi-chunk datasets must still use the canonical export.py (workflow 1), which concatenates chunks.
import os

EXPORT_INLINE = "--export" in sys.argv
if EXPORT_INLINE:
    sys.argv.remove("--export")  # strip before run_workflow parses the mozaik positional CLI


def export_datastore_inline(data_store):
    """Export the just-simulated (in-memory) datastore to a full Experanto shard beside it.

    Reads the single chunk this run simulated (TRIAL/CHUNK/CHUNK_DIR — the same env
    create_randomized_experanto uses). Rank-0 only: PyNN gathers all ranks onto MPI_ROOT, so only
    rank 0's in-memory store holds every neuron's spikes.
    """
    from mozaik.meta_workflow.experanto_export import export_dsvs_to_experanto
    from mozaik.storage.queries import param_filter_query

    trial = int(os.environ.get("TRIAL", 0))
    chunk = int(os.environ.get("CHUNK", 0))
    chunk_dir = os.environ.get("CHUNK_DIR", "/data/mozaik_chunk")

    experiment_dir = os.path.join(data_store.parameters.root_directory, "experanto")
    chunk_path = f"{chunk_dir}/{trial}_{chunk}.json"
    print(
        f"[inline-export] trial={trial} chunk={chunk} -> {experiment_dir} "
        f"(chunk_json={chunk_path})",
        flush=True,
    )

    # One DSV over the in-memory store; no st_name filter so blank (InternalStimulus) segments are
    # kept and the spike timeline stays aligned with the screen timeline; no sheet_name filter so every
    # recorded sheet is folded into spikes.npy (same as export.py). SHEET_NAMES env restricts the subset.
    dsv = param_filter_query(data_store)

    _sheet_env = os.environ.get("SHEET_NAMES", "").strip()
    sheet_names = [s.strip() for s in _sheet_env.split(",") if s.strip()] or None

    export_dsvs_to_experanto(
        [dsv],
        experiment_dir,
        trial_id=trial,
        chunk_paths=[chunk_path],
        sheet_names=sheet_names,
        frame_duration_ms=7.0,
        movie_frame_duration_ms=35.0,
    )
    print(f"[inline-export] done -> {experiment_dir}", flush=True)


if True:
    data_store, model = run_workflow(
        "SelfSustainedPushPull", SelfSustainedPushPull, create_randomized_experanto
    )
    if False:
        model.connectors["V1AffConnectionOn"].store_connections(data_store)
        model.connectors["V1AffConnectionOff"].store_connections(data_store)
        model.connectors["V1AffInhConnectionOn"].store_connections(data_store)
        model.connectors["V1AffInhConnectionOff"].store_connections(data_store)
        model.connectors["V1L4ExcL4ExcConnection"].store_connections(data_store)
        model.connectors["V1L4ExcL4InhConnection"].store_connections(data_store)
        model.connectors["V1L4InhL4ExcConnection"].store_connections(data_store)
        model.connectors["V1L4InhL4InhConnection"].store_connections(data_store)
        model.connectors["V1L23ExcL23ExcConnection"].store_connections(data_store)
        model.connectors["V1L23ExcL23InhConnection"].store_connections(data_store)
        model.connectors["V1L23InhL23ExcConnection"].store_connections(data_store)
        model.connectors["V1L23InhL23InhConnection"].store_connections(data_store)
        model.connectors["V1L4ExcL23ExcConnection"].store_connections(data_store)
        model.connectors["V1L4ExcL23InhConnection"].store_connections(data_store)
    data_store.save()

    # Workflow 2: inline export (rank 0 only) — after the datastore is saved.
    if EXPORT_INLINE and mozaik.mpi_comm.rank == mozaik.MPI_ROOT:
        export_datastore_inline(data_store)
else:
    setup_logging()
    data_store = PickledDataStore(
        load=True,
        parameters=ParameterSet(
            {"root_directory": "SelfSustainedPushPull_test____", "store_stimuli": False}
        ),
        replace=True,
    )

# if mpi_comm.rank == 0:
#    print("Starting visualization")
#    perform_analysis_and_visualization_spont(data_store)

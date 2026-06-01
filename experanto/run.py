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

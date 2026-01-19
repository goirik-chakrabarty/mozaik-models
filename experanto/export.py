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
import gc

from mozaik2experanto import MozaikScreenExporter, MozaikTrialExporter

sys.path.append('/experanto')
import experanto

output_dir = '/project/data'

# Initialize the exporter ONCE before the loop
exporter = MozaikTrialExporter(output_dir, trial_id=1, sampling_rate=1000.0)
# screen_exporter = MozaikScreenExporter(output_dir, trial_id=1)

dsv_list = []
for num in range(0, 156):
    stimuli = num * 8
    # path = f"SelfSustainedPushPull_test:fullbig32_{stimuli}_____"
    path = f"SelfSustainedPushPull_mozaik32_trials10_{stimuli}_____" # 2,3 are not completed.
    
    # Load DataStore
    data_store = PickledDataStore(
        load=True,
        parameters=ParameterSet({"root_directory": path, "store_stimuli": False}),
        replace=False,
    )
    
    # Create View
    dsv = param_filter_query(
        data_store, st_name="PixelMovieExperanto", sheet_name="V1_Exc_L2/3"
    )
    dsv_list.append(dsv)
    
    # Process in batches of 2
    if (num + 1) % 12 == 0:
        # Feed the batch to the exporter
        exporter.process_batch(dsv_list)
        # screen_exporter.process_batch(dsv_list)
        
        # Clear list to free memory references to the DataStores
        dsv_list = []
        
        # Important: Verify if you need to manually close/del data_store here 
        # to ensure RAM is freed before the next iteration.
        del data_store
        gc.collect()

# Process any remaining items in the list
if dsv_list:
    exporter.process_batch(dsv_list)
    # screen_exporter.process_batch(dsv_list)

# Finalize writes the single large file
exporter.finalize()
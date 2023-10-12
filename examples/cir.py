"""
This script shows how to get the channel impulse response when
performing ranging. This script is intended to be used with at
least two UWB modules.

This script publishes messages continuously until terminated.
"""
from pyuwb import UwbModule, find_uwb_serial_ports
import numpy as np

# Find all ports with a connected UWB module.
ports = find_uwb_serial_ports()

# Create a UwbModule object for each module.
uwb = [UwbModule(port, verbose=False) for port in ports]

# Get the ID of each module.
ids = [u.get_id() for u in uwb]

# Print the IDs.
for i in range(len(ids)):
    print("UWB " + str(i) + " ID: " + str(ids[i]["id"]))

# Turn on passive listening for all modules.
[u.set_passive_listening() for u in uwb]

# Channel impulse response callback. This will get called whenever a CIR
# measurement is obtained by any of the modules.
def cb_cir(data, my_id):
    msg = {}
    msg["from_id"] = data[0]
    msg["to_id"] = data[1]
    msg["idx"] = data[2] + data[3] / 1e3
    msg["cir"] = data[4:]
    print("\nCIR received at Tag ", my_id, ": ", msg)

# Register the callbacks.
[u.register_cir_callback(cb_cir, ids[i]["id"]) for i, u in enumerate(uwb)]

while True:
    # Randomly choose two of the modules to range.
    tags_to_range = np.random.choice(range(len(ids)),2,replace=False)
    
    data = uwb[tags_to_range[0]].do_twr(
        target_id = ids[tags_to_range[1]]['id'],
        ds_twr = True,
        get_cir=True,
    )
    print("\nMeasurement received at Tag ", ids[tags_to_range[0]]['id'], ": ", data,)

    # Read from the queue of spontaneous messages and process callbacks.
    [u.wait_for_messages(timeout=0.1) for u in uwb]
    
"""
This script shows a basic example of how to perform TWR using
this package's API. This script is intended to be used with at
least two UWB modules.

This script publishes messages continuously until terminated.
"""
from pyuwb import UwbModule, find_uwb_serial_ports

# Find all ports with a connected UWB module.
ports = find_uwb_serial_ports()

# Create a UwbModule object for each module.
uwb = [UwbModule(port, verbose=False) for port in ports]

# Get the ID of each module.
ids = [u.get_id() for u in uwb]

# Print the IDs.
for i in range(len(ids)):
    print("UWB " + str(i) + " ID: " + str(ids[i]["id"]))

# Perform TWR
while True:
    data = uwb[0].do_twr(
        target_id = ids[1]['id'],
    )
    print(data)
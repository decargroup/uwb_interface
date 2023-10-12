"""
This script shows how to use callbacks to process data received by the UWB
modules. It is intended to be used with at least two UWB modules. UWB 0 is 
the initiator, and UWB 1 is the target.

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

# Ranging callback. This will get called whenever a range measurement is
# obtained by the second module when it is the target for a ranging transaction
# initiated by the first module. 
def cb_target(data, my_id):
    if data[2] != 0: 
        # Data is valid
        msg = {}
        msg["neighbour"] = data[0]
        msg['range'] = data[1]
        msg['tx1'] = data[2]
        msg['rx1'] = data[3]
        msg['tx2'] = data[4]
        msg['rx2'] = data[5]
        msg['tx3'] = data[6]
        msg['rx3'] = data[7]
        msg['fpp1'] = data[8]
        msg['fpp2'] = data[9]
        msg['skew1'] = data[10]
        msg['skew2'] = data[11]
        msg["is_valid"] = True
        print("Measurement received at Tag ", my_id, ": ", msg)

# Register the callback.
uwb[1].register_range_callback(cb_target, ids[1]['id'])

# Perform TWR ranging transaction between the first and second modules.
# This only stops when the user presses Ctrl+C.
counter = 0
while True:
    data = uwb[0].do_twr(
        ids[1]['id'], # Target ID
        ds_twr=True, # Double-sided TWR
        meas_at_target=True, # Make measurement available at target, not just initiator
    )
    print("Measurement received at Tag ", ids[0]['id'], ": ", data)

    # Read from the queue of spontaneous messages and process callbacks.
    uwb[1].wait_for_messages()

    counter += 1
    print(counter)

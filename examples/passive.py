"""
This script shows how to get the passive listening measurements
using callbacks. It is intended to be used with the following setup:

    UWB 0 <----> UWB 1 <----> UWB 2
    
UWB 0 and UWB 1 are performing TWR ranging, while UWB 2 is passively listening
for messages. UWB 0 is the initiator, and UWB 1 is the target. UWB 2 is not
involved in the ranging transaction, but it can still receive messages
through passive listening.

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

# Turn on passive listening for the third module.
uwb[2].set_passive_listening()

# Passive-listening callback. This will get called whenever a message is
# received by the third module passively while the first and second modules
# are ranging.
def cb_passive(data, my_id):
    if data[2] != 0: 
        # Data is valid
        msg = {}
        msg["from_id"] = data[0]
        msg["to_id"] = data[1]
        msg['rx1'] = data[2]
        msg['rx2'] = data[3]
        msg['rx3'] = data[4]
        msg['tx1_n'] = data[5]
        msg['rx1_n'] = data[6]
        msg['tx2_n'] = data[7]
        msg['rx2_n'] = data[8]
        msg['tx3_n'] = data[9]
        msg['rx3_n'] = data[10]
        msg['fpp1'] = data[11]
        msg['fpp2'] = data[12]
        msg['fpp3'] = data[13]
        msg['skew1'] = data[14]
        msg['skew2'] = data[15]
        msg['skew3'] = data[16]
        msg['fpp1_n'] = data[17]
        msg['fpp2_n'] = data[18]
        msg['skew1_n'] = data[19]
        msg['skew2_n'] = data[20]
        print("Passive measurement at Tag ", my_id, ": ", msg)

# Register the callbacks.
uwb[2].register_listening_callback(cb_passive, ids[2]['id'])

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
    uwb[2].wait_for_messages()    

    counter += 1
    print(counter)

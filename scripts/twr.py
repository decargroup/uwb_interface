from pyuwb import UwbModule, find_uwb_serial_ports

"""
This script does ranging with a prespecified neighbour.
"""
ports = find_uwb_serial_ports()

if len(ports) > 0:
    uwb1 = UwbModule(ports[0], verbose=True)
    counter = 0
    while True:
        range_data = uwb1.do_twr(target_id=6)
        print(range_data)
        print(counter)
        counter += 1

else:
    print("Did not detect a UWB device on this machine.")

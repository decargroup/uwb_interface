from pyuwb.uwbmodule import UwbModule, find_uwb_serial_ports
from itertools import combinations
""" 
These tests require a minimum of two modules physically connected
to the computer.
"""

def test_find_ports():
    ports = find_uwb_serial_ports()
    assert(len(ports) > 0)
    for port in ports:
        uwb = UwbModule(port)
        data = uwb.get_id()
        assert data["is_valid"]

def test_twr():
    ports = find_uwb_serial_ports()
    modules = [UwbModule(port) for port in ports]
    for (uwb1, uwb2) in combinations(modules, 2):
        range_data = uwb1.do_twr(target_id = uwb2.get_id())
        assert range_data["is_valid"]


if __name__ == "__main__":
    test_twr()

from pyuwb.uwbmodule import UwbModule, find_uwb_serial_ports
from itertools import combinations
import pytest
from time import sleep

""" 
These tests require a minimum of two modules physically connected
to the computer.
"""

ports = find_uwb_serial_ports()
modules = [UwbModule(port, verbose=True) for port in ports]


def test_get_id():
    for uwb in modules:
        data = uwb.get_id()
        assert data["is_valid"]


def test_twr():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    for (uwb1, uwb2) in combinations(modules, 2):
        neighbor_id = uwb2.get_id()["id"]
        range_data = uwb1.do_twr(target_id=neighbor_id)
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]


def test_twr_meas_at_target():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    uwb1 = modules[0]
    uwb2 = modules[1]
    neighbor_id = uwb2.get_id()["id"]
    range_data = uwb1.do_twr(target_id=neighbor_id, meas_at_target=True)
    assert range_data["range"] != 0.0
    assert range_data["is_valid"]


class DummyCallbackTracker(object):
    def __init__(self):
        self.num_called = 0

    def dummy_callback(self, *args):
        self.num_called += 1


def test_twr_callback():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    uwb1 = modules[0]
    uwb1.verbose = False
    uwb2 = modules[1]
    neighbor_id = uwb2.get_id()["id"]
    tracker = DummyCallbackTracker()
    uwb2.register_callback("R05", tracker.dummy_callback)

    # TODO: message prefixes are not meant to be user-facing
    N = 10
    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=False
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 10

def test_mult_twr_callback():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    uwb1 = modules[0]
    uwb1.verbose = False
    uwb2 = modules[1]
    neighbor_id = uwb2.get_id()["id"]
    tracker = DummyCallbackTracker()
    uwb2.register_callback("R05", tracker.dummy_callback)

    # TODO: message prefixes are not meant to be user-facing
    N = 10
    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=True
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 10


def test_get_max_frame_len():
    for uwb in modules:
        data = uwb.get_max_frame_length()
        print(data)
        assert data["is_valid"]

if __name__ == "__main__":
    test_get_max_frame_len()

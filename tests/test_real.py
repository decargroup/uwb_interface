from random import random
from pyuwb.uwbmodule import UwbModule, find_uwb_serial_ports
from itertools import combinations
import pytest
from time import sleep
import msgpack
""" 
These tests require a minimum of two modules physically connected
to the computer.
"""

ports = find_uwb_serial_ports()
modules = [UwbModule(port, verbose=True) for port in ports]


def test_get_id():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

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

def test_power():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    for (uwb1, uwb2) in combinations(modules, 2):
        neighbor_id = uwb2.get_id()["id"]
        range_data = uwb1.do_twr(target_id=neighbor_id, only_range=False)
        assert range_data["Pr1"] != 0.0
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
    uwb2.register_callback("S05", tracker.dummy_callback)

    # TODO: message prefixes are not meant to be user-facing
    N = 10
    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=False
        )
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == N


def test_mult_twr_callback():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    uwb1 = modules[0]
    uwb1.verbose = False
    uwb2 = modules[1]
    neighbor_id = uwb2.get_id()["id"]
    tracker = DummyCallbackTracker()
    uwb2.register_callback("S05", tracker.dummy_callback)

    # TODO: message prefixes are not meant to be user-facing
    N = 10
    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=True
        )
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == N

def test_passive_listening():
    if len(modules) < 3:
        pytest.skip("At least three modules need to be connected.")

    uwb1 = modules[0]
    uwb1.verbose = False
    uwb2 = modules[1]
    uwb3 = modules[2]
    neighbor_id = uwb2.get_id()["id"]
    tracker = DummyCallbackTracker()
    uwb3.register_callback("S01", tracker.dummy_callback)

    uwb3.toggle_passive(toggle=True)
    sleep(0.1)

    N = 5
    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=True
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == N

    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=False, mult_twr=True
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 2*N

    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, mult_twr=False
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 3*N

    for i in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=False, mult_twr=False
        )

        assert range_data["is_valid"]
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 4*N


def test_get_max_frame_len():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.get_max_frame_length()
        print(data)
        assert data["is_valid"]


def test_firmware_tests():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.do_tests()
        assert data["is_valid"]
        assert data["parsing_test"] == True


class MessageTracker:
    def callback(self, msg):
        self.msg = msg


def test_broadcast():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [MessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_callback("S06",trackers[i].callback)

    test_msg = b'test\0\r\n|message'
    modules[0].broadcast(test_msg)
    sleep(0.2)

    for tracker in trackers:
        assert tracker.msg[1:] == test_msg

def test_broadcast_msgpack():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [MessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_callback("S06",trackers[i].callback)

    test_msg = {
    "t": 3.14159,
    "x":[1,2,3],
    "P":[[1,0,0],[0,1,0],[0,0,1]],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    sleep(0.1)
    for tracker in trackers:
        assert msgpack.unpackb(tracker.msg[1:]) == test_msg



class LongMessageTracker:
    def callback(self, msg, is_valid):
        self.msg = msg

def test_message_callback():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [LongMessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_message_callback(trackers[i].callback)

    test_msg = {
    "t": 3.14159,
    "x":[1,2,3],
    "P":[[1,0,0],[0,1,0],[0,0,1]],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    sleep(0.1)
    for tracker in trackers:
        assert msgpack.unpackb(tracker.msg) == test_msg


def test_long_message():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [LongMessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_message_callback(trackers[i].callback)


    test_msg = {
    "t": 3.14159,
    "x":[1.0]*15,
    "P":[[random()]*i for i in range(1,15+1)],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    sleep(0.1)
    for tracker in trackers:
        assert msgpack.unpackb(tracker.msg) == test_msg


if __name__ == "__main__":
    test_long_message()

from random import random
from pyuwb.uwbmodule import UwbModule, find_uwb_serial_ports
import itertools
import pytest
from time import sleep
import msgpack

""" 
Most of these tests require a minimum of two modules physically
connected to the computer, with some requiring three.
"""

ports = find_uwb_serial_ports()
modules = [UwbModule(port, verbose=True) for port in ports]


def test_get_id():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.get_id()
        assert data["is_valid"]


def test_firmware_tests():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.do_tests()
        assert data["is_valid"]
        assert data["parsing_test"] == True


def test_twr():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=False,
            ds_twr=False,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=True,
            ds_twr=False,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=False,
            ds_twr=True,
            get_cir=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]


    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=True,
            ds_twr=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]


def test_twr_w_cir():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=False,
            ds_twr=False,
            get_cir=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=True,
            ds_twr=False,
            get_cir=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=False,
            ds_twr=True,
            get_cir=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]

    for (uwb1, uwb2) in itertools.permutations(modules, 2):
        sleep(0.01)
        neighbor_id = uwb2.get_id()["id"]
        sleep(0.01)
        range_data = uwb1.do_twr(
            target_id=neighbor_id,
            meas_at_target=True,
            ds_twr=True,
            get_cir=True,
        )
        assert range_data["neighbour"] == neighbor_id
        assert range_data["range"] != 0.0
        assert range_data["tx1"] != 0.0
        assert range_data["fpp1"] != 0.0
        assert range_data["skew1"] != 0.0
        assert range_data["is_valid"]


def test_get_max_frame_len():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.get_max_frame_length()
        print(data)
        assert data["is_valid"]


def test_set_response_delay():
    if len(modules) < 1:
        pytest.skip("At least one module needs to be connected.")

    for uwb in modules:
        data = uwb.set_response_delay()
        assert data


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
            target_id=neighbor_id, meas_at_target=True, ds_twr=False
        )
        assert range_data["is_valid"]
        uwb2.wait_for_messages()
    sleep(0.1)
    assert tracker.num_called == N


def test_ds_twr_callback():
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
            target_id=neighbor_id, meas_at_target=True, ds_twr=True
        )
        assert range_data["is_valid"]
        uwb2.wait_for_messages()
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
    uwb3.register_listening_callback(tracker.dummy_callback)

    uwb3.set_passive_listening()
    sleep(0.1)

    N = 5
    for _ in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, ds_twr=True
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        uwb3.wait_for_messages()
    sleep(0.1)
    assert tracker.num_called == N

    for _ in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=False, ds_twr=True
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        uwb3.wait_for_messages()
    sleep(0.1)
    assert tracker.num_called == 2 * N

    for _ in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=True, ds_twr=False
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        uwb3.wait_for_messages()
        sleep(0.01)
    sleep(0.1)
    assert tracker.num_called == 3 * N

    for _ in range(N):
        range_data = uwb1.do_twr(
            target_id=neighbor_id, meas_at_target=False, ds_twr=False
        )
        assert range_data["range"] != 0.0
        assert range_data["is_valid"]
        uwb3.wait_for_messages()
    sleep(0.1)
    assert tracker.num_called == 4 * N


def test_cir_callback():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    uwb1 = modules[0]
    uwb1.verbose = False
    uwb2 = modules[1]
    neighbor_id = uwb2.get_id()["id"]
    tracker = DummyCallbackTracker()
    uwb2.register_callback("S10", tracker.dummy_callback)

    range_data = uwb1.do_twr(
        target_id=neighbor_id, 
        meas_at_target=True, 
        ds_twr=True,
        get_cir=True,
    )
    assert range_data["is_valid"]
    uwb2.wait_for_messages()
    sleep(0.1)
    assert tracker.num_called == 1


class MessageTracker:
    def callback(self, msg, is_valid):
        self.msg = msg


def test_broadcast():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [MessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_message_callback(trackers[i].callback)

    test_msg = b"test\0\r\n|message"
    modules[0].broadcast(test_msg)
    
    for i, uwb in enumerate(modules[1:]):
        uwb.wait_for_messages()

    for tracker in trackers:
        assert tracker.msg == test_msg


def test_broadcast_msgpack():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    trackers = [MessageTracker() for uwb in modules[1:]]

    for i, uwb in enumerate(modules[1:]):
        uwb.register_message_callback(trackers[i].callback)

    test_msg = {
        "t": 3.14159,
        "x": [1, 2, 3],
        "P": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    
    for i, uwb in enumerate(modules[1:]):
        uwb.wait_for_messages()

    for tracker in trackers:
        assert msgpack.unpackb(tracker.msg) == test_msg


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
        "x": [1, 2, 3],
        "P": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    
    for i, uwb in enumerate(modules[1:]):
        uwb.wait_for_messages()

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
        "x": [1.0] * 15,
        "P": [[random()] * i for i in range(1, 15 + 1)],
    }
    data = msgpack.packb(test_msg)
    modules[0].broadcast(data)
    
    for i, uwb in enumerate(modules[1:]):
        uwb.wait_for_messages()

    for tracker in trackers:
        assert msgpack.unpackb(tracker.msg) == test_msg


def test_discovery():
    if len(modules) < 2:
        pytest.skip("At least two modules need to be connected.")

    # Get actual IDs of boards connected to this comp
    tag_ids = [uwb.get_id()["id"] for uwb in modules]

    for j, uwb in enumerate(modules):
        my_id = tag_ids[j]
        neighbor_ids = [i for i in tag_ids if i != my_id]
        neighbor_ids.sort()
        discovered_ids = uwb.do_discovery()

        assert set(neighbor_ids) <= set(discovered_ids)


if __name__ == "__main__":
    test_twr()

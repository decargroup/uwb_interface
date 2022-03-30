import os, pty
import sys
from time import sleep

sys.path.append(os.path.dirname(sys.path[0]))
from pyuwb.uwbmodule import UwbModule

# device, client = pty.openpty()
# port = os.ttyname(client)


def test_open():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port)


def test_write():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port)
    my_string = "Hello to the uwb device"
    uwb._send(my_string)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == my_string


def test_read():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1)
    my_string = "I'm a virtual uwb device"
    os.write(device, my_string.encode(uwb._encoding))
    out = uwb._read()
    print(out)


def test_monitor_thread():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=0.1, verbose=True)
    my_string = "I'm a virtual uwb device\n"
    os.write(device, my_string.encode(uwb._encoding))
    sleep(1)


def test_get_id():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R01|4\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C01\r"
    assert response["id"] == 4
    assert response["is_valid"] == True


def test_get_id_err1():
    """
    Get ID when a different response is returned.
    """
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=10, verbose=True)
    test_string = "R02\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    assert response["id"] == -1
    assert response["is_valid"] is False


def test_get_id_err2():
    """
    Get ID when response is of incorrect format
    """
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=10, verbose=True)
    test_string = "R01\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    assert response["id"] is None


def test_get_id_multiple_response():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R05|0\r\nR01|32\r\nR00\r\nR02|1\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C01\r"
    assert response["id"] == 32
    assert response["is_valid"] == True

def test_get_max_frame_length():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R07|100\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_max_frame_length()
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C07\r"
    assert response["length"] == 100
    assert response["is_valid"] == True

def test_do_twr():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R05|1|3.14159|0|0|0|0|0|0\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.do_twr(target_id=1)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C05|1|0|0\r"
    assert response["range"] == 3.14159
    assert response["is_valid"] == True


def test_twr_err1():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R05|3.14159abc\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.do_twr(target_id=1)
    assert response["range"] == 0.0
    assert response["is_valid"] == False


"""
For the callback tests, we must define a dummy callback, which just sets a flag
confirming that it was called. Since the callback is called in a seperate thread
we use a global variable to communicate this flag value between the callback
thread and the main thread.
"""

entered_cb1 = False


def cb_range1(*args):
    global entered_cb1
    entered_cb1 = True


def test_twr_callback():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    uwb.register_callback("R05", cb_range1)
    test_string = "R05|1|3.14159|0|0|0|0|0|0\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    sleep(0.1)
    assert entered_cb1 == True


entered_cb2 = False


def cb_range2(*args):
    global entered_cb2
    entered_cb2 = True


def test_twr_callback_unregister():
    device, client = pty.openpty()
    port = os.ttyname(client)
    uwb = UwbModule(port, timeout=1, verbose=True)
    uwb.register_callback("R05", cb_range2)
    uwb.unregister_callback("R05", cb_range2)
    test_string = "R05|3.14159\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    sleep(0.1)
    assert entered_cb2 == False


if __name__ == "__main__":
    test_twr_callback()

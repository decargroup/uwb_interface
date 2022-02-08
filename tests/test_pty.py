import os, pty
import sys
from time import sleep

sys.path.append(os.path.dirname(sys.path[0]))
from pyuwb.uwbmodule import UwbModule

device, client = pty.openpty()
port = os.ttyname(client)


def test_open():
    uwb = UwbModule(port)


def test_write():
    uwb = UwbModule(port)
    my_string = "Hello to the uwb device"
    uwb._send(my_string)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == my_string


def test_read():
    uwb = UwbModule(port, timeout=1)
    my_string = "I'm a virtual uwb device"
    os.write(device, my_string.encode(uwb._encoding))
    out = uwb._read()
    print(out)

def test_monitor_thread():
    uwb = UwbModule(port, timeout=0.1, verbose= True)
    my_string = "I'm a virtual uwb device\n"
    os.write(device, my_string.encode(uwb._encoding))
    sleep(1)

def test_get_id():
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R01,4\r\n"
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
    uwb = UwbModule(port, timeout=10, verbose=True)
    test_string = "R02\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    assert response["id"] == None
    assert response["is_valid"] is False

def test_get_id_err2():
    """
    Get ID when response is of incorrect format
    """
    uwb = UwbModule(port, timeout=10, verbose=True)
    test_string = "R01\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    assert response["id"] is None

def test_get_id_multiple_response():
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R05,0\r\nR01,32\r\nR00\r\nR02,1\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C01\r"
    assert response["id"] == 32
    assert response["is_valid"] == True


def test_do_twr():
    uwb = UwbModule(port, timeout=1, verbose=True)
    test_string = "R05,3.14159\r\n"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.do_twr(target_id=1)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C05,1,0\r"
    assert response["range"] == 3.14159
    assert response["is_valid"] == True


if __name__ == "__main__":
    test_get_id_multiple_response()

import os, pty, serial
import sys
sys.path.append(os.path.dirname(sys.path[0]))
from pyuwb.uwbmodule import UwbModule

device, client = pty.openpty()
port = os.ttyname(client)

def test_open():
    uwb = UwbModule(port)
    temp =1

def test_write():
    uwb = UwbModule(port)
    my_string = "Hello to the uwb device"
    uwb._send(my_string)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == my_string

def test_read():
    uwb = UwbModule(port, timeout = 1)
    my_string = "I'm a virtual uwb device"
    os.write(device, my_string.encode(uwb._encoding))
    out = uwb._read()
    print(out)

def test_get_id():
    uwb = UwbModule(port, timeout = 1)
    test_string = "R01,4\r"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.get_id()
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C01\r"
    assert response["id"] == 4

def test_do_twr():
    uwb = UwbModule(port, timeout = 1)
    test_string = "R02,3.14159\r"
    os.write(device, test_string.encode(uwb._encoding))
    response = uwb.do_twr(target_id=1)
    out = os.read(device, 1000)
    assert out.decode(uwb._encoding) == "C02,1\r"
    assert response["range"] == 3.14159


if __name__ == "__main__":
    test_get_id()
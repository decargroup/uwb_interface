# Python Interface to the MRASL/DECAR UWB Modules

This python package provides a basic API to UWB modules, allowing a user to initiate and collect ranging data between devices, as well as data transfer and broadcast capabilities between UWB devices.

# Installation
Installation
To install, cd into the repository directory (the one with setup.py) and run:

    pip install .
or

    pip install -e .

The -e flag tells pip to install the package in-place, which lets you make changes to the code without having to reinstall every time. Do not do this on shared workstations!

```python
from pyuwb import UwbModule
uwb = UwbModule("/dev/ttyUSB0")
uwb.broadcast("Hello EVERYONE!")
```

## Our USB serial message format
We adopt a command/response (or request/response) style where the PC (referred to as the client) sends command messages over USB to the UWB module, which then performs some function and returns a response. 

Depending on the command, the actual message that is ultimately sent as a sequence of bytes, will differ in structure. Hence, for each difference command, there exists a predefined __message format specifier__. An example is 

    C99 "sfi" 

This says that command #99 will have a string field, followed by a float field, followed by an integer field, __all seperated by semicolons__ (entry 69/3B in the ASCII table). All messages are prefixed by the message ID, and terminated by `"\r"`. This lets the receiver know the message format. An example corresponding to the above is

    "C99;hello;3.1415+00;420\r"

If an empty response is expected, the message specifier would be `R99 ""`, and a message would look like

    "R99\r"

An empty response is essentially just an acknowledgement that the message was received and things are operating normally. The field type specifiers used are those from the following table:
https://docs.python.org/3/library/struct.html#format-characters





|# | Example: Python | Example: message| Example: response|
|--|--------|---------------------|------------------|
|C00| `uwb.set_idle()`| `"C00\r"` | `"R00\r"` |
|C01| `uwb.get_id()`| `"C01\r"`|`"R01,3\r"`
|C02| `range_data = uwb.do_ranging(destination_id = 1)`| `"C02,1\r"`| `"R02,1.2345,98.1\r"`
|
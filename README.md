# Python Interface to the MRASL/DECAR UWB Modules

This python package provides a basic API to UWB modules, allowing a user to initiate and collect ranging data between devices, as well as data transfer and broadcast capabilities between UWB devices.

## Installation
Inside this repo's directory, you may run

    pip install .
or

    pip install -e .

which installs the package in-place, allowing you make changes to the code without having to reinstall every time. 


## Minimal Working Example
```python
from pyuwb import UwbModule
uwb = UwbModule("/dev/ttyUSB0")
range_data = uwb.do_twr(target_id=5)
print(range_data["range"])
```

## Our USB serial message format
We adopt a command/response (or request/response) style where the PC (referred to as the client) sends command messages over USB to the UWB module, which then performs some function and returns a response. 

Depending on the command, the actual message that is ultimately sent as a sequence of bytes, will differ in structure. Hence, for each difference command, there exists a predefined __message format specifier__. An example is 

    C99 "string,float,int" 

This says that command #99 will have a string field, followed by a float field, followed by an integer field, __all seperated by commas__. All messages are prefixed by the message ID, and terminated by `"\r"`. This lets the receiver know the message format. An example corresponding to the above is

    "C99,hello,1.123456,44\r"

If an empty response is expected, the message specifier would be `R99 ""`, and a message would look like

    "R99\r"

An empty response is essentially just an acknowledgement that the message was received and things are operating normally. The field type specifiers used are those from the following table:
https://docs.python.org/3/library/struct.html#format-characters


## Current list of commands


|# | Example: Python | Example: message| Example: response|
|--|--------|---------------------|------------------|
|C00| `uwb.set_idle()`| `"C00\r"` | `"R00\r"` |
|C01| `uwb.get_id()`| `"C01\r"`|`"R01,3\r"`
|C02| `uwb.reset()`| `"C02\r"`| `"R02\r"`
|C03| `uwb.do_tests()`| `"C03\r"`| `"R03,1\r"`
|C04| `uwb.toggle_passive(toggle = 1)`| `"C04,1\r"`| `"R04\r"`
|C05| `range_data = uwb.do_twr(target_id = 1)`| `"C02,1\r"`| `"R02,1.2345\r"`
|
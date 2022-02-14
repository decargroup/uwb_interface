# Python Interface to the MRASL/DECAR UWB Modules

This python package provides a basic API to UWB modules, allowing a user to initiate and collect ranging data between devices, as well as data transfer and broadcast capabilities between UWB devices.

## Installation
Python 3.6 or greater is required. Inside this repo's directory, you may run

    pip3 install .
or

    pip3 install -e .

which installs the package in-place, allowing you make changes to the code without having to reinstall every time. 

TODO: we could make this python2 compatible by removing the type annotations. This is not needed right now.

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
|C05| `range_data = uwb.do_twr(target_id = 1)`| `"C05,1\r"`| `"R05,1.2345\r"`
|


## How it works internally
This interface is designed to allow a user to execute functions in the firmware by sending messages over USB. However, a second key feature is the ability to register callbacks, such that the UWB module firmware can send a "spontaneous" message without being commanded to do so, which can then be sent to a callback so the user can do what they want with the data. For these two features to coexist simultaneously, we had to divide the backend into three seperate threads. Three threads (which includes the main starting thread) are created a user creates a `UwbModule()` instance.

### Thread 1: Main Thread
This is the same thread in which `UwbModule()` was instantiated, as well as where user-triggered commands such as `uwb.get_id()` are called.

### Thread 2: Serial monitor
This is a thread that is constantly reading the USB serial output for messages from the firmware. It searches for recognized message prefixes such as `R01`. If one is detected, the message is parsed and the message fields are converted to their corresponding types. The parsed results and then sent to two places:

1. A dictionary that holds the latest values for any specific message prefix. This is so that functions from the main thread can come collect their responses. 

2. Added to a message queue, which is used to trigger callbacks as described by the next thread.

### Thread 3: Callback dispatcher
This thread continuously monitors the message queue described above, looping through any messages in the queue, executing callbacks registered for that message prefix. Hence, when a user experiences a callback call, it is inside a different thread (this one) than the main thread. Thread 3 and Thread 1 are user-facing threads, whereas Thread 2 is strictly internal. The reason Thread 3 and Thread 2 weren't merged into one thread was becaused callbacks could potentially taking a very long time to execute, which would block the serial reading. This way, the serial monitor can continue to operate even if a very long callback is running.
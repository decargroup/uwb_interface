# Python Interface to the MRASL/DECAR UWB Modules

This python package provides a basic API to UWB modules, allowing a user to initiate and collect ranging data between devices, as well as data transfer and broadcast capabilities between UWB devices.

## A simple example
```python 
from pyuwb import UwbModule

# Find all ports with a UWB module connected
ports = find_uwb_serial_ports()

# Create two UwbModule instances 
uwb0 = UwbModule(ports[0], verbose=True)
uwb1 = UwbModule(ports[0], verbose=True)

# Get the ID of each module
id0 = uwb0.get_id()
id1 = uwb1.get_id()

# Do a ranging transaction between the two modules
range_data = uwb0.do_twr(target_id = id1["id"]])

# Print the range measurement
print(range_data["range"])
```

## Installation

Python 3.6 or greater is required. Clone this repo, and Iinside this repo's directory, execute 

    pip3 install -e .

to install the package in-place, allowing you make changes to the code without having to reinstall every time.

This repository assumes that the UWB modules are running the firmware from our package `uwb_firmware`, which can be found [here](https://github.com/shalabyma/uwb_firmware.git).

## The USB serial message format
We adopt a command/response (or request/response) style where the PC (referred to as the client) sends command messages over USB to the UWB module, which then performs some function and returns a response. 

Depending on the command, the actual message that is ultimately sent as a sequence of bytes, will differ in structure. Hence, for each different command, there exists a predefined __message format specifier__. An example is 

    C99 "string,float,int" 

This says that command #99 will have a string field, followed by a float field, followed by an integer field, __all separated by commas__. All messages are prefixed by the message ID, and terminated by `"\r"`. This lets the receiver know the message format. An example corresponding to the above is

    "C99,hello,1.123456,44\r"

If an empty response is expected, the message specifier would be `R99 ""`, and a response would look like

    "R99\r"

An empty response is essentially just an acknowledgement that the message was received and things are operating normally. The field type specifiers used are those from the following table:
https://docs.python.org/3/library/struct.html#format-characters. 


## Current list of commands

Note that all commands and responses are signed with a `Cxx` and `Rxx` prefix, respectively. The `xx` is the message ID, which is a two-digit number. A response to a specific command will have the same message ID as the command.

|# | Python | Message| Response | Description|
|--|--------|---------------------|------------------|-----------|
|C00| `uwb.set_idle()`| `"C00\r"` | `"R00\r"` | Set the UWB module to idle mode
|C01| `uwb.get_id()`| `"C01\r"`|`"R01,3\r"` | Get the ID of the UWB module
|C02| `uwb.reset()`| `"C02\r"`| `"R02\r"` | Reset the UWB module
|C03| `uwb.do_tests()`| `"C03\r"`| `"R03,1\r"` | Run a series of tests
|C04| `uwb.toggle_passive(toggle = 1)`| `"C04,1\r"`| `"R04\r"` | Toggle passive listening mode
|C05| `uwb.do_twr(target_id = 1)`| `"C05,1\r"`| `"R05,1.2345\r"` | Initiate a TWR transaction
|C06| `uwb.broadcast(b"example")`| `"C06,example\r"`| `"R06\r"` | Broadcast a message
|C07| `uwb.get_max_frame_length()`| `"C07\r"`| `"R07,100\r"`| Get max frame length
|C08| `uwb.set_response_delay(delay=1500)`| `"C08,1500\r"`| `"R08\r"`| Set delay for 2nd response in DS-TWR

The above table shows a sample of the most basic functionality. Many of these commands have additional optional arguments that can be passed to customize the behavior for a wide variety of applications, and these arguments can modify the form of the message and response.

## Callbacks and spontaneous messages

In addition to the command/response style, the UWB module firmware can also send spontaneous messages to the PC without being commanded to do so. These messages are signed with a `Sxx` prefix. To handle these messages, we have a callback system, where a user can register a callback function to be called whenever a message with a specific message ID is received. The callback function will be called with the message fields as arguments. 


## How it works internally

This interface is designed to allow a user to execute functions in the firmware by sending messages over USB. However, a second key feature is the ability to register callbacks, such that the UWB module firmware can send a "spontaneous" message without being commanded to do so, which can then be sent to a callback so the user can do what they want with the data. For these two features to coexist simultaneously, we had to divide the backend into three seperate threads. Three threads (which includes the main starting thread) are created a user creates a `UwbModule()` instance.

### Thread 1: Main Thread
This is the same thread in which `UwbModule()` was instantiated, as well as where user-triggered commands such as `uwb.get_id()` are called.

### Thread 2: Serial monitor
This is a thread that is constantly reading the USB serial output for messages from the firmware. It searches for recognized message prefixes such as `R01`. If one is detected, the message is parsed and the message fields are converted to their corresponding types. The parsed results and then sent to two places:

1. A dictionary that holds the latest values for any specific message prefix. This is so that functions from the main thread can come collect their responses. 

2. Added to a message queue, which is used to trigger callbacks as described by the next thread.

### Thread 3: Callback dispatcher
This thread continuously monitors the message queue described above, looping through any messages in the queue, executing callbacks registered for that message prefix. Hence, when a user experiences a callback call, it is inside a different thread (this one) than the main thread. Thread 3 and Thread 1 are user-facing threads, whereas Thread 2 is strictly internal. The reason Thread 3 and Thread 2 weren't merged into one thread was because callbacks could potentially taking a very long time to execute, which would block the serial reading. This way, the serial monitor can continue to operate even if a very long callback is running.
import struct
import serial
from serial.tools import list_ports
from time import sleep
from datetime import datetime
import threading
import queue
import msgpack
import traceback
from typing import List
from .packing import (
    Packer,
    IntField,
    BoolField,
    StringField,
    FloatField,
    ByteField,
)


def find_uwb_serial_ports():
    """
    Automatically detects UWB modules connected to this computer via USB.

    RETURNS:
    --------
    list[port path: string]:
        list of paths to the serial ports that have a UWB device
    """
    ports = list_ports.comports()
    uwb_ports = []
    for port in ports:
        uwb = UwbModule(port.device, baudrate=19200, timeout=1, verbose=True)
        id_dict = uwb.get_id()
        if id_dict["is_valid"]:
            uwb_ports.append(port.device)
        uwb.close()
    sleep(1)
    return uwb_ports


class UwbModule(object):
    """
    Main interface object for DECAR/MRASL UWB modules.

    PARAMETERS:
    -----------
    port: str
        path to port that the UWB device is connected to
    baudrate: int
        baudrate for the serial connection with the UWB module
    timeout: float
        max amount of time, in seconds, to wait for a response to commands
    verbose: bool
        if set to true, full serial output will be printed.
    log: bool
        TODO: get rid of logging?
    threaded: bool
        if true, initializes this module in a multi-threaded mode with  
        serial port monitoring and callback execution executing in other threads.
    """

    _encoding = "utf-8"
    _c_format_dict = {
        "C00": [],
        "C01": [],
        "C02": [],
        "C03": [IntField, StringField, BoolField, FloatField, ByteField],
        "C04": [BoolField],
        "C05": [IntField, BoolField, BoolField],
        "C06": [ByteField],
        "C07": [],
    }
    _r_format_dict = {
        "R00": [],
        "R01": [IntField],
        "R02": [],
        "R03": [
            IntField,
            IntField,
            StringField,
            BoolField,
            FloatField,
            ByteField,
        ],
        "R04": [],
        "R05": [IntField, FloatField] + [IntField] * 6 + [FloatField] * 2,
        "R06": [],
        "R07": [IntField],
        "S01": [IntField] * 11 + [FloatField] * 5,
        "S05": [IntField, FloatField] + [IntField] * 6 + [FloatField] * 2,
        "S06": [ByteField],
    }

    def __init__(
        self,
        port,
        baudrate=19200,
        timeout=0.1,
        verbose=False,
        log=False,
        threaded=False,
    ):
        """
        Constructor
        """
        self.device = serial.Serial(port, baudrate=baudrate, timeout=0.1)
        self.verbose = verbose
        self.timeout = timeout
        self.logging = log

        self._r_format_dict = {
            key.encode(self._encoding): val
            for key, val in self._r_format_dict.items()
        }
        self._c_format_dict = {
            key.encode(self._encoding): val
            for key, val in self._c_format_dict.items()
        }
        self.packer = Packer(separator="|", terminator="\r")

        # Logging
        self._log_filename = None

        # Messaging internal variables.
        self._max_frame_len = None
        self._receivers = {}
        self._response_container = {}
        self._callbacks = {}

        # Start a separate thread for serial port monitoring
        self._threaded = threaded
        if self._threaded:
            self._kill_monitor = False
            self._msg_queue = queue.Queue()
            self._response_condition = threading.Condition()
            self._main_thread = threading.main_thread()

            self._monitor_thread = threading.Thread(
                target=self._serial_monitor, name="Serial Monitor"
            )

            self._dispatcher_thread = threading.Thread(
                target=self._cb_dispatcher, name="Callback Dispatcher"
            )

            self._monitor_thread.start()
            self._dispatcher_thread.start()
        else: 
            self._msg_queue = []

    def _serial_monitor(self):
        """
        SERIAL MONITOR THREAD

        Continuously monitors the serial port, watching for official messages.
        If an official message is detected, it is extracted and stored in a queue.
        """
        time_to_exit = False
        while True:

            if self._kill_monitor or not self._main_thread.is_alive():
                # Why not just put this condition in the while loop condition?
                # Because this way, we will read the serial and process
                # messages one last time before exiting.
                time_to_exit = True

            self._read_and_unpack()

            if time_to_exit:
                self._msg_queue.put(None)  # Signals CB dispatcher to exit.
                break  # Exits this thread.

    def _cb_dispatcher(self):
        """
        CALLBACK DISPATCHER THREAD

        Thread which executes callbacks by watching a queue of messages received
        from the firmware.

        This thread will shutdown when it receives a 'None' on the queue.
        """
        while True:
            # Waits
            msg = self._msg_queue.get()
            if msg is None:
                break  # Shut down the thread.
            else:
                msg_key, field_values = msg
                self._execute_callbacks(msg_key, field_values)

                

    def _send(self, message: bytes):
        """
        Send an arbitrary string to the UWB device.
        """
        if isinstance(message, str):
            message = message.encode(
                self._encoding
            )  

        if self.verbose:
            print("<< ", end="")
            print(str(message)[2:-1])

        self.device.write(message)

    def _read(self) -> bytes:
        """
        Read arbitrary string from UWB device.
        """
        # Here we use pyserial's readline() command to take advantage of the
        # built-in timeout feature. This lets us wait a bit for messages to
        # arrive over USB. However, once we do recieve a message, we immediately
        # call read(device.in_waiting) to also read whatever else is in the
        # input buffer.
        out = self.device.read_until(b"\r\n")
        out += self.device.read(self.device.in_waiting)

        if self.verbose and len(out) > 0:
            print(">> ", end="")
            print(str(out)[2:-1])
        return out

    def _read_and_unpack(self):

        # This line may block for a short timeout using pyserial's
        # timeout functionality. 
        out = self._read()

        if len(out) > 0:

            # Temporary variable will act as buffer that is progressively
            # "consumed" as the message is processed left-to-right.
            temp = out
            while len(temp) >= 4:

                # Find soonest of "R" or "S"
                next_r_idx = temp.find(b"R")
                next_s_idx = temp.find(b"S")
                if next_r_idx == -1 and next_s_idx == -1:
                    next_msg_idx = -1
                elif next_r_idx == -1:
                    next_msg_idx = next_s_idx
                elif next_s_idx == -1:
                    next_msg_idx = next_r_idx
                else:
                    next_msg_idx = min(next_r_idx, next_s_idx)

                if next_msg_idx == -1:
                    # No message start found, exit loop
                    break
                else:
                    # Go to next msg_idx
                    temp = temp[next_msg_idx:]

                    # Read first three characters, check if valid msg
                    msg_key = temp[0:3]
                    temp = temp[3:]
                    if msg_key in self._r_format_dict:
                        try:
                            field_values, end_idx = self.packer.unpack(
                                temp, self._r_format_dict[msg_key]
                            )

                            if self._threaded:
                                # Lock main thread while response is being parsed.
                                with self._response_condition:
                                    self._response_container[msg_key] = field_values

                                    # Signal to main thread that a response is
                                    # ready.
                                    self._response_condition.notify()

                                # Put messages on a queue for callbacks.
                                self._msg_queue.put((msg_key, field_values))
                            
                            else:
                                self._response_container[msg_key] = field_values

                                # Put messages on a queue for callbacks.
                                self._msg_queue.append((msg_key, field_values))

                            # Go to end of message.
                            temp = temp[end_idx + 1 :]
                        except Exception:
                            if self.verbose:
                                print("Message parsing error occured.")
                                print(traceback.format_exc())

    def _execute_callbacks(self, msg_key, field_values):
        # Check if any callbacks are registered for this specific msg
        if msg_key in self._callbacks.keys():
            cb_list = self._callbacks[msg_key]
            for cb, cb_args in cb_list:
                if cb_args is not None:
                    cb(field_values, cb_args)
                else:
                    cb(field_values)

    def _create_log_file(self):
        # Current date and time for logging
        temp = self.get_id()
        self.id = temp["id"]
        temp = datetime.now()
        now = temp.strftime("%d_%m_%Y_%H_%M_%S")
        self._log_filename = (
            "datasets/log_" + now + "_ID" + str(self.id) + ".txt"
        )

    def close(self):
        """
        Proper shutdown of this module. Note that even if the object does not
        exist anymore in the main thread, the two internal threads will
        continue to exist unless this method is called or the main thread exits.
        """

        self._kill_monitor = True

    def register_callback(self, msg_key: str, cb_function, callback_args=None):
        """
        Registers a callback function to be executed whenever a specific
        message key is received over serial.
        """
        msg_key = msg_key.encode(self._encoding)
        if msg_key in self._callbacks.keys():
            self._callbacks[msg_key].append((cb_function, callback_args))
        else:
            self._callbacks[msg_key] = [(cb_function, callback_args)]

    def unregister_callback(self, msg_key: str, cb_function):
        """
        Removes a callback function from the execution list corresponding to
        a specific message key.
        """
        msg_key = msg_key.encode(self._encoding)
        if msg_key in self._callbacks.keys():
            funcs = [x[0] for x in self._callbacks[msg_key]]
            if cb_function in funcs:
                idx = funcs.index(cb_function)
                self._callbacks[msg_key].pop(idx)
            else:
                print("This callback is not registered.")
        else:
            print("No callbacks registered for this key.")

    def output(self, data):
        """
        Outputs data by printing and saving to a log file.

        PARAMETERS:
        -----------
        data: Any
            data to be stored and printed
        """
        print(str(data))

        if self.logging is True:
            self.log(data)

    def log(self, data):
        """
        Logs data by saving to a log file.

        PARAMETERS:
        -----------
        data: Any
            data to be stored and printed
        """
        data = str(data)
        if self._log_filename is None:
            self._create_log_file()

        with open(self._log_filename, "a") as myfile:
            myfile.write(data + "\n")

    def wait_for_messages(self, timeout=None):
        """
        Check the serial port for any messages, parse them, 
        and then execute any callbacks registered to the parsed messages.
        This function will block for a max of `timeout` seconds. If left blank 
        or `timeout=None`, the default timeout will be used.
        """
        if not self._threaded:
            
            if timeout is None:
                timeout = self.timeout 

            old_timeout = self.timeout
            self.device.timeout = timeout 
            self._read_and_unpack()

            # Execute any callbacks.
            while len(self._msg_queue) > 0:
                msg_key, field_values = self._msg_queue.pop(0)
                self._execute_callbacks(msg_key, field_values)

            self.device.timeout = old_timeout


    ############################################################################
    ########################## COMMAND IMPLEMENTATIONS #########################
    ############################################################################
    def _execute_command(self, command_key: str, response_key: str, *args):
        command_key = command_key.encode(self._encoding)
        response_key = response_key.encode(self._encoding)
        msg = self.packer.pack(args, self._c_format_dict[command_key])
        msg = command_key + msg
        self._send(msg)

        if self._threaded:
            with self._response_condition:
                self._response_container[response_key] = None
                self._response_condition.wait(self.timeout)
                response = self._response_container[response_key]
        else:
            self._response_container[response_key] = None
            self._read_and_unpack()
            response = self._response_container[response_key]

            # Execute any callbacks.
            while len(self._msg_queue) > 0:
                msg_key, field_values = self._msg_queue.pop(0)
                self._execute_callbacks(msg_key, field_values)

        return response

    def set_idle(self):
        """
        Sets the module to be idle/inactive.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C00"
        rsp_key = "R00"
        response = self._execute_command(msg_key, rsp_key)
        if response is None:
            return False
        else:
            return True

    def get_id(self):
        """
        Gets the module's ID.

        RETURNS:
        --------
        dict with keys:
            "id": int
                board ID
            "is_valid": bool
                whether the reported result is valid or an error occurred
        """
        msg_key = "C01"
        rsp_key = "R01"
        response = self._execute_command(msg_key, rsp_key)
        if response is None:
            return {"id": None, "is_valid": False}
        else:
            self.id = response[0]
            return {"id": response[0], "is_valid": True}

    def reset(self):
        """
        Resets and re-enables the DW receiver.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C02"
        rsp_key = "R02"
        response = self._execute_command(msg_key, rsp_key)
        if response is None:
            return False
        else:
            return True

    def do_tests(self):
        """
        Performs pre-determined tests to identify any faults with the board.

        RETURNS:
        --------
        dict with fields:
            error_id: int
                ID associated with the error that occured.
            is_valid: bool
                whether the result is valid or some error occured
        """
        msg_key = "C03"
        rsp_key = "R03"

        test_dict = {"a": 3.14159, "b": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]}
        test_bytes = msgpack.packb(test_dict, use_single_float=True)
        test_fields = [
            12345,
            "the test string",
            True,
            1.2345,
            test_bytes,
        ]
        response = self._execute_command(msg_key, rsp_key, *test_fields)

        if response is None:
            return {
                "error_id": -1,
                "is_valid": False,
                "parsing_test": False,
            }
        else:
            if (
                test_fields[0] != response[1]
                or test_fields[1] != response[2]
                or test_fields[2] != response[3]
                or test_fields[3] != response[4]
                or test_fields[4] != response[5]
            ):
                firmware_parsing_error = False
            else:
                firmware_parsing_error = True
            return {
                "error_id": response[0],
                "is_valid": True,
                "parsing_test": firmware_parsing_error,
            }

    def toggle_passive(self, toggle=False):
        """
        Toggles the passive listening or "eavesdropping" feature.

        PARAMETERS:
        -----------
        toggle: bool
            flag to turn on or off passive listening

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C04"
        rsp_key = "R04"
        response = self._execute_command(msg_key, rsp_key, toggle)
        if response is None:
            return False
        else:
            return True

    def set_passive_listening(self, active=True):
        """
        Activiates/deactivates the passive listening or "eavesdropping" feature.

        PARAMETERS:
        -----------
        active: bool
            flag to turn on or off passive listening

        RETURNS:
        --------
        bool: successfully received response
        """
        return self.toggle_passive(active)

    def register_listening_callback(self, cb_function, callback_args=None):
        """
        Register a callback that will get called whenever a range message
        involving other tags is heard.
        """
        self.register_callback("S01", cb_function, callback_args)

    def unregister_listening_callback(self, cb_function):
        """
        Unregister a previously-registered listening callback.
        """
        self.unregister_callback("S01", cb_function)

    def do_twr(
        self,
        target_id=1,
        meas_at_target=False,
        mult_twr=False,
        only_range=False,
    ):
        """
        Performs Two-Way Ranging with a chosen target/destination tag.

        PARAMETERS:
        -----------
        target_id: int
            ID of the tag to range with
        meas_at_target: bool
            flag to have the range measurement also available at the target
        mult_twr: bool
            flag to indicate if the multiplicate TWR will be used
        only_range: bool
            flag indicate if only range measurements should be output.
            NOTE: Does not get passed to the modules.

        RETURNS:
        --------
        dict with fields:
            neighbour: int
                id of the neighbour
            range: float
                range measurement in meters
            is_valid: bool
                whether the result is valid or some error occured
            tx1: float
                timestamp of the transmission time of signal 1 in
                the initiator tag's clock
            rx1: float
                timestamp of the reception time of signal 1 in
                the target tag's clock
            tx2: float
                timestamp of the transmission time of signal 2 in
                the target tag's clock
            rx2: float
                timestamp of the reception time of signal 2 in
                the initiator tag's clock
            tx3: float
                timestamp of the transmission time of signal 3 in
                the target tag's clock
            rx3: float
                timestamp of the reception time of signal 3 in
                the initiator tag's clock
            Pr1: float
                the power at the target tag for the first signal
            Pr2: float
                the power at the initiator tag for the second signal
        """
        msg_key = "C05"
        rsp_key = "R05"
        response = self._execute_command(
            msg_key, rsp_key, target_id, meas_at_target, mult_twr
        )
        if response is None:
            return {"neighbour": 0.0, "range": 0.0, "is_valid": False}
        elif only_range is False:
            return {
                "neighbour": response[0],
                "range": response[1],
                "tx1": response[2],
                "rx1": response[3],
                "tx2": response[4],
                "rx2": response[5],
                "tx3": response[6],
                "rx3": response[7],
                "Pr1": response[8],
                "Pr2": response[9],
                "is_valid": True,
            }
        else:
            return {
                "neighbour": response[0],
                "range": response[1],
                "is_valid": True,
            }

    def register_range_callback(self, cb_function, callback_args=None):
        """
        Register a callback that gets executed whenever a module initiates
        ranging with this one.
        """
        self.register_callback("S05", cb_function, callback_args)

    def unregister_range_callback(self, cb_function):
        """
        Unregister a previously-registered ranging callback.
        """
        self.unregister_callback("S05", cb_function)

    def do_discovery(self, possible_ids: List[int] = None) -> List[int]:
        """
        Discovers tags that are within UWB range by trying to range with every
        single one.

        PARAMETERS
        ----------
        possible_ids (optional): IDs of the tags to try and range with

        RETURNS
        -------
        list: list of tag IDs found
        """

        if possible_ids is None:
            possible_ids = [i for i in range(0, 11)]

        discovered = []
        for test_id in possible_ids:
            response = self.do_twr(target_id=test_id)
            if response["is_valid"]:
                discovered.append(test_id)

        return discovered

    def get_max_frame_length(self):
        """
        Gets the module's ID.

        RETURNS:
        --------
        dict with keys:
            "length": int
                max frame length (in number of bytes) that the board is
                configured to send over UWB.
            "is_valid": bool
                whether the reported result is valid or an error occurred
        """
        msg_key = "C07"
        rsp_key = "R07"
        response = self._execute_command(msg_key, rsp_key)
        if response is False or response is None:
            return {"length": -1, "is_valid": False}
        else:
            self.id = response[0]
            return {"length": response[0], "is_valid": True}

    def broadcast(self, data: bytes):
        """
        Broadcast string of bytes data over UWB.

        RETURNS:
        --------
        bool: successfully sent
        """
        if not isinstance(data, bytes):
            raise RuntimeError("Data must be of bytes type.")

        if self._max_frame_len is None:
            len_data = self.get_max_frame_length()
            if len_data["is_valid"]:
                self._max_frame_len = len_data["length"]
            else:
                RuntimeError(
                    "Unable to detect the max supported UWB frame length."
                )

        msg_key = "C06"
        rsp_key = "R06"

        # add a small buffer to not hit max frame length exactly.
        frame_len = self._max_frame_len - 20
        num_msg = int(len(data) / frame_len) + 1
        frames = [
            data[i : i + frame_len] for i in range(0, len(data), frame_len)
        ]

        for i, frame in enumerate(frames):
            indexed_frame = struct.pack("<B", num_msg - i - 1) + frame
            response = self._execute_command(msg_key, rsp_key, indexed_frame)

        if response is None:
            return False
        else:
            return True

    def register_message_callback(self, cb_function):
        """
        Register a callback that gets called whenever a generic
        non-ranging message is sent to this module.
        """
        # TODO: add callback_args
        receiver = LongMessageReceiver(cb_function)
        self._receivers[id(cb_function)] = receiver
        self.register_callback("S06", receiver.frame_callback)

    def unregister_message_callback(self, cb_function):
        """
        Unregister a previously-registered messaging callback.
        """
        if not id(cb_function) in self._receivers.keys():
            print("This callback is not registered.")

        receiver = self._receivers[id(cb_function)]
        self.unregister_callback("S06", receiver.frame_callback)


class LongMessageReceiver:
    def __init__(self, cb_function) -> None:
        self._long_msg = b""
        self._cb_function = cb_function
        self._exp_frames_remaining = None

    def frame_callback(self, msg):
        msg = msg[0]
        frames_remaining = struct.unpack("<B", msg[0:1])[0]
        print("GOT THE FOLLOWING: " + str(frames_remaining))
        self._long_msg += msg[1:]

        is_valid = True
        if self._exp_frames_remaining is None:
            self._exp_frames_remaining = frames_remaining
        elif (self._exp_frames_remaining - 1) != frames_remaining:
            print("WARNING: A frame was missed in a frame sequence.")
            is_valid = False
        else:
            self._exp_frames_remaining = frames_remaining

        if frames_remaining == 0:
            self._cb_function(self._long_msg, is_valid)
            self._long_msg = b""
            self._exp_frames_remaining = None

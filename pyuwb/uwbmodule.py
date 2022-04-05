import serial
from serial.tools import list_ports
from time import time, sleep
from datetime import datetime
from threading import Thread
import msgpack
import traceback
from typing import List, Any
from .packing import Packer, IntField, BoolField, StringField, FloatField, ByteField

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
        uwb = UwbModule(port.device, baudrate=19200, timeout=1)
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

    """

    _encoding = "utf-8"
    _c_format_dict = {
        "C00": [],
        "C01": [],
        "C02": [],
        "C03": [IntField, StringField, BoolField, FloatField, ByteField],
        "C04": [BoolField],
        "C05": [IntField, BoolField, BoolField],
        "C06": [StringField],
        "C07": [],
    }
    _r_format_dict = {
        "R00": [],
        "R01": [IntField],
        "R02": [],
        "R03": [IntField, IntField, StringField, BoolField, FloatField, ByteField], 
        "R04": [],
        "R05": [IntField] + [FloatField]*7,
        "R06": [StringField],
        "R07": [IntField],
        "R99": [FloatField]*4,
    }
    _format_dict = {**_c_format_dict, **_r_format_dict}  # merge both dicts
    # _sep = "|"
    # _sep_encoded = _sep.encode(_encoding)
    # _eol = "\r"
    # _eol_encoded = _eol.encode(_encoding)

    def __init__(
        self, port, baudrate=19200, timeout=0.1, verbose=False, log=False
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
        self._format_dict = {
            key.encode(self._encoding): val
            for key, val in self._format_dict.items()
        }
        self.packer = Packer(seperator='|', terminator='\r')


        # Start a seperate thread for serial port monitoring
        self._kill_monitor = False
        self._msg_queue = []
        self._callbacks = {}
        self._response_container = {}
        self._monitor_thread = Thread(
            target=self._serial_monitor, name="Serial Monitor", daemon=True
        )
        self._monitor_thread.start()
        self._dispatcher_thread = Thread(
            target=self._cb_dispatcher, name="Callback Dispatcher", daemon=True
        )
        self._dispatcher_thread.start()

        # Logging
        self._log_filename = None

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
        continue to exist unless this method is called.
        """

        self._kill_monitor = True

    def _send(self, message: bytes):
        """
        Send an arbitrary string to the UWB device.
        """
        if isinstance(message, str):
            message = message.encode(self._encoding) #TODO: should remove this.

        if self.verbose:
            print("<< ", end="")
            print(str(message)[2:-1], end="")
            
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
        out = self.device.readline() + self.device.read(self.device.in_waiting)
        # out = out.decode(self._encoding, errors="ignore")
        
        return out

    def _serial_monitor(self):
        """
        Continuously monitors the serial port, watching for official messages.
        If an official message is detected, it is extracted and stored in a queue.
        """

        while not self._kill_monitor:
            out = self._read()

            if len(out) > 0:

                # Find all messages in the string (might be slow)
                msg_idxs = [
                    out.find(msg_key)
                    for msg_key in self._r_format_dict.keys()
                    if msg_key in out
                ]
                msg_idxs.sort()

                # Extract all the messages and parse them
                if len(msg_idxs) > 0:
                    for idx in msg_idxs:
                        temp = out[idx:]
                        msg_key = temp[0:3]
                        try:
                            field_values = self.packer.unpack(temp[3:], self._r_format_dict[msg_key])
                            self._response_container[msg_key] = field_values
                            self._msg_queue.append((msg_key, field_values))
                        except Exception as e:
                           if self.verbose:
                               print("Message parsing error occured.")
                               print(traceback.format_exc())
                               print(e)

    def _cb_dispatcher(self):
        while not self._kill_monitor:
            if len(self._msg_queue) > 0:
                msg_key, field_values = self._msg_queue.pop(0)

                # Check if any callbacks are registered for this specific msg
                if msg_key in self._callbacks.keys():
                    cb_list = self._callbacks[msg_key]
                    for cb in cb_list:
                        cb(*field_values)  # Execute the callback
            else:
                sleep(0.001)  # To prevent high CPU usage
                # TODO: look into threading events to avoid busywait

    def register_callback(self, msg_key: str, cb_function):
        """
        Registers a callback function to be executed whenever a specific
        message key is received over serial.
        """
        msg_key = msg_key.encode(self._encoding)
        if msg_key in self._callbacks.keys():
            self._callbacks[msg_key].append(cb_function)
        else:
            self._callbacks[msg_key] = [cb_function]

    def unregister_callback(self, msg_key: str, cb_function):
        """
        Removes a callback function from the execution list corresponding to
        a specific message key.
        """
        msg_key = msg_key.encode(self._encoding)
        if msg_key in self._callbacks.keys():
            if cb_function in self._callbacks[msg_key]:
                self._callbacks[msg_key].remove(cb_function)
            else:
                print("This callback is not registered.")
        else:
            print("No callbacks registered for this key.")

    def _execute_command(self, command_key: str, response_key: str, *args):
        command_key = command_key.encode(self._encoding)
        response_key = response_key.encode(self._encoding)
        self._response_container[response_key] = None
        msg = self.packer.pack(args, self._c_format_dict[command_key])
        msg = command_key + msg
        self._send(msg)
        start_time = time()
        while (
            self._response_container[response_key] is None
            and (time() - start_time) < self.timeout
        ):
            # TODO: threading package has solutions to avoid this busy wait
            sleep(0.001)
        return self._response_container[response_key]

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

    ############################################################################
    ########################## COMMAND IMPLEMENTATIONS #########################
    ############################################################################
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
        elif response[0] == rsp_key:
            return True
        else:
            return False

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
        if response is False or response is None:
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
        test_bytes = msgpack.packb(test_dict)
        test_fields = [
            123456,
            "the test string",
            True,
            1.234567891011e-8,
            test_bytes,
        ]
        response = self._execute_command(msg_key, rsp_key, *test_fields)
        if response is None or response is False:
            return {"error_id": -1, "is_valid": False}
        else:
            return {"error_id": response[0], "is_valid": True}

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

    def do_twr(
        self, target_id=1, meas_at_target=False, mult_twr=False, output_ts=False
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
        output_ts: bool
            flag indicate if the recorded timestamps will also be output.
            Does not get passed to the modules.

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
                the master tag's clock
            rx1: float
                timestamp of the reception time of signal 1 in
                the slave tag's clock
            tx2: float
                timestamp of the transmission time of signal 2 in
                the slave tag's clock
            rx2: float
                timestamp of the reception time of signal 2 in
                the master tag's clock
            tx3: float
                timestamp of the transmission time of signal 3 in
                the slave tag's clock
            rx3: float
                timestamp of the reception time of signal 3 in
                the master tag's clock
        """
        msg_key = "C05"
        rsp_key = "R05"
        response = self._execute_command(
            msg_key, rsp_key, target_id, meas_at_target, mult_twr
        )
        if response is False or response is None:
            return {"neighbour": 0.0, "range": 0.0, "is_valid": False}
        elif output_ts is True and mult_twr is not 0:
            return {
                "neighbour": response[0],
                "range": response[1],
                "tx1": response[2],
                "rx1": response[3],
                "tx2": response[4],
                "rx2": response[5],
                "tx3": response[6],
                "rx3": response[7],
                "is_valid": True,
            }
        elif output_ts is True and mult_twr is 0:
            return {
                "neighbour": response[0],
                "range": response[1],
                "tx1": response[2],
                "rx1": response[3],
                "tx2": response[4],
                "rx2": response[5],
                "is_valid": True,
            }
        else:
            return {
                "neighbour": response[0],
                "range": response[1],
                "is_valid": True,
            }

    def broadcast(self, data):
        """
        Broadcast an arbitrary dictionary of data over UWB.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C06"
        rsp_key = "R06"

        data_serialized = msgpack.packb(data, use_single_float=True)

        response = self._execute_command(msg_key, rsp_key, data_serialized)
        if response is None:
            return False
        else: 
            return True

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

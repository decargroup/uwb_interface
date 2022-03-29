import serial
from serial.tools import list_ports
from time import time, sleep
from datetime import datetime
from threading import Thread


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
        "C00": "",
        "C01": "",
        "C02": "",
        "C03": "",
        "C04": "bool",
        "C05": "int,bool,int",
        "C06": "",
    }
    _r_format_dict = {
        "R00": "",
        "R01": "int",
        "R02": "",
        "R03": "int",
        "R04": "",
        "R05": "int,float,float,float,float,float,float,float",
        "R06": "",
        "R99": "float,float,float,float",
    }
    _format_dict = {**_c_format_dict, **_r_format_dict}  # merge both dicts
    _sep = "|"
    _eol = "\r"
    _eol_encoded = _eol.encode(_encoding)

    def __init__(self, port, baudrate=19200, timeout=0.1, verbose=False, log=False):
        """
        Constructor
        """
        self.device = serial.Serial(port, baudrate=baudrate, timeout=0.1)
        self.verbose = verbose
        self.timeout = timeout
        self.logging = log

        # Start a seperate thread for serial port monitoring
        self._kill_monitor = False
        self._msg_queue = []
        self._callbacks = {}
        self._response_container = {}
        self._monitor_thread = Thread(target=self._serial_monitor, name="Serial Monitor", daemon=True)
        self._monitor_thread.start()
        self._dispatcher_thread = Thread(target=self._cb_dispatcher, name="Callback Dispatcher", daemon=True)
        self._dispatcher_thread.start()

        # Logging
        self._is_logfile_setup = False

    def _create_log_file(self):
        # Current date and time for logging
        temp = self.get_id()
        self.id = temp["id"]
        temp = datetime.now()
        self._now = temp.strftime("%d_%m_%Y_%H_%M_%S")
        self._log_filename = "datasets/log_"+self._now+"_ID"+str(self.id)+".txt"


    def close(self):
        """
        Proper shutdown of this module. Note that even if the object does not
        exist anymore in the main thread, the two internal threads will
        continue to exist unless this method is called.
        """

        self._kill_monitor = True

    def _send(self, message):
        """
        Send an arbitrary string to the UWB device.
        """
        if isinstance(message, str):
            if self.verbose:
                print("<< " + message)
            message = message.encode(self._encoding)
        self.device.write(message)

    def _read(self):
        """
        Read arbitrary string from UWB device.
        """
        # Here we use pyserial's readline() command to take advantage of the
        # built-in timeout feature. This lets us wait a bit for messages to
        # arrive over USB. However, once we do recieve a message, we immediately
        # call read(device.in_waiting) to also read whatever else is in the
        # input buffer.
        out = self.device.readline() + self.device.read(self.device.in_waiting)
        out = out.decode(self._encoding, errors="replace")
        if self.verbose:
            print(">> " + out, end="")
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
                        idx_end = temp.find(self._eol)
                        #try:
                        parsed_msg = self._parse_message(temp[:idx_end])
                        self._response_container[parsed_msg[0]] = parsed_msg
                        self._msg_queue.append(parsed_msg)
                        #except:
                            #if self.verbose:
                        #print("Message parsing error occured.")

    def _cb_dispatcher(self):
        while not self._kill_monitor:
            if len(self._msg_queue) > 0:
                parsed_msg = self._msg_queue.pop(0)

                # Check if any callbacks are registered for this specific msg
                if parsed_msg[0] in self._callbacks.keys():
                    cb_list = self._callbacks[parsed_msg[0]]
                    for cb in cb_list:
                        cb(*parsed_msg[1:])  # Execute the callback
            else:
                sleep(0.001)  # To prevent high CPU usage
                # TODO: look into threading events to avoid busywait

    def register_callback(self, msg_key, cb_function):
        """
        Registers a callback function to be executed whenever a specific
        message key is received over serial.
        """
        if msg_key in self._callbacks.keys():
            self._callbacks[msg_key].append(cb_function)
        else:
            self._callbacks[msg_key] = [cb_function]

    def unregister_callback(self, msg_key, cb_function):
        """
        Removes a callback function from the execution list corresponding to
        a specific message key.
        """
        if msg_key in self._callbacks.keys():
            if cb_function in self._callbacks[msg_key]:
                self._callbacks[msg_key].remove(cb_function)
            else:
                print("This callback is not registered.")
        else:
            print("No callbacks registered for this key.")

    def _check_field_format(self, specifier: str, field):
        """
        Checks to see if a particular field complies with its format specifier.
        """
        specifier = specifier.strip()
        if specifier == "int":
            return isinstance(field, int)
        if specifier == "float":
            return isinstance(field, float)
        if specifier == "str":
            return isinstance(field, str)
        if specifier == "bool":
            return isinstance(field, bool)
        if specifier == "uint":
            return isinstance(field, int) and field >= 0

    def _build_message(self, msg_key: str, fieldvalues: list = None):
        """
        Constructs the message string and checks if the format is correct.
        """
        # Check to see if all the fieldvalues match with the message format
        if len(self._format_dict[msg_key]) > 0:
            fieldtypes = self._format_dict[msg_key].split(",")
            for i, t in enumerate(fieldtypes):
                if not self._check_field_format(t, fieldvalues[i]):
                    raise RuntimeError("Incorrect message format.")

        # Assemble the message
        msg = msg_key
        converted = []
        if fieldvalues is not None:

            # Perform type-specific conversion on each field.
            for field in fieldvalues:
                if isinstance(field, bool):
                    converted.append(str(int(field)))
                elif isinstance(field, int):
                    converted.append(str(field))
                elif isinstance(field, float):
                    # TODO: needs to be replaced by float_to_hex
                    converted.append(str(field))
                elif isinstance(field, str):
                    converted.append(field)

        if len(converted) > 0:
            msg += self._sep + self._sep.join(converted)

        msg += "\r"
        return msg

    def _parse_message(self, msg, msg_key=None):
        """
        Parses a pure string message into a list of values, where each value
        is converted to the type as specified in _format_dict[msg_key]

        If no msg_key is provided, it will automatically be detected as the
        first field in the message.
        """

        if not isinstance(msg, str):
            msg = str(msg)

        fields = msg.split(self._sep)
        received_key = fields[0]
        if msg_key is None:
            msg_key = received_key

        format = self._format_dict[msg_key].split(",")
        results = [received_key]
        if format[0] == "":
            return results

        for i in range(len(format)):
            # This can potentially throw errors if value is not convertible
            # to say, a float.
            if i + 1 <= len(fields) - 1:
                value = fields[i + 1]
                if format[i] == "int":
                    results.append(int(value))
                elif format[i] == "float":
                    results.append(float(value))
                elif format[i] == "bool":
                    results.append(bool(value))
                elif format[i] == "str":
                    results.append(str(value))
                else:
                    raise RuntimeError("unsupported format type.")
            else:
                results.append(None)

        return results

    def _execute_command(self, command_key, response_key, *args):
        if self.logging and not self._is_logfile_setup:
            self._create_log_file()

        self._response_container[response_key] = None
        msg = self._build_message(command_key, args)
        self._send(msg)
        start_time = time()
        while (
            self._response_container[response_key] is None
            and (time() - start_time) < self.timeout
        ):
            # TODO: threading package has solutions to avoid this busy wait
            sleep(0.001)
        return self._response_container[response_key]

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

    def output(self,data):
        """
        Outputs data by printing and saving to a log file.

        PARAMETERS:
        -----------
        data: unspecified
            data to be stored and printed
        """
        data = str(data)
        print(data)
        if self.logging is True:
            with open(self._log_filename, "a") as myfile:
                myfile.write(data+"\n")

    def log(self, data):
        """
        Logs data by printing and saving to a log file.

        PARAMETERS:
        -----------
        data: unspecified
            data to be stored and printed
        """
        self.output(data)


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
            return {"id": -1, "is_valid": False}
        else:
            self.id = response[1]
            return {"id": response[1], "is_valid": True}

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
        elif response[0] == rsp_key:
            return True
        else:
            return False

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
        response = self._execute_command(msg_key, rsp_key)
        if response is None or response is False:
            return {"error_id": -1, "is_valid": False}
        else:
            return {"error_id": response[1], "is_valid": True}

    def toggle_passive(self, toggle=0):
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
        elif response[0] == rsp_key:
            return True
        else:
            return False

    def do_twr(self, target_id=1, meas_at_target=False, mult_twr=False, output_ts=False):
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
        response = self._execute_command(msg_key, rsp_key, target_id,
                                         meas_at_target, mult_twr)
        if response is False or response is None:
            return {"neighbour": 0.0, "range": 0.0, "is_valid": False}
        elif output_ts is True and mult_twr is not 0:
            return {"neighbour": response[1], "range": response[2], 
                    "tx1": response[3], "rx1": response[4],
                    "tx2": response[5], "rx2": response[6],
                    "tx3": response[7], "rx3": response[8],
                    "is_valid": True}
        elif  output_ts is True and mult_twr is 0:
            return {"neighbour": response[1], "range": response[2], 
                    "tx1": response[3], "rx1": response[4],
                    "tx2": response[5], "rx2": response[6],
                    "is_valid": True}
        else:
            return {"neighbour": response[1], "range": response[2],
                    "is_valid": True}
                    
    def broadcast(self):
        """
        Broadcast an arbitrary dictionary of data over UWB.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C06"
        rsp_key = "R06"
        response = self._execute_command(msg_key, rsp_key)
        if response is None:
            return False
        elif response[0] == rsp_key:
            return True
        else:
            return False
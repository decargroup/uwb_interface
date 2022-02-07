import serial
from serial.tools import list_ports
from time import time, sleep


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
    return uwb_ports


class UwbModule(object):
    """
    Main interface object for DECAR/MRASL UWB modules.

    """

    _encoding = "utf-8"
    _format_dict = {
        "C00": "",
        "R00": "",
        "C01": "",
        "R01": "int",
        "C02": "",
        "R02": "",
        "C03": "",
        "R03": "int",
        "C04": "bool",
        "R04": "",
        "C05": "int,bool",
        "R05": "float",
    }
    _sep = ","
    _eol = "\r"

    def __init__(self, port, baudrate=19200, timeout=1):
        self.device = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self._eol_encoded = self._eol.encode(self._encoding)

    def __del__(self):
        """
        Destructor.
        """
        if hasattr(self, "device"):
            if isinstance(self.device, serial.Serial):
                print("Closing serial connection.")
                self.device.close()

    def _send(self, message):
        """
        Send an arbitrary string to the UWB device.
        """
        if isinstance(message, str):
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
        return out.decode(self._encoding, errors="replace")

    def _wait_for_response(self, msg_key: str, max_attempts=10):
        """
        Reads the serial port a max_attempts number of times until a response is
        detected. Then, extracts the response.
        """
        idx = -1
        start_time = time()
        for i in range(max_attempts):
            out = self._read()
            idx = out.find(msg_key)
            if idx >= 0:
                resp = out[idx:]
                idx_end = resp.find(self._eol)
                return resp[:idx_end]
            sleep(0.001)  # NOTE: this might limit our command frequency to 1000Hz
        # TODO: we need a more standardized error reporting system
        # raise RuntimeError("No valid response received.")
        return False

    def _extract_response(self, string: str, msg_key: str):
        idx = string.find(msg_key)
        string2 = string[idx:]
        idx2 = string2.find(self._eol)
        return string2[:idx2]
    

    def _serial_exchange(self, msg: str):
        """
        Sends a message, then immediately collects a response.
        """
        self._send(msg)
        response = self._read()
        if len(response) == 0:
            return False
            #raise serial.SerialException("Didn't receive response from MCU.")
        return response

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

        if not isinstance(msg, str):
            msg = str(msg)

        fields = msg.split(self._sep)
        format = self._format_dict[msg_key].split(self._sep)

        received_key = fields[0]
        if msg_key is not None:
            if received_key != msg_key:
                # raise RuntimeError("Did not receive expected response key.")
                return False
            elif len(fields) == 1:
                return True

        if len(fields) - 1 != len(format):
            # raise RuntimeError("Received different amount of data than expected.")
            return False

        results = []
        for i, value in enumerate(fields[1:]):
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
        return results

    def set_idle(self):
        """
        Sets the module to be idle/inactive.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C00"
        rsp_key = "R00"
        msg = self._build_message(msg_key, None)
        raw_response = self._serial_exchange(msg)
        response = self._extract_response(raw_response, rsp_key)
        parsed = self._parse_message(response, rsp_key)
        if parsed is True:
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
        msg = self._build_message(msg_key, None)
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        if response is False:
            return {"id": -1, "is_valid": False}

        parsed = self._parse_message(response, rsp_key)
        if parsed is False:
            return {"id": -1, "is_valid": False}
        else:
            self.id = parsed[0]
            return {"id": parsed[0], "is_valid": True}

    def reset(self):
        """
        Resets and re-enables the DW receiver.

        RETURNS:
        --------
        bool: successfully received response
        """
        msg_key = "C02"
        rsp_key = "R02"
        msg = self._build_message(msg_key, None)
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        if response is False:
            return False

        parsed = self._parse_message(response, rsp_key)

        if parsed is True:
            return True
        else:
            return False

    def do_tests(self):
        """
        Performs pre-determined tests to identify any faults with the board.

        RETURNS:
        --------
        dict with fields:
            errorID: int
                ID associated with the error that occured.
            is_valid: bool
                whether the result is valid or some error occured
        """
        msg_key = "C03"
        rsp_key = "R03"
        msg = self._build_message(msg_key, None)
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        if response is False:
            return {"errorID": -1, "is_valid": False}

        parsed = self._parse_message(response, rsp_key)

        if parsed is False:
            return {"errorID": -1, "is_valid": False}
        else:
            return {"errorID": parsed[0], "is_valid": True}

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
        msg = self._build_message(msg_key, [toggle])
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        if response is False:
            return False

        parsed = self._parse_message(response, rsp_key)

        if parsed is True:
            return True
        else:
            return False

    def do_twr(self, target_id=1, meas_at_target=False):
        """
        Performs Two-Way Ranging with a chosen target/destination tag.

        PARAMETERS:
        -----------
        target_id: int
            ID of the tag to range with
        meas_at_target: bool
            flag to have the range measurement also available at the target

        RETURNS:
        --------
        dict with fields:
            range: float
                range measurement in meters
            is_valid: bool
                whether the result is valid or some error occured
        """
        msg_key = "C05"
        rsp_key = "R05"
        msg = self._build_message(msg_key, [target_id, meas_at_target])
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        if response is False:
            return {"range": 0.0, "is_valid": False}

        parsed = self._parse_message(response, rsp_key)

        if parsed is False:
            return {"range": 0.0, "is_valid": False}
        else:
            return {"range": parsed[0], "is_valid": True}

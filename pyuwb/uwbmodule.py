import serial 
from time import time, sleep

class UwbModule(object):
    _encoding = "utf-8"
    _format_dict = {
        "C00":"",
        "R00":"",
        "C01":"",
        "R01":"int",
        "C02":"int,bool",
        "R02":"float"
    }
    _sep = ","
    _eol = "\r"
    def __init__(self, port, baudrate = 19200, timeout = 1):
        self.device = serial.Serial(port, baudrate=baudrate, timeout = timeout)
        self._eol_encoded = self._eol.encode(self._encoding)

    def __del__(self):
        """ 
        Destructor. 
        """
        print("Closing serial connection")
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
        out = self.device.readline() + self.device.read(self.device.in_waiting)
        return out.decode(self._encoding, errors="replace")

    def _wait_for_response(self, msg_key: str, max_attempts = 10):
        """
        
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
            sleep(0.001)
        
        raise RuntimeError("No valid response received.")
        


    def _extract_response(self, string: str, msg_key:str):
        idx = string.find(msg_key)
        string2 = string[idx:]
        idx2 = string2.find(self._eol)
        return string2[:idx2]

    def _check_message_format(self, msg_key, msg):
        pass
    
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

    def _serial_exchange(self, msg):
        """
        Sends a message, then immediately collects a response.
        """
        self._send(msg)
        response = self._read()
        if len(response) == 0:
            raise serial.SerialException("Didn't receive response from MCU.")
        return response
        
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
        if fieldvalues is not None:
            # Convert everything to strings
            # TODO: will need to add float_to_hex here.
            fieldvalues = [str(x) for x in fieldvalues]
            # Join them all in a big string
            if len(fieldvalues) > 0:
                msg += self._sep + self._sep.join(fieldvalues)

        msg += "\r"
        return msg

    def _parse_message(self, msg, msg_key = None):

        if not isinstance(msg, str):
            msg = str(msg)

        fields = msg.split(self._sep)
        format = self._format_dict[msg_key].split(self._sep)

        received_key = fields[0]
        if msg_key is not None:
            if received_key != msg_key:
                #raise RuntimeError("Response is not what was expected!")
                return False

        if len(fields)-1 != len(format):
            #raise RuntimeError("Received different amount of data than expected.")
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
                # TODO: add the remaining datatypes as needed
            else: 
                raise RuntimeError("unsupported format type.")
        return results

    def set_idle(self):
        msg_key = "C00"
        rsp_key = "R00"
        msg = self._build_message(msg_key, None)
        raw_response = self._serial_exchange(msg)
        response = self._extract_response(raw_response, rsp_key)
        parsed = self._parse_message(response, rsp_key) 

    def get_id(self):
        msg_key = "C01"
        rsp_key = "R01"
        msg = self._build_message(msg_key, None) 
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        parsed = self._parse_message(response, rsp_key)
        if parsed is False:
            return {"id":-1, "is_valid":False}
        else:
            return {"id":parsed[0], "is_valid":True}

    def do_twr(self, target_id = 1, meas_at_target = False):
        msg_key = "C02"
        rsp_key = "R02"
        msg = self._build_message(msg_key, [target_id, meas_at_target]) 
        self._send(msg)
        response = self._wait_for_response(rsp_key)
        parsed = self._parse_message(response, rsp_key)

        if parsed is False:
            return {"range":0.0, "is_valid":False}
        else:
            return {"range":parsed[0], "is_valid":True}


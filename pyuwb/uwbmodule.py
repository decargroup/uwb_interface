from pdb import runeval
import serial 

class UwbModule(object):
    _encoding = "utf-8"
    _format_dict = {
        "C01":"",
        "C02":"i",
        "R01":"i",
        "R02":"f"
    }

    def __init__(self, port, baudrate = 19200, timeout = 1):
        self.device = serial.Serial(port, baudrate=baudrate, timeout = timeout)

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
        if type(message) == str:
            message = message.encode(self._encoding)
        
        self.device.write(message)
    
    def _read(self):
        """ 
        Read arbitrary string from UWB device. 
        """
        out = self.device.readline()
        return out.decode(self._encoding)

    def _check_message_format(self, msg_key, msg):
        pass
    
    def _check_field_format(self, specifier: str, field):
        """
        Checks to see if a particular field complies with its format specifier.
        """
        if specifier == "i":
            return isinstance(field, int)
        if specifier == "f":
            return isinstance(field, float)
        if specifier == "s":
            return isinstance(field, str)
        if specifier == "?":
            return isinstance(field, bool)
        if specifier == "I":
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
        
    def _build_message(self, msg_key: str, fields: list = None):
        """
        Constructs the message string and checks if the format is correct.
        """
        # Check to see if all the fields match with the message format
        for i, c in enumerate(self._format_dict[msg_key]):
            if not self._check_field_format(c, fields[i]):
                raise RuntimeError("Incorrect message format.")

        # Assemble the message
        msg = msg_key
        format = self._format_dict["C01"]
        if fields is not None:
            # Convert everything to strings
            fields = [str(x) for x in fields]
            # Join them all in a big string
            if len(fields) > 0:
                msg += ";" + ";".join(fields)

        msg += "\r"
        return msg

    def _parse_message(self, msg, msg_key = None):

        if not isinstance(msg, str):
            msg = str(msg)

        fields = msg.split(";")
        format = self._format_dict[msg_key]

        received_key = fields[0]
        if msg_key is not None:
            if received_key[0:3] != msg_key:
                raise RuntimeError("Response is not what was expected!")

        if len(fields)-1 != len(format):
            raise RuntimeError("Received different amount of data than expected.")

        
        results = []
        for i, value in enumerate(fields[1:]):
            if format[i] == "i":
                results.append(int(value))
            elif format[i] == "f":
                results.append(float(value))
            elif format[i] == "?":
                results.append(bool(value))
            else: 
                raise RuntimeError("unsupported format type.")
        return results
    
    def get_id(self):
        msg_key = "C01"
        rsp_key = "R01"
        msg = self._build_message(msg_key, None)
        response = self._serial_exchange(msg)
        parsed = self._parse_message(response, rsp_key)
        return {"id":parsed[0]}

    def do_twr(self, destination_id: int):
        msg_key = "C02"
        rsp_key = "R02"
        msg = self._build_message(msg_key, [destination_id]) 
        response = self._serial_exchange(msg)
        parsed = self._parse_message(response, rsp_key)
        return {"range":parsed[0]}

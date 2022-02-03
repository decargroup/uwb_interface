from curses import baudrate
from pyuwb import UwbModule

uwb = UwbModule("/dev/ttyACM1", baudrate=19200)
resp = uwb.get_id()
print(resp["id"])

# %%
from pyuwb import UwbModule, find_uwb_serial_ports

ports = find_uwb_serial_ports()
uwb1 = UwbModule(ports[1], verbose=False)
uwb2 = UwbModule(ports[0], verbose=False)

id1 = uwb1.get_id()
id2 = uwb2.get_id()

while True:
    data = uwb1.do_twr(
        target_id = id2['id'],
        ds_twr = True,
        meas_at_target=True,
    )
    # uwb2.wait_for_messages()
    print(data)

    data = uwb2.do_twr(
        target_id = id1['id'],
        ds_twr = True,
        meas_at_target=True,
    )
    # uwb1.wait_for_messages()
    print(data)
# %%
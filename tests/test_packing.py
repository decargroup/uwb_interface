from pyuwb.packing import *
import msgpack


def test_all_types():
    test_dict = {"a": 3.14159, "b": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]}
    test_bytes = msgpack.packb(test_dict)
    test_values = [
        123456,
        "the test string",
        True,
        1.234567891011e-8,
        test_bytes,
    ]
    test_types = [IntField, StringField, BoolField, FloatField, ByteField]

    test_unpack = (
        b"|123456|the test string|1|1.234567891011e-8|"
        b"G\x00\x82\xa1a\xcb@\t!\xf9\xf0\x1b\x86n\xa1b\x92\x93\xcb?\xf0\x00\x00\x00"
        b"\x00\x00\x00\xcb@\x00\x00\x00\x00\x00\x00\x00\xcb@\x08\x00\x00\x00\x00"
        b"\x00\x00\x93\xcb@\x10\x00\x00\x00\x00\x00\x00\xcb@\x14\x00\x00\x00\x00"
        b"\x00\x00\xcb@\x18\x00\x00\x00\x00\x00\x00\r"
    )

    packer = Packer()
    msg = packer.pack(test_values, test_types)
    values_unpacked = packer.unpack(test_unpack, test_types)
    assert values_unpacked == test_values
    assert msg.split(packer._sep)[:3] == test_unpack.split(packer._sep)[:3]


if __name__ == "__main__":
    test_all_types()

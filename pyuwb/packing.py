import struct
from typing import Any, List
from abc import ABC, abstractmethod

encoding = "utf-8"


class Field(ABC):
    """
    An abstract Field is essentially a namespace for two specific methods:

     - a `pack` method that takes a specific variable type and returns a
       representation in bytes
     - an `unpack` method that takes an array of bytes and returns a variable
       of that type.

    In the unpack method, the index of the next key character will also be
    supplied. A key character is either a field separator or a message
    terminator. The implementation of the unpack method can therefore use the
    location of the key character to detect how many bytes to read. As a
    second output argument, it is mandatory to provide the index of the first
    byte of the following field in the message.

    """

    @staticmethod
    @abstractmethod
    def pack(value: Any) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def unpack(msg: bytes, next_key_idx: int) -> Any:
        # return value, next_field_idx
        pass


class IntField(Field):
    @staticmethod
    def pack(value: int) -> bytes:
        return str(value).encode(encoding)

    @staticmethod
    def unpack(msg: bytes, next_key_idx: int) -> int:
        return int(msg[:next_key_idx].decode(encoding)), next_key_idx + 1


class BoolField(Field):
    @staticmethod
    def pack(value: bool) -> bytes:
        return str(int(value)).encode(encoding)

    @staticmethod
    def unpack(msg: bytes, next_key_idx: int) -> bool:
        if next_key_idx != 1:
            raise RuntimeError("Bool field is more than 1 byte..")

        return bool(msg[:next_key_idx].decode(encoding)), next_key_idx + 1


class StringField(Field):
    @staticmethod
    def pack(value: str) -> bytes:
        return value.encode(encoding)

    @staticmethod
    def unpack(msg: bytes, next_key_idx: int) -> str:
        return msg[:next_key_idx].decode(encoding), next_key_idx + 1


class FloatField(Field):
    @staticmethod
    def pack(value: float) -> bytes:
        return struct.pack("<f", value)

    @staticmethod
    def unpack(msg: bytes, next_key_idx: int) -> float:
        return float(msg[:next_key_idx].decode(encoding)), next_key_idx + 1


class ByteField(Field):
    @staticmethod
    def pack(value: bytes) -> bytes:
        num_bytes = len(value)
        return struct.pack("<H", num_bytes) + value

    @staticmethod
    def unpack(msg: bytes, next_key_idx: int) -> bytes:
        fieldlen = struct.unpack("<H", msg[:2])

        return msg[2 : 2 + fieldlen[0]], 2 + fieldlen[0] + 1


class Packer:
    def __init__(self, separator: str = "|", terminator: str = "\r"):
        self._sep = separator.encode(encoding)
        self._eol = terminator.encode(encoding)

    def pack(self, field_values: List[Any], field_types: List[Field]) -> bytes:
        msg = b""
        for i, val in enumerate(field_values):
            msg += self._sep + field_types[i].pack(val)
        msg += self._eol

        return msg  # Dont include initial separator

    def unpack(self, msg: bytes, field_types: List[Field]):

        # If no expected fields, return empty.
        results = []
        if field_types is None or len(field_types) == 0:
            return results

        # There will always be a separator character at the beginning.
        # Remove it.
        msg = msg[1:]

        for field in field_types:

            # Find the "soonest" key character (separator or terminator)
            next_sep = msg.find(self._sep)
            next_eol = msg.find(self._eol)
            if next_sep == -1 and next_eol == -1:
                raise RuntimeError(
                    "No separator or terminator detected in received message."
                )
            elif next_sep == -1:
                next_key_idx = next_eol
            elif next_eol == -1:
                next_key_idx = next_sep
            else:
                next_key_idx = min(next_sep, next_eol)

            # Unpack the value
            value, next_field_idx = field.unpack(msg, next_key_idx)
            results.append(value)

            # Move through the message to the next field.
            msg = msg[next_field_idx:]

        return results

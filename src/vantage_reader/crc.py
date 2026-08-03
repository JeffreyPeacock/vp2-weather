"""Davis CRC-16: CRC-16/CCITT, polynomial 0x1021, seed 0 (aka XMODEM).

The console appends the CRC big-endian, so a packet including its CRC
checks to 0. (Vantage Serial Protocol v2.6.1, section XIII.)
"""

_POLY = 0x1021


def _make_table() -> list[int]:
    table = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ _POLY) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
        table.append(crc)
    return table


_TABLE = _make_table()


def crc16(data: bytes, crc: int = 0) -> int:
    for byte in data:
        crc = (_TABLE[(crc >> 8) ^ byte] ^ (crc << 8)) & 0xFFFF
    return crc


def check(packet: bytes) -> bool:
    """True when a packet with trailing big-endian CRC is intact."""
    return crc16(packet) == 0

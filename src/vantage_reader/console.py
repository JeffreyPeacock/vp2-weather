"""Serial driver for the Davis Vantage Pro 2 console.

Port of the working Java driver (VantagePro2Driver) against the Vantage
Serial Protocol v2.6.1: 19200 8N1, LF wakeup, `LPS 3 n` for alternating
LOOP/LOOP2 packets. Unlike the Java, packets that fail CRC are dropped.
"""

from __future__ import annotations

import time

import serial

from . import crc, packets

ACK = 0x06
WAKE_ATTEMPTS = 3
WAKE_WAIT_S = 1.2


class ConsoleError(Exception):
    """Console did not respond as the protocol requires."""


class VantageConsole:
    def __init__(self, port: str, *, baud: int = 19200, timeout: float = 10.0):
        self.port_name = port
        self._port = serial.Serial(port, baudrate=baud, timeout=timeout,
                                   bytesize=serial.EIGHTBITS,
                                   parity=serial.PARITY_NONE,
                                   stopbits=serial.STOPBITS_ONE)

    def close(self) -> None:
        try:
            self._port.write(b"\r")  # cancel any active LOOP stream
        except serial.SerialException:
            pass
        self._port.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _scan_for(self, patterns: tuple[bytes, ...], max_bytes: int = 256) -> bool:
        """Read bytes (each waits up to the port timeout, like the Java
        driver's per-byte semantics) discarding garbage until one of the
        patterns appears. Garbage tolerance matters on a marginal link."""
        window = b""
        for _ in range(max_bytes):
            byte = self._port.read(1)
            if not byte:
                return False  # line went quiet for a full timeout
            window = (window + byte)[-8:]
            if any(p in window for p in patterns):
                return True
        return False

    def wake(self) -> None:
        """Davis-documented wakeup: send LF, scan for LF CR, retry up to 3x.

        Mirrors the proven Java driver: junk bytes before the \\n\\r are
        skipped rather than failing the attempt.
        """
        for _ in range(WAKE_ATTEMPTS):
            self._port.reset_input_buffer()
            self._port.write(b"\n")
            if self._scan_for((b"\n\r",)):
                return
            time.sleep(WAKE_WAIT_S)
        raise ConsoleError("console did not wake (is it connected and powered?)")

    def test(self) -> None:
        """TEST echo — sanity check that commands round-trip.

        Like the Java driver, a bare \\n\\r response (echo lost, console
        awake) is accepted as success.
        """
        self._port.reset_input_buffer()
        self._port.write(b"TEST\n")
        if not self._scan_for((b"TEST", b"\n\r")):
            raise ConsoleError("TEST failed: no response")

    def stop_streaming(self) -> bool:
        """STRMOFF — cancel any leftover streaming mode from a prior
        session (the Java driver sent this on every connect). Non-fatal."""
        self._port.reset_input_buffer()
        self._port.write(b"STRMOFF\n")
        return self._scan_for((b"OK", b"\n\r"))

    def read_pair(self) -> tuple[dict, dict]:
        """One (LOOP, LOOP2) decoded pair via `LPS 3 2`."""
        got: dict[int, dict] = {}
        last_err = "no ACK for LPS"
        for _ in range(3):  # a retry budget for CRC drops / missing type
            self._port.reset_input_buffer()
            self._port.write(b"LPS 3 2\n")
            # Scan for the ACK rather than demanding it first: a radio in
            # echo mode reflects our own command bytes before the ACK.
            for _ in range(16):
                first = self._port.read(1)
                if not first or first == bytes([ACK]):
                    break
            if first != bytes([ACK]):
                last_err = f"no ACK for LPS, last byte {first!r}"
                continue
            for _ in range(2):
                packet = self._read_packet()
                if packet is None or not crc.check(packet):
                    continue
                kind = packets.packet_type(packet)
                if kind == 0:
                    got[0] = packets.decode_loop(packet)
                elif kind == 1:
                    got[1] = packets.decode_loop2(packet)
            if 0 in got and 1 in got:
                return got[0], got[1]
            last_err = "packets failed CRC or a type was missing"
        raise ConsoleError(f"could not collect a clean LOOP/LOOP2 pair: {last_err}")

    def _read_packet(self) -> bytes | None:
        """Align on the "LOO" prefix, then read the fixed 99-byte packet."""
        window = b""
        for _ in range(packets.PACKET_SIZE * 3):  # bounded resync scan
            byte = self._port.read(1)
            if not byte:
                return None  # timeout
            window = (window + byte)[-3:]
            if window == b"LOO":
                rest = self._port.read(packets.PACKET_SIZE - 3)
                if len(rest) != packets.PACKET_SIZE - 3:
                    return None
                return b"LOO" + rest
        return None

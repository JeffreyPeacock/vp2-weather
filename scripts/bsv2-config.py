#!/usr/bin/env python3
"""Configure a BlueSMiRF v2 over Bluetooth inside its 60-second command
window.

The BSv2 only honors the $$$ escape while millis() < 60000 (AT-MaxCommandTimeMs),
so: pair the radio first, power-cycle it, then run this script immediately.
It keeps knocking with $$$ (respecting the 2-second serial-silence rule)
until command mode opens, then sets the UART speed, saves, and exits.

    ./bsv2-config.py                       # /dev/rfcomm0 -> 19200 baud
    ./bsv2-config.py --port /dev/rfcomm1 --speed 9600

Opening the rfcomm device is what triggers the Bluetooth reconnect, so
starting the script IS the reconnect. The port's own baud setting is
irrelevant over Bluetooth; --speed sets the radio's wired UART side.
"""

import argparse
import sys
import time

import serial

ESCAPE_RETRY_S = 2.5   # firmware ignores escapes within 2s of serial traffic
DEADLINE_S = 90.0      # give up: the window is 60s from radio power-on


def read_until(port, token: bytes, timeout: float) -> bytes:
    """Collect bytes until token appears or timeout elapses."""
    got = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        got += port.read(64)
        if token in got:
            break
    return got


def command(port, cmd: str, timeout: float = 3.0) -> bool:
    port.reset_input_buffer()
    port.write(cmd.encode() + b"\r")
    answer = read_until(port, b"OK", timeout)
    print(f"  {cmd} -> {answer.decode(errors='replace').strip() or '(no response)'}")
    return b"OK" in answer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/rfcomm0",
                        help="Bluetooth serial device (default: /dev/rfcomm0)")
    parser.add_argument("--speed", type=int, default=19200,
                        help="UART baud to set on the radio (default: 19200)")
    args = parser.parse_args()

    print(f"opening {args.port} (this initiates the Bluetooth connection)...")
    try:
        port = serial.Serial(args.port, baudrate=115200, timeout=0.5)
    except serial.SerialException as exc:
        print(f"cannot open {args.port}: {exc}", file=sys.stderr)
        print("is the radio paired and bound? e.g.: sudo rfcomm bind 0 <bt-addr>",
              file=sys.stderr)
        return 1

    with port:
        print("knocking with $$$ (waiting for the command window)...")
        deadline = time.monotonic() + DEADLINE_S
        while True:
            if time.monotonic() > deadline:
                print("gave up: no OK within the deadline. Power-cycle the "
                      "radio and rerun this script right away.", file=sys.stderr)
                return 1
            port.reset_input_buffer()
            port.write(b"$$$")
            if b"OK" in read_until(port, b"OK", ESCAPE_RETRY_S):
                print("  in command mode.")
                break

        ok = command(port, f"AT-SerialSpeed={args.speed}")
        ok = command(port, "ATW") and ok      # save to NVM
        command(port, "ATX", timeout=1.0)     # exit command mode (may not echo OK)

        if not ok:
            print("configuration NOT confirmed — rerun to retry.", file=sys.stderr)
            return 1
        print(f"done: radio UART set to {args.speed} 8N1 and saved.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

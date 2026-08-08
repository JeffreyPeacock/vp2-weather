#!/usr/bin/env python3
"""Low-level console probe: send the Davis wakeup LF and dump every raw
byte that comes back. Reads the tea leaves for you.

    ./vp2-probe.py                  # /dev/rfcomm0
    ./vp2-probe.py --port /dev/ttyUSB0

Interpretation:
  b'\\n\\r' back        -> console is awake and talking; run vp2-read
  total silence        -> wiring: swap the two data wires (console TXD0
                          pin 6 -> radio RXI; console RXD0 pin 5 -> radio TXO)
  garbage bytes        -> baud mismatch: radio UART vs console setting
"""

import argparse
import sys
import time

import serial


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/rfcomm0",
                        help="serial device (default: /dev/rfcomm0)")
    parser.add_argument("--tries", type=int, default=6)
    args = parser.parse_args()

    try:
        port = serial.Serial(args.port, baudrate=115200, timeout=1,
                             write_timeout=3)
    except serial.SerialException as exc:
        print(f"cannot open {args.port}: {exc}", file=sys.stderr)
        return 1

    got_any = False
    with port:
        for attempt in range(1, args.tries + 1):
            port.write(b"\n")
            time.sleep(1.5)
            data = port.read(port.in_waiting or 0)
            got_any = got_any or bool(data)
            print(f"attempt {attempt}: sent LF, got {len(data)} bytes: {data!r}")

    if not got_any:
        print("\nverdict: total silence -> almost certainly wiring "
              "(TX/RX crossover); swapping the two data wires is harmless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

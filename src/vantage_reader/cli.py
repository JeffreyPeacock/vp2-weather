"""`vp2-read` — module 1 of the pipeline.

Reads the Davis VP2 console and writes one Weather Report JSON document
per line to stdout. All diagnostics go to stderr; stdout is data only.

    vp2-read --port /dev/rfcomm0 --interval 60 | wu-upload
"""

from __future__ import annotations

import argparse
import sys
import time

import serial

from weather_report import dumps_line

from .console import ConsoleError, VantageConsole
from .packets import build_report

RECONNECT_WAIT_S = 10.0


def _log(msg: str) -> None:
    print(f"vp2-read: {msg}", file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="/dev/rfcomm0",
                        help="serial device (default: /dev/rfcomm0)")
    parser.add_argument("--station-id", default="vp2",
                        help="station id stamped into each report")
    parser.add_argument("--interval", type=float, default=60.0,
                        help="seconds between reports (default: 60)")
    parser.add_argument("--count", type=int, default=0,
                        help="stop after N reports (default: run forever)")
    args = parser.parse_args(argv)

    emitted = 0
    console: VantageConsole | None = None
    while True:
        try:
            if console is None:
                console = VantageConsole(args.port)
                console.wake()
                console.test()
                if not console.stop_streaming():
                    _log("STRMOFF unanswered (continuing)")
                _log(f"connected to console on {args.port}")
            started = time.monotonic()
            console.wake()
            loop, loop2 = console.read_pair()
            sys.stdout.write(dumps_line(build_report(loop, loop2,
                                                     args.station_id)))
            sys.stdout.flush()
            emitted += 1
            if args.count and emitted >= args.count:
                console.close()
                return 0
            time.sleep(max(0.0, args.interval - (time.monotonic() - started)))
        except (ConsoleError, serial.SerialException, OSError) as exc:
            _log(f"{exc}; reconnecting in {RECONNECT_WAIT_S:g}s")
            if console is not None:
                try:
                    console.close()
                except Exception:
                    pass
                console = None
            time.sleep(RECONNECT_WAIT_S)
        except KeyboardInterrupt:
            if console is not None:
                console.close()
            return 0


if __name__ == "__main__":
    sys.exit(main())

"""`wu-upload` — module 2 of the pipeline.

Two modes:

Pipe mode (default when any Weather Report JSONL is on stdin): consume
reports, throttle to --period seconds, map, and upload. Upload failures
are logged to stderr and skipped — the pipe never stalls the reader.

    vp2-read --port /dev/rfcomm0 | wu-upload --period 300

One-shot mode (any measurement flag given): upload a single observation
built from the flags, for end-to-end testing without a console.

    wu-upload --tempf 70.2 --humidity 55

Credentials come from $WU_STATION_ID / $WU_STATION_KEY or --id/--key.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from weather_report import loads_line

from .mapping import report_to_observation
from .wunderground import Observation, UploadError, upload

_FLOAT_FIELDS = [
    "tempf", "humidity", "dewptf", "windspeedmph", "windgustmph",
    "windspdmph_avg2m", "windgustmph_10m", "baromin",
    "rainin", "dailyrainin", "solarradiation", "uv", "soiltempf",
    "indoortempf", "indoorhumidity",
]
_INT_FIELDS = ["winddir", "windgustdir", "windgustdir_10m",
               "soilmoisture", "leafwetness"]


def _log(msg: str) -> None:
    print(f"wu-upload: {msg}", file=sys.stderr, flush=True)


def _pipe_mode(args) -> int:
    last_upload = float("-inf")
    period = args.period if not args.realtime else max(args.period, 2.5)
    for line in sys.stdin:
        report = loads_line(line)
        if report is None:
            _log("skipping non-report line")
            continue
        now = time.monotonic()
        if now - last_upload < period:
            continue
        try:
            upload(args.id, args.key, report_to_observation(report),
                   realtime=args.realtime,
                   rtfreq=period if args.realtime else None)
            last_upload = now
        except UploadError as exc:
            _log(f"upload failed: {exc}")
    return 0


def _one_shot(args) -> int:
    obs = Observation(**{name: getattr(args, name)
                         for name in _FLOAT_FIELDS + _INT_FIELDS})
    try:
        upload(args.id, args.key, obs,
               realtime=args.realtime,
               rtfreq=args.period if args.realtime else None)
    except UploadError as exc:
        _log(f"upload failed: {exc}")
        return 1
    print("success")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--id", default=os.environ.get("WU_STATION_ID"),
                        help="station ID (default: $WU_STATION_ID)")
    parser.add_argument("--key", default=os.environ.get("WU_STATION_KEY"),
                        help="station key (default: $WU_STATION_KEY)")
    parser.add_argument("--period", type=float, default=300.0,
                        help="min seconds between uploads in pipe mode "
                             "(default: 300)")
    parser.add_argument("--realtime", action="store_true",
                        help="use the rapid-fire endpoint (periods to 2.5s)")
    for name in _FLOAT_FIELDS:
        parser.add_argument(f"--{name}", type=float, default=None)
    for name in _INT_FIELDS:
        parser.add_argument(f"--{name}", type=int, default=None)
    args = parser.parse_args(argv)

    if not args.id or not args.key:
        parser.error("station credentials required: --id/--key or "
                     "WU_STATION_ID/WU_STATION_KEY")

    one_shot = any(getattr(args, name) is not None
                   for name in _FLOAT_FIELDS + _INT_FIELDS)
    return _one_shot(args) if one_shot else _pipe_mode(args)


if __name__ == "__main__":
    sys.exit(main())

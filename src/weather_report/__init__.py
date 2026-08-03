"""The Weather Report contract: the JSON document that joins the console
reader (producer) and the uploaders (consumers). See DESIGN.md.

A report is a plain dict; this module owns its structure, JSONL framing,
and validation. It has no other project dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

SCHEMA = "weather-report/1"

_GROUPS = ("station", "outdoor", "wind", "pressure", "rain", "sun",
           "indoor", "soil", "leaf", "console")


def new_report(station_id: str, *, model: str = "davis-vantage-pro2",
               time_utc: datetime | None = None) -> dict:
    """A skeleton report with every group present and measurements null."""
    now = (time_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "schema": SCHEMA,
        "station": {"id": station_id, "model": model},
        "time_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outdoor": {"temp_f": None, "humidity_pct": None, "dewpoint_f": None,
                    "heat_index_f": None, "wind_chill_f": None,
                    "thsw_index_f": None},
        "wind": {"dir_deg": None, "speed_mph": None, "avg_2min_mph": None,
                 "avg_10min_mph": None, "gust_10min_mph": None,
                 "gust_10min_dir_deg": None},
        "pressure": {"sea_level_inhg": None, "trend": None,
                     "absolute_inhg": None},
        "rain": {"rate_in_hr": None, "last_15min_in": None,
                 "last_hour_in": None, "last_24h_in": None, "day_in": None,
                 "month_in": None, "year_in": None, "storm_in": None,
                 "storm_start": None},
        "sun": {"uv_index": None, "solar_wm2": None, "et_day_in": None},
        "indoor": {"temp_f": None, "humidity_pct": None},
        "soil": {"temp_f": [None] * 4, "moisture_cb": [None] * 4},
        "leaf": {"temp_f": [None] * 4, "wetness": [None] * 4},
        "console": {"battery_v": None, "tx_battery_status": None,
                    "forecast_icons": None, "forecast_rule": None},
    }


def is_valid(report) -> bool:
    """Cheap structural check: right schema, groups are dicts, has a time.

    Consumers must tolerate unknown keys (additive evolution), so this
    checks presence, not exhaustiveness.
    """
    return (
        isinstance(report, dict)
        and report.get("schema") == SCHEMA
        and isinstance(report.get("time_utc"), str)
        and all(isinstance(report.get(g), dict) for g in _GROUPS)
    )


def time_of(report: dict) -> datetime:
    """The acquisition time as an aware UTC datetime."""
    return datetime.strptime(report["time_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)


def dumps_line(report: dict) -> str:
    """One JSONL line, newline included."""
    return json.dumps(report, separators=(",", ":")) + "\n"


def loads_line(line: str) -> dict | None:
    """Parse one JSONL line; None if unparseable or not a valid report."""
    try:
        report = json.loads(line)
    except json.JSONDecodeError:
        return None
    return report if is_valid(report) else None

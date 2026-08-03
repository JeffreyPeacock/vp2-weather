"""Decode Davis LOOP (type 0) and LOOP2 (type 1) packets into dicts, and
merge a LOOP/LOOP2 pair into a Weather Report.

Byte layout per Vantage Serial Protocol v2.6.1 section X (Rev B), same
offsets as the Java reference (DavisLoopData_Type0/Type1). All packets
are 99 bytes: "LOO", bar trend, type byte, ..., LF, CR, CRC16.

"Dashed" console values (sensor absent/lost) become None:
  2-byte temps 32767, humidity 255, solar 32767, UV byte 255,
  offset-90 temp bytes 255, soil moisture / leaf wetness 255,
  wind direction 0 (spec: 0 = no wind data; 360 = north).
Rain counts are clicks assumed to be 0.01 in (US collector).
"""

from __future__ import annotations

from weather_report import new_report

PACKET_SIZE = 99
LOOP_TYPE_OFFSET = 4  # 0 = LOOP, 1 = LOOP2

_BAR_TRENDS = {196: "falling-rapidly", 236: "falling-slowly", 0: "steady",
               20: "rising-slowly", 60: "rising-rapidly"}


def _u16(p: bytes, off: int) -> int:
    return p[off] | (p[off + 1] << 8)


def _s16(p: bytes, off: int) -> int:
    v = _u16(p, off)
    return v - 0x10000 if v >= 0x8000 else v


def _temp10(p: bytes, off: int) -> float | None:
    v = _s16(p, off)
    return None if v == 32767 else v / 10.0


def _temp_whole(p: bytes, off: int) -> int | None:
    v = _s16(p, off)
    return None if v == 32767 else v


def _byte_or_none(p: bytes, off: int) -> int | None:
    return None if p[off] == 255 else p[off]


def _offset90(p: bytes, off: int) -> int | None:
    return None if p[off] == 255 else p[off] - 90


def _wind_dir(p: bytes, off: int) -> int | None:
    v = _u16(p, off)
    return None if v == 0 else v


def _rain100(p: bytes, off: int) -> float:
    return _u16(p, off) / 100.0


def _storm_start(p: bytes, off: int) -> str | None:
    v = _u16(p, off)
    if v in (0xFFFF, 0):
        return None
    month, day, year = v >> 12, (v >> 7) & 0x1F, (v & 0x7F) + 2000
    return f"{year:04d}-{month:02d}-{day:02d}"


def packet_type(packet: bytes) -> int:
    return packet[LOOP_TYPE_OFFSET]


def decode_loop(p: bytes) -> dict:
    """LOOP (type 0): the everything-packet, incl. extra sensor stations."""
    solar = _u16(p, 44)
    uv = p[43]
    return {
        "bar_trend": _BAR_TRENDS.get(p[3]),
        "barometer_inhg": _u16(p, 7) / 1000.0,
        "temp_in_f": _temp10(p, 9),
        "humidity_in_pct": _byte_or_none(p, 11),
        "temp_out_f": _temp10(p, 12),
        "wind_mph": p[14],
        "wind_avg_10min_mph": float(p[15]),
        "wind_dir_deg": _wind_dir(p, 16),
        "humidity_out_pct": _byte_or_none(p, 33),
        "rain_rate_in_hr": _rain100(p, 41),
        "uv_index": None if uv == 255 else uv / 10.0,
        "solar_wm2": None if solar == 32767 else solar,
        "storm_rain_in": _rain100(p, 46),
        "storm_start": _storm_start(p, 48),
        "rain_day_in": _rain100(p, 50),
        "rain_month_in": _rain100(p, 52),
        "rain_year_in": _rain100(p, 54),
        "et_day_in": _u16(p, 56) / 1000.0,
        "soil_temp_f": [_offset90(p, 25 + i) for i in range(4)],
        "leaf_temp_f": [_offset90(p, 29 + i) for i in range(4)],
        "soil_moisture_cb": [_byte_or_none(p, 62 + i) for i in range(4)],
        "leaf_wetness": [_byte_or_none(p, 66 + i) for i in range(4)],
        "tx_battery_status": p[86],
        "console_battery_v": ((_u16(p, 87) * 300) // 512) / 100.0,
        "forecast_icons": p[89],
        "forecast_rule": p[90],
    }


def decode_loop2(p: bytes) -> dict:
    """LOOP2 (type 1): derived values and rolling wind/rain figures."""
    solar = _u16(p, 44)
    uv = p[43]
    return {
        "bar_trend": _BAR_TRENDS.get(p[3]),
        "barometer_inhg": _u16(p, 7) / 1000.0,
        "temp_in_f": _temp10(p, 9),
        "humidity_in_pct": _byte_or_none(p, 11),
        "temp_out_f": _temp10(p, 12),
        "wind_mph": p[14],
        "wind_dir_deg": _wind_dir(p, 16),
        "wind_avg_10min_mph": _u16(p, 18) / 10.0,
        "wind_avg_2min_mph": _u16(p, 20) / 10.0,
        "wind_gust_10min_mph": _u16(p, 22) / 10.0,
        "wind_gust_10min_dir_deg": _wind_dir(p, 24),
        "dewpoint_f": _temp_whole(p, 30),
        "humidity_out_pct": _byte_or_none(p, 33),
        "heat_index_f": _temp_whole(p, 35),
        "wind_chill_f": _temp_whole(p, 37),
        "thsw_index_f": _temp_whole(p, 39),
        "rain_rate_in_hr": _rain100(p, 41),
        "uv_index": None if uv == 255 else uv / 10.0,
        "solar_wm2": None if solar == 32767 else solar,
        "storm_rain_in": _rain100(p, 46),
        "storm_start": _storm_start(p, 48),
        "rain_day_in": _rain100(p, 50),
        "rain_15min_in": _rain100(p, 52),
        "rain_hour_in": _rain100(p, 54),
        "et_day_in": _u16(p, 56) / 1000.0,
        "rain_24h_in": _rain100(p, 58),
        "barometer_abs_inhg": _u16(p, 67) / 1000.0,
    }


def build_report(loop: dict, loop2: dict, station_id: str, *,
                 time_utc=None) -> dict:
    """Merge one LOOP + one LOOP2 decode into a Weather Report.

    Common fields prefer LOOP2 (it is the later firmware's packet and the
    pair is read seconds apart at most); LOOP contributes the extra
    sensor stations, month/year rain, forecast, and battery data.
    """
    r = new_report(station_id, time_utc=time_utc)
    r["outdoor"].update({
        "temp_f": loop2["temp_out_f"], "humidity_pct": loop2["humidity_out_pct"],
        "dewpoint_f": loop2["dewpoint_f"], "heat_index_f": loop2["heat_index_f"],
        "wind_chill_f": loop2["wind_chill_f"], "thsw_index_f": loop2["thsw_index_f"],
    })
    r["wind"].update({
        "dir_deg": loop2["wind_dir_deg"], "speed_mph": loop2["wind_mph"],
        "avg_2min_mph": loop2["wind_avg_2min_mph"],
        "avg_10min_mph": loop2["wind_avg_10min_mph"],
        "gust_10min_mph": loop2["wind_gust_10min_mph"],
        "gust_10min_dir_deg": loop2["wind_gust_10min_dir_deg"],
    })
    r["pressure"].update({
        "sea_level_inhg": loop2["barometer_inhg"], "trend": loop2["bar_trend"],
        "absolute_inhg": loop2["barometer_abs_inhg"],
    })
    r["rain"].update({
        "rate_in_hr": loop2["rain_rate_in_hr"],
        "last_15min_in": loop2["rain_15min_in"],
        "last_hour_in": loop2["rain_hour_in"],
        "last_24h_in": loop2["rain_24h_in"],
        "day_in": loop2["rain_day_in"],
        "month_in": loop["rain_month_in"], "year_in": loop["rain_year_in"],
        "storm_in": loop2["storm_rain_in"], "storm_start": loop2["storm_start"],
    })
    r["sun"].update({
        "uv_index": loop2["uv_index"], "solar_wm2": loop2["solar_wm2"],
        "et_day_in": loop2["et_day_in"],
    })
    r["indoor"].update({
        "temp_f": loop2["temp_in_f"], "humidity_pct": loop2["humidity_in_pct"],
    })
    r["soil"].update({
        "temp_f": loop["soil_temp_f"], "moisture_cb": loop["soil_moisture_cb"],
    })
    r["leaf"].update({
        "temp_f": loop["leaf_temp_f"], "wetness": loop["leaf_wetness"],
    })
    r["console"].update({
        "battery_v": loop["console_battery_v"],
        "tx_battery_status": loop["tx_battery_status"],
        "forecast_icons": loop["forecast_icons"],
        "forecast_rule": loop["forecast_rule"],
    })
    return r

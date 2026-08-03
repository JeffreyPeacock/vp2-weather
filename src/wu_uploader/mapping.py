"""Map a Weather Report document to a Weather Underground Observation.

Field-semantics fixes relative to the Java predecessor (see DESIGN.md):
WU `rainin` means rain accumulated in the last 60 minutes, so it maps
from rain.last_hour_in (the Java sent the instantaneous rate); `dateutc`
carries the report's acquisition time, not the upload time.
"""

from __future__ import annotations

from weather_report import time_of

from .wunderground import Observation


def report_to_observation(report: dict) -> Observation:
    outdoor, wind = report["outdoor"], report["wind"]
    rain, sun = report["rain"], report["sun"]
    indoor, soil, leaf = report["indoor"], report["soil"], report["leaf"]
    return Observation(
        dateutc=time_of(report),
        tempf=outdoor["temp_f"],
        humidity=outdoor["humidity_pct"],
        dewptf=outdoor["dewpoint_f"],
        winddir=wind["dir_deg"],
        windspeedmph=wind["speed_mph"],
        windgustmph=wind["gust_10min_mph"],
        windgustdir=wind["gust_10min_dir_deg"],
        windspdmph_avg2m=wind["avg_2min_mph"],
        windgustmph_10m=wind["gust_10min_mph"],
        windgustdir_10m=wind["gust_10min_dir_deg"],
        baromin=report["pressure"]["sea_level_inhg"],
        rainin=rain["last_hour_in"],
        dailyrainin=rain["day_in"],
        solarradiation=sun["solar_wm2"],
        uv=sun["uv_index"],
        soiltempf=soil["temp_f"][0],
        soilmoisture=soil["moisture_cb"][0],
        leafwetness=leaf["wetness"][0],
        indoortempf=indoor["temp_f"],
        indoorhumidity=indoor["humidity_pct"],
    )

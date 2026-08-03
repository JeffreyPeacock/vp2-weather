"""Weather Underground PWS upload protocol client.

Protocol reference: https://support.weather.com/s/article/PWS-Upload-Protocol
All units are US customary, as the protocol requires: degrees Fahrenheit,
miles per hour, inches of mercury, inches of rain.

A successful upload returns HTTP 200 with the body "success".
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timezone

import requests

STANDARD_URL = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
REALTIME_URL = "https://rtupdate.wunderground.com/weatherstation/updateweatherstation.php"

SOFTWARE_TYPE = "vp2-wu-uploader-0.1"


class UploadError(Exception):
    """Weather Underground rejected the upload or was unreachable."""


@dataclass
class Observation:
    """One weather observation. Every field is optional; only fields that are
    set are sent. Field names match the WU GET parameters exactly (case
    restored at build time where needed)."""

    dateutc: datetime | None = None  # None -> "now" (server-side timestamp)
    tempf: float | None = None
    humidity: float | None = None            # outdoor RH, 0-100
    dewptf: float | None = None
    winddir: int | None = None               # instantaneous, degrees 0-360
    windspeedmph: float | None = None
    windgustmph: float | None = None
    windgustdir: int | None = None
    windspdmph_avg2m: float | None = None    # 2-min average wind
    windgustmph_10m: float | None = None     # 10-min gust max
    windgustdir_10m: int | None = None
    baromin: float | None = None             # sea-level pressure, inHg
    rainin: float | None = None              # rain in the past 60 min
    dailyrainin: float | None = None         # since local midnight
    solarradiation: float | None = None      # W/m^2
    uv: float | None = None                  # sent as "UV"
    soiltempf: float | None = None
    soilmoisture: int | None = None          # 0-100
    leafwetness: int | None = None           # 0-15
    indoortempf: float | None = None
    indoorhumidity: float | None = None

    def to_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.dateutc is None:
            params["dateutc"] = "now"
        else:
            utc = self.dateutc.astimezone(timezone.utc)
            params["dateutc"] = utc.strftime("%Y-%m-%d %H:%M:%S")
        for f in fields(self):
            if f.name == "dateutc":
                continue
            value = getattr(self, f.name)
            if value is None:
                continue
            name = "UV" if f.name == "uv" else f.name
            params[name] = f"{value:g}" if isinstance(value, float) else str(value)
        return params


def upload(
    station_id: str,
    station_key: str,
    observation: Observation,
    *,
    realtime: bool = False,
    rtfreq: float | None = None,
    timeout: float = 15.0,
    session: requests.Session | None = None,
) -> None:
    """Send one observation. Raises UploadError on any failure.

    realtime=True uses the rapid-fire endpoint (updates as often as every
    2.5 s); rtfreq is the intended update period in seconds.
    """
    params: dict[str, str] = {
        "ID": station_id,
        "PASSWORD": station_key,
        "action": "updateraw",
        "softwaretype": SOFTWARE_TYPE,
        **observation.to_params(),
    }
    url = STANDARD_URL
    if realtime:
        url = REALTIME_URL
        params["realtime"] = "1"
        params["rtfreq"] = f"{rtfreq or 2.5:g}"

    http = session or requests
    try:
        resp = http.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise UploadError(f"request failed: {exc}") from exc

    body = resp.text.strip()
    if resp.status_code != 200 or body.lower() != "success":
        raise UploadError(f"HTTP {resp.status_code}: {body!r}")

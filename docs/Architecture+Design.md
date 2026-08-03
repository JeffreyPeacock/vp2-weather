# Architecture + Design: Davis VP2 → Weather Underground

This document records the architecture and the decisions behind it —
hardware and software. The narrative background is in the root
`README.md`; hands-on hardware steps are in `BSv2-Setup.md`.

## System overview

```
┌─────────────┐   3.3V TTL    ┌──────────────┐   Bluetooth   ┌─────────────────────────┐
│ VP2 console │───UART,19200──│ BlueSMiRF v2 │───SPP─────────│ laptop                  │
│ (expansion  │               │ (ESP32)      │               │  /dev/rfcomm0           │
│  port)      │               │              │               │  vp2-read | wu-upload   │
└─────────────┘               └──────────────┘               └─────────────────────────┘
                                                                        │ HTTPS GET
                                                                        ▼
                                                              Weather Underground (PWS)
```

## Hardware architecture

The console's expansion port exposes its serial port 0 at 0–3.3V TTL,
19200 8N1. A SparkFun BlueSMiRF v2 wires directly to it (no level
shifting, no resistors) and bridges the UART to Bluetooth SPP; the
laptop binds it to an rfcomm device. Full pinout, wiring, and
configuration: `BSv2-Setup.md`; primary sources are archived in this
directory (see References).

## Software architecture

Two independent programs joined by a documented JSON contract,
composable as a shell pipeline:

```
vp2-read --port /dev/rfcomm0 --interval 60  |  wu-upload
└──────────────┬──────────────┘                └───────┬────────┘
        module 1: reader                    module 2: WU uploader
    (owns all Davis protocol)            (owns all WU protocol)
                        │
              "Weather Report" JSONL
         (one JSON document per line, stdout→stdin)
```

Either side can be replaced or multiplied without touching the other:
`vp2-read | tee -a wx.jsonl | wu-upload`, a future CWOP/APRS uploader,
a replay tool feeding archived JSONL, etc.

### Logical components

| Component | Package | CLI | Responsibility |
|---|---|---|---|
| Weather Report schema | `weather_report` | — | The shared contract: document structure, JSONL framing, validation. Depends on nothing. |
| Console reader | `vantage_reader` | `vp2-read` | Serial comms with the DVP2 console (wakeup, `LPS 3`, CRC), decode LOOP/LOOP2, merge each pair into one Weather Report, emit JSONL on stdout. Logs to stderr only — stdout is data. |
| WU uploader | `wu_uploader` | `wu-upload` | Consume Weather Reports from stdin (or one-shot flags), map to PWS-protocol params, throttle, upload, report failures. |

### Physical layout (one repo, one installed distribution, three packages)

```
src/
  weather_report/__init__.py     # schema constant, build/validate/serialize
  vantage_reader/
    crc.py                       # Davis CRC-16 (CRC-16/XMODEM)
    packets.py                   # LOOP (type 0) / LOOP2 (type 1) byte decoding
    console.py                   # VantageConsole: port, wake, commands, LPS pairs
    cli.py                       # vp2-read
  wu_uploader/
    wunderground.py              # WU PWS client (Observation, upload)
    mapping.py                   # Weather Report → Observation
    cli.py                       # wu-upload
```

They ship in one wheel (`vp2-weather`) for convenience; the dependency
arrows only point inward to `weather_report`, so splitting into
separate distributions later is mechanical.

## The Weather Report document (`weather-report/1`)

One report per line (JSON Lines). Field groups; every measurement is
either a number or `null` (sensor absent / value "dashed" by the
console). Units are embedded in key names. Example:

```json
{"schema": "weather-report/1",
 "station": {"id": "sensorcast-weather-002", "model": "davis-vantage-pro2"},
 "time_utc": "2026-08-02T20:20:37Z",
 "outdoor": {"temp_f": 45.9, "humidity_pct": 47, "dewpoint_f": 27,
             "heat_index_f": 45, "wind_chill_f": 44, "thsw_index_f": null},
 "wind": {"dir_deg": 134, "speed_mph": 2, "avg_2min_mph": 4.6,
          "avg_10min_mph": 3.1, "gust_10min_mph": 11.0, "gust_10min_dir_deg": 135},
 "pressure": {"sea_level_inhg": 30.16, "trend": "steady", "absolute_inhg": 24.65},
 "rain": {"rate_in_hr": 0.0, "last_15min_in": 0.0, "last_hour_in": 0.0,
          "last_24h_in": 0.0, "day_in": 0.0, "month_in": 0.1, "year_in": 4.2,
          "storm_in": 0.0, "storm_start": null},
 "sun": {"uv_index": 2.5, "solar_wm2": 512, "et_day_in": 0.012},
 "indoor": {"temp_f": 72.3, "humidity_pct": 25},
 "soil": {"temp_f": [45, null, null, null], "moisture_cb": [39, null, null, null]},
 "leaf": {"temp_f": [null, null, null, null], "wetness": [0, null, null, null]},
 "console": {"battery_v": 4.71, "tx_battery_status": 0,
             "forecast_icons": 6, "forecast_rule": 45}}
```

Contract rules:

1. `schema` is mandatory; consumers must ignore documents whose major
   schema they don't understand, and must tolerate unknown keys
   (additive evolution only within `/1`).
2. `time_utc` is the acquisition time (when the LOOP pair was read),
   ISO-8601 UTC — not upload time.
3. `null` means "not available"; keys are always present so consumers
   can be dumb.
4. stdout carries only reports; all diagnostics go to stderr.

## Reader design (module 1)

Direct port of the working Java driver (`VantagePro2Driver.java` in the
sensorcast project) against the Davis *Vantage Serial Protocol* v2.6.1:

- Port: 19200 8N1, no flow control (default `/dev/rfcomm0`; the Java
  ran on `/dev/rfcomm2`).
- Wake: send `\n`, expect `\n\r`, ≤3 attempts, then `TEST` sanity check.
- Acquire: `LPS 3 2\n`, wait ACK (0x06), read two 99-byte packets
  (align on the `"LOO"` prefix; byte 4 discriminates LOOP=0 / LOOP2=1),
  verify CRC and discard corrupt packets.
- Merge: LOOP contributes soil/leaf/extra sensors, month/year rain,
  forecast, battery; LOOP2 contributes dewpoint/heat-index/wind-chill,
  2-min/10-min wind stats, 15-min/1-h/24-h rain, absolute pressure;
  common fields prefer LOOP2.
- Emit one report every `--interval` seconds (default 60); reconnect
  with backoff on serial errors.

## Uploader design (module 2)

- Pipe mode (default when stdin is not a TTY): read JSONL, drop
  documents that don't validate, throttle to `--period` seconds
  (default 300 — WU's standard endpoint), map via `mapping.py`, upload.
  `--realtime` switches to the rapid-fire endpoint and allows periods
  down to 2.5 s.
- One-shot mode (measurement flags given): a single observation from
  CLI flags, for testing without a console.
- Failures: log to stderr and keep consuming; upload errors never
  propagate backpressure to the reader.
- WU protocol: HTTPS GET `updateweatherstation.php`, `action=updateraw`,
  success = HTTP 200 with body `success`.

## Decision log

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Replace the lost XBee pair with a BlueSMiRF v2 | Single radio instead of two; laptop side is plain Bluetooth; BSv2 verified working desktop↔laptop |
| D2 | No level shifting or series resistors on the console hookup | Console port is 0–3.3V TTL (DeKay), BSv2 is 3.3V logic; both DeKay's and af4ex's builds wired direct |
| D3 | BSv2 UART pinned to 19200 8N1 (`AT-SerialSpeed=19200`, saved to NVM) | Console's rate; BSv2 factory default of 115200 was the silent failure of the first hookup attempt |
| D4 | Two processes joined by a pipe, not a monolith | The Java monolith's blocking WU upload stalled serial reading; separate processes isolate failure domains and compose (`tee`, replay, more consumers) |
| D5 | Contract is JSON Lines over stdout/stdin ("Weather Report", `weather-report/1`) | Human-readable, greppable, archivable; language-neutral; versioned for additive evolution |
| D6 | Units are US customary with units in key names (`temp_f`, `sea_level_inhg`) | Native units of both the Davis console and the WU protocol — no conversions to get wrong; names make units unambiguous |
| D7 | `null` = dashed/absent; keys always present | Console "dashed" sentinels (32767, 255, dir 0) are normalized once, in the reader; consumers stay dumb |
| D8 | `time_utc` = acquisition time | The Java stamped upload time (bug); replay/backfill needs real sample times |
| D9 | CRC-failed packets are dropped | The Java logged CRC errors but used the corrupt packet anyway |
| D10 | UV byte decoded as tenths of an index (25 → 2.5) | Matches weewx and the console display; the Java's whole-index reading was never exercised (its `uv ≤ 15` filter) |
| D11 | WU `rainin` ← `rain.last_hour_in` | WU defines `rainin` as accumulation over 60 min; the Java sent the instantaneous rate |
| D12 | Upload throttle default 300 s; `--realtime` for rapid-fire | The Java uploaded every ~4 s unthrottled to the standard endpoint |
| D13 | Credentials via `$WU_STATION_ID`/`$WU_STATION_KEY`, never in source | The Java hardcoded live WU credentials in `StandaloneStation.java` |
| D14 | One wheel, three packages, deps point only at `weather_report` | Convenience now, mechanical split later |
| D15 | Rain click size assumed 0.01 in (US collector) | Matches this station; if the collector is ever 0.2 mm, `packets.py` is the single place to fix |

## References

Archived in this directory:

- `VantageSerialProtocolDocs_v261.pdf` (also v2.30, v2.50) — the Davis
  serial protocol: commands, LOOP/LOOP2 layout, CRC.
- `6152_62_53_63_SS.pdf` — VP2 console spec sheet.
- `VP2_Fan_Aspirated_ISS_Rev_C.pdf` — ISS spec sheet.
- `wxforum-topic-10721-vantage-console-pinout-p2.pdf` — capture of
  wxforum topic 10721 page 2 (af4ex's XBee build, replies #25–49),
  including the expansion-connector pinout diagram and cable photos.

External — the console hack lineage:

- MadScientistLabs, *Davis WeatherLink Software Not Required* (Jan 2011) —
  DeKay's original discovery of direct 3.3V serial on the expansion port:
  <https://madscientistlabs.blogspot.com/2011/01/davis-weatherlink-software-not-required.html>
- wxforum topic 10721, *Vantage Vue Console logger pinout* — af4ex's XBee
  wireless build (replies #25–49; source of the archived PDF above):
  <https://www.wxforum.net/index.php?topic=10721.msg104689#msg104689>
- DeKay's DavisRFM69 wiki, Hardware Hacks — index of console interface
  hacks, incl. the firmware ≥3.0 authentic-logger restriction:
  <https://github.com/dekay/DavisRFM69/wiki/Hardware-Hacks>

External — Davis documentation:

- Vantage Serial Protocol reference, v2.30 mirror (local copies of
  v2.30/2.50/2.61 are archived in this directory):
  <https://wiki.greengaragedetroit.com/images/e/e4/VantageSerialProtocolDocs_v230.pdf>
- Vantage Pro/Pro2 Serial Communication Reference Manual (ManualsLib):
  <https://www.manualslib.com/manual/586601/Davis-Vantage-Pro.html>
- Vantage Pro2 Console User Manual (ManualsLib):
  <https://www.manualslib.com/manual/35985/Davis-Vantage-Pro2.html>

External — hardware (SparkFun):

- BlueSMiRF v2 hookup guide: <https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/>
  — esp. hardware overview
  (<https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/hardware_overview/>)
  and AT command reference
  (<https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/at_commands/>);
  firmware/hardware repo: <https://github.com/sparkfun/SparkFun_BlueSMiRF-v2>
- FTDI Basic Breakout 5V: <https://www.sparkfun.com/sparkfun-ftdi-basic-breakout-5v.html>
  and 3.3V: <https://www.sparkfun.com/sparkfun-ftdi-basic-breakout-3-3v.html>
  — the 3.3V variant is DeKay's wired-hookup adapter; either configures the BSv2.
- *Exploring XBees and XCTU* — configuration of the original XBee S1 link
  this project replaces:
  <https://learn.sparkfun.com/tutorials/exploring-xbees-and-xctu>

External — Weather Underground upload protocol:

- PWS Upload Protocol (official):
  <https://support.weather.com/s/article/PWS-Upload-Protocol?language=en_US>
- meteodrenthe, *Uploading to the Weather Underground API* — readable
  parameter walkthrough (the official page is a JS-only portal):
  <https://blog.meteodrenthe.nl/2021/12/27/uploading-to-the-weather-underground-api/>
- ccgruber/updateweatherstation — endpoint emulation, parameter/response
  cross-reference:
  <https://github.com/ccgruber/updateweatherstation/blob/master/updateweatherstation.php>

Local:

- Java predecessor: `~/Workspace/Sensorcast/sensorcast-main/sensorcast-vantage-pro2`
  (`VantagePro2Driver.java`, `WundergroundUpdater.java`, `DavisLoopData_Type0/1.java`)

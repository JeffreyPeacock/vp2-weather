# Davis Vantage Pro 2 — Bluetooth link + Weather Underground pipeline

A wireless bridge from a Davis Vantage Pro 2 weather station console to
a laptop, and a small Python pipeline that publishes the station's data
to Weather Underground:

```
VP2 console ── BlueSMiRF v2 ── Bluetooth ── vp2-read | wu-upload ── Weather Underground
```

## Background

Davis consoles have always had the data; what Davis sold separately —
at a premium — was the WeatherLink datalogger needed to get it out. In
January 2011, DeKay (MadScientistLabs) published the workaround that
this whole lineage builds on: the console's 2x10 expansion connector
exposes its serial port directly at 0–3.3V TTL, 19200 8N1, so a 3.3V
USB-serial adapter and three wires replace the dongle for live data
("[Davis WeatherLink Software Not Required](https://madscientistlabs.blogspot.com/2011/01/davis-weatherlink-software-not-required.html)").
Weeks later, John/af4ex extended it wirelessly with a pair of XBee
radios plugged into that same connector
([wxforum topic 10721](https://www.wxforum.net/index.php?topic=10721.msg104689#msg104689),
archived with the pinout diagram in
[`docs/wxforum-topic-10721-vantage-console-pinout-p2.pdf`](docs/wxforum-topic-10721-vantage-console-pinout-p2.pdf)).

This station ran that XBee arrangement, feeding a Java application
(`sensorcast-vantage-pro2`, in `~/Workspace/Sensorcast/`) that spoke
the Davis serial protocol over `/dev/rfcomm2`, logged everything, and
uploaded to both a private Sensorcast server and Weather Underground.
It ran reliably through 2017–2018 and then wound down; the Sensorcast
server is gone, and the XBee modules were eventually lost.

This project is the revival, with two substitutions:

- **Hardware**: the XBee pair is replaced by a single SparkFun
  BlueSMiRF v2 on the console side — the laptop's own Bluetooth is the
  other half of the link.
- **Software**: the Java monolith is replaced by two small Python
  programs joined by a documented JSON contract, so the pieces can run,
  fail, and evolve independently.

## The hardware

The BlueSMiRF v2 wires directly to the console's expansion connector —
both sides are 3.3V logic, so there is no level shifting and there are
no resistors (a lesson inherited from DeKay's and af4ex's builds). The
one non-obvious step, and the cause of the classic
"powers up but no data" symptom: the BSv2's UART defaults to 115200
baud and must be reconfigured to the console's 19200. The complete
recipe — parts, factory reset, AT commands, pin-by-pin wiring,
troubleshooting — is in [`docs/BSv2-Setup.md`](docs/BSv2-Setup.md).

On the laptop, the paired radio is bound once per boot to an rfcomm
device (`sudo rfcomm bind 0 <BSv2-address>`) and from then on it's an
ordinary serial port.

## The software

Two programs, one contract (design and decision log in
[`docs/Architecture+Design.md`](docs/Architecture+Design.md)):

- **`vp2-read`** owns the Davis side: it wakes the console, requests
  alternating LOOP/LOOP2 packets (`LPS 3`), verifies CRCs, decodes and
  merges each pair, and writes one "Weather Report" JSON document per
  line to stdout. Diagnostics go to stderr; stdout is data only.
- **`wu-upload`** owns the Weather Underground side: it reads Weather
  Reports from stdin, throttles (default one upload per 5 minutes), maps
  fields to the PWS upload protocol, and uploads. Failures are logged
  and skipped, never stalling the reader.

The Weather Report is deliberately boring: JSON Lines, US-customary
units embedded in the key names (`temp_f`, `sea_level_inhg`), `null`
for anything the console "dashed", and the acquisition timestamp in
UTC. Boring is the point — it can be `tee`'d to a monthly archive file,
replayed later for backfill, or fed to some future uploader without
touching the reader.

The Java application remains the reference implementation this port was
checked against, with a handful of deliberate fixes recorded in the
decision log: corrupt packets are dropped rather than used, WU's
`rainin` gets last-hour accumulation rather than the instantaneous
rate, timestamps are acquisition time rather than upload time, and
credentials live in the environment rather than the source.

## Running it

```sh
# one-time setup
python -m venv .venv && . .venv/bin/activate   # or: uv venv
pip install -e '.[dev]'
pytest

# credentials (from wunderground.com → My Devices)
export WU_STATION_ID=KXXXXXXXX
export WU_STATION_KEY=xxxxxxxx

# the pipeline
vp2-read --port /dev/rfcomm0 --station-id my-vp2 --interval 60 | wu-upload
```

Useful variations:

```sh
vp2-read --port /dev/rfcomm0 --count 1          # smoke test: one report
vp2-read ... | tee -a wx-$(date +%Y-%m).jsonl | wu-upload   # archive + upload
wu-upload --tempf 70.2 --humidity 55            # test WU creds, no console
cat archive.jsonl | wu-upload --period 0        # replay/backfill
```

## Repository map

| Path | What |
|---|---|
| `src/weather_report/` | the Weather Report contract (`weather-report/1`) |
| `src/vantage_reader/` | Davis serial protocol → reports (`vp2-read`) |
| `src/wu_uploader/` | reports → Weather Underground (`wu-upload`) |
| `tests/` | CRC, packet-decode, schema, and mapping tests |
| `docs/BSv2-Setup.md` | hardware: attach the BlueSMiRF v2 to the console |
| `docs/Architecture+Design.md` | architecture, contract spec, decisions D1–D15 |
| `docs/*.pdf` | Davis serial protocol manuals (v2.30/2.50/2.61), console and ISS spec sheets, archived pinout thread |
| `CLAUDE.md` | terse working notes for AI-assisted sessions |

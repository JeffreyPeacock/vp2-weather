# CLAUDE.md

Davis Vantage Pro 2 console → BlueSMiRF v2 (Bluetooth) → laptop pipeline
that publishes to Weather Underground. Python 3.12, hatchling, distribution
`vp2-weather`.

## Commands

```sh
uv venv && uv pip install -e '.[dev]'   # or python -m venv + pip
.venv/bin/pytest tests/ -q              # all tests must pass
scripts/vp2-read --port /dev/rfcomm0 --count 1   # one Weather Report
scripts/vp2-read --port /dev/rfcomm0 | scripts/wu-upload   # full pipeline
```

Executables live in `scripts/` (bash launchers that use the project venv;
also `bsv2-config.py`, `vp2-probe.py`). Do NOT add [project.scripts]
entry points — Jeff wants no project scripts generated into .venv/bin.

WU credentials come from `$WU_STATION_ID` / `$WU_STATION_KEY` — never
hardcode them (the Java predecessor did; that's decision D13).

## Layout

- `src/weather_report/` — the JSONL contract (`weather-report/1`). No deps.
- `src/vantage_reader/` — Davis serial protocol (`vp2-read`). Depends on
  `weather_report` + pyserial.
- `src/wu_uploader/` — WU PWS upload (`wu-upload`). Depends on
  `weather_report` + requests.
- `docs/` — Davis protocol PDFs, archived pinout thread PDF,
  `BSv2-Setup.md` (hardware), `Architecture+Design.md` (decisions D1–D15).

## Hard facts (verified; don't re-derive)

- Console serial: **19200 8N1, 0–3.3V TTL**, LF wakeup (expect `\n\r`,
  ≤3 tries), commands UPPERCASE. `LPS 3 n` streams alternating
  LOOP/LOOP2 99-byte packets; byte 4 is the type (0/1); CRC-16/XMODEM
  over the whole packet checks to 0.
- BlueSMiRF v2 must be configured to 19200 (`$$$`, `AT-SerialSpeed=19200`,
  `ATW`) — factory default is 115200 and yields silent no-data.
- Console expansion pinout (from back): TXD0=pin 6, RXD0=pin 5,
  VCC=13/14, GND=15/16. Console TXD0 → BSv2 RXI.
- Deliberate deviations from the Java reference (not bugs): UV decoded
  as tenths; WU `rainin` = last-hour accumulation; CRC-failed packets
  dropped. See the decision log before "fixing" any of these.
- Java reference implementation:
  `~/Workspace/Sensorcast/sensorcast-main/sensorcast-vantage-pro2`
  (NOT `~/Workspace/sensorcast-vantage-pro2` — that's a gutted skeleton
  holding only old logs).

## Conventions

- `vp2-read` stdout is data only (JSONL reports); all logging to stderr.
- Weather Report evolution is additive-only within `/1`; consumers
  tolerate unknown keys, keys are always present, `null` = unavailable.
- Tests build synthetic spec-conformant packets (see
  `tests/test_vantage_reader.py::_blank_packet`) — extend those rather
  than checking in binary fixtures.

# BlueSMiRF v2 → Davis Vantage Pro 2 Console Setup

Goal: replace the lost XBee S1 pair with a single SparkFun BlueSMiRF v2 (BSv2)
so the VP2 console's serial data reaches a laptop over Bluetooth.

```
VP2 console expansion port ──(3.3V TTL UART)── BSv2 ──(Bluetooth SPP)── laptop COM port
```

## Why this works with no level shifting

- The console expansion-port serial lines are **0–3.3V TTL** (DeKay,
  MadScientistLabs). A normal RS-232 port (±12V) would damage it; a 3.3V
  radio wires straight in.
- The BSv2 is **3.3V logic** (ESP32 Pico Mini) with 3.3–5V tolerant TX/RX
  and a 3.3–5V VCC input (AP2112K regulator).
- Neither DeKay's wired FTDI hookup nor af4ex's XBee build used any series
  resistors, pull-ups, or level shifters. **None are needed here either.**

## Bill of materials

| Item | Purpose |
|------|---------|
| SparkFun BlueSMiRF v2 (WRL-23287 PTH / WRL-24113 headers / WRL-24112 JST) | The Bluetooth-UART bridge |
| FTDI Basic Breakout **3.3V** (or 5V — BSv2 TX/RX are 5V tolerant) | One-time BSv2 configuration from a PC |
| 2mm-pitch header sockets (e.g. SparkFun PRT-10030) | Mate with the console's 2x10 2mm expansion connector (af4ex's method: cut sockets apart for individual pins) |
| Hookup wire + heat shrink | af4ex: "I'll guarantee short circuits if you don't use it" |

## Step 1 — Factory-reset the BSv2 (unknown state → baseline)

No serial access needed:

1. Power the BSv2 normally (do **not** hold PAIR during power-up — that is
   bootloader mode).
2. Press and hold **PAIR**. At 4–8 s the Status/Connect LEDs blink back and
   forth slowly (pairing mode — keep holding).
3. Past **8 s** they blink quickly — **release now** → factory reset.

Baseline after reset: **115200 baud, 8N1, flow control off, all Bluetooth
pairings erased.**

## Step 2 — Set the BSv2 UART to 19200 baud (the critical step)

The console talks **19200 8N1**; the BSv2 factory default is **115200**.
This mismatch produces exactly the observed symptom: power but no data.
(af4ex had the same step with XBees: default 9600 → reconfigure to 19200.)

1. Plug the BSv2 onto the FTDI Basic. The BSv2 6-pin header
   (RTS, RXI, TXO, VCC, CTS, GND) mates pin-for-pin with the FTDI Basic —
   the crossover is built in.
2. Open a terminal on the FTDI port at **115200**.
3. **Within ~60 s of power-up** (command-mode window, `AT-MaxCommandTimeMs`):

   ```
   $$$                    → OK
   AT-SerialSpeed=19200
   ATW                    (save to NVM)
   ATX                    (exit command mode)
   ```

4. Verify: re-pair the laptop over Bluetooth, reopen the FTDI terminal at
   **19200**, and confirm characters pass both ways (same as the
   desktop↔laptop bench test, but at the new rate). Any remaining problem
   at the console is then wiring, not the radio.

### Alternative: configure over Bluetooth (no FTDI, radio stays on the console)

The BSv2 also accepts `$$$` from the Bluetooth side, but only within the
same 60-second window after power-on (firmware checks
`millis() < maxCommandTime_ms`; escapes are also ignored until there's
been 2 s of serial silence — automatic here, the console is quiet unless
polled). Order matters because the factory reset erases pairings:

1. Radio attached to the console and powered; factory-reset it (Step 1).
2. Pair the desktop with the radio — no deadline on this step.
3. Bind it once: `sudo rfcomm bind 0 <bt-addr>`.
4. Power-cycle the radio (pull console power or the VCC wire) to restart
   the 60-second window, then immediately run
   [`scripts/bsv2-config.py`](../scripts/bsv2-config.py) — it opens
   `/dev/rfcomm0` (which triggers the reconnect), knocks with `$$$`
   until command mode opens, then sets 19200, saves, and exits.

Changing the UART speed over Bluetooth does not drop the Bluetooth
connection — the two sides are independent.

## Step 3 — Wire the BSv2 to the console expansion port

Four wires to serial port 0 on the 2x10, 2mm-pitch expansion connector.
Pin numbers below are **as seen from the back of the unit**, per the
expansion-connector pinout diagram captured in
`wxforum-topic-10721-vantage-console-pinout-p2.pdf` (page 4). Even pins
are the top row (20, 18, … 2), odd pins the bottom row (19, 17, … 1):

```
 top:  20=NC 18=DC-IN 16=GND 14=VCC 12=TXD1 10=PE3 8=PC4 6=TXD0 4=MISO 2=SCK
 bot:  19=NC 17=PB4   15=GND 13=VCC 11=RXD1  9=PE2 7=RST 5=RXD0 3=MOSI 1=SS
```

| BSv2 pin | Console pin | af4ex wire color | Note |
|----------|-------------|------------------|------|
| VCC | **13 or 14** (Vcc 3.3V) | red | Battery works too, but the radio's draw shortens battery life; run the console on its AC adapter |
| GND | **15 or 16** (GND) | black | Required — no common ground, no data, ever |
| **RXI** | **6 (TXD0)** | blue | Console transmit → radio input |
| **TXO** | **5 (RXD0)** | green | Radio output → console receive |

af4ex: TX/RX crossover is where "most common wiring errors occur." BSv2 pin
names are from the *radio's* perspective; console names are from the
*console's*. Output always feeds input.

Leave BSv2 RTS/CTS unconnected (flow control is off by default,
`AT-FlowControl=0`).

TXD1/RXD1 on the connector are unused (DeKay: dead — likely factory test).

## Step 4 — Talk to the console

Pair the laptop with the BSv2 and open its Bluetooth COM port (baud on this
side is irrelevant; only the BSv2's wired UART rate matters).

The console **sleeps** to save power. Protocol basics (Davis *Vantage
Serial Protocol* doc; MadScientistLabs):

1. Wake: send a bare `\n` (LF), wait ~1.2 s for `\n\r` back; retry up to 3x.
2. Commands are **UPPERCASE**, terminated with `\n`:
   - `TEST` → echoes `TEST` (sanity check)
   - `VER` → firmware date code; `NVER` → version string
   - `LOOP 1` → one binary LOOP packet (live weather data, CRC-checked)
   - `STRMON` / `STRMOFF` → raw streaming on/off
3. Weewx/Cumulus configured for a "Vantage, serial" on the Bluetooth COM
   port handle all of this automatically.

## Troubleshooting checklist

1. Baud: BSv2 UART = 19200 (Step 2), and console baud setting still 19200
   (it may have been changed in the XBee days — check console setup mode).
2. TX/RX swapped — swapping is harmless, try it.
3. Common ground present.
4. Data only after wakeup — a silent console may just be asleep; software
   must send the `\n` wakeup.
5. Console firmware ≥3.0 refuses serial without an authentic-logger
   handshake — only relevant if the console firmware was updated since the
   XBee rig worked.
6. Avoid sending `$$$` patterns from the laptop within the first 60 s of
   BSv2 power-up (command-mode escape).

## References

- MadScientistLabs, *Davis WeatherLink Software Not Required* (Jan 2011):
  <https://madscientistlabs.blogspot.com/2011/01/davis-weatherlink-software-not-required.html>
- af4ex XBee build, wxforum topic 10721 (Reply #26+):
  <https://www.wxforum.net/index.php?topic=10721.msg104689#msg104689>
- DeKay's DavisRFM69 wiki, Hardware Hacks:
  <https://github.com/dekay/DavisRFM69/wiki/Hardware-Hacks>
- BlueSMiRF v2 hookup guide: <https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/>
  (hardware overview, AT commands)
- Davis *Vantage Serial Protocol* reference (v2.3.0 mirror):
  <https://wiki.greengaragedetroit.com/images/e/e4/VantageSerialProtocolDocs_v230.pdf>
- SparkFun *Exploring XBees and XCTU* (for the old rig):
  <https://learn.sparkfun.com/tutorials/exploring-xbees-and-xctu>

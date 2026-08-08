# docs/

Reference documentation for this project. Two of these documents were
written here; the rest **came from external sources and are copied here
for convenience** — so the project remains buildable and debuggable even
if the originals move or disappear. All copyrights remain with their
respective owners (Davis Instruments Corp., wxforum.net and its posters,
et al.). **No copyright infringement is intended**; copies are retained
solely for personal reference and interoperability. If you are a rights
holder and want a copy removed, open an issue and it will be taken down.

## Written for this project

| File | What |
|---|---|
| `Architecture+Design.md` | system architecture, the Weather Report contract, decision log D1–D15 |
| `BSv2-Setup.md` | hardware guide: attaching the BlueSMiRF v2 to the VP2 console |

## Copied from external sources

| File | What | Source |
|---|---|---|
| `wxforum-topic-10721-vantage-console-pinout-p2.pdf` | archival capture (2026-08-02) of wxforum topic 10721 page 2 — af4ex's XBee console interface build, replies #25–49, incl. the expansion-connector pinout diagram | <https://www.wxforum.net/index.php?topic=10721.msg104689#msg104689> |
| `6152_62_53_63_SS.pdf` | Vantage Pro2 station spec sheet (models 6152/6162/6153/6163) | Davis Instruments; originally <http://www.davisnet.com/product_documents/weather/spec_sheets/6152_62_53_63_SS.pdf> |
| `SparkFun_BlueSMiRF-v2_Hookup_Guide.pdf` | archival capture (2026-08-07) of the SparkFun BlueSMiRF v2 hookup guide, single-page edition — hardware overview, pinout, AT commands, examples | <https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/single_page/>; section links: [hardware overview](https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/hardware_overview/), [AT commands](https://docs.sparkfun.com/SparkFun_BlueSMiRF-v2/at_commands/); firmware/hardware repo: <https://github.com/sparkfun/SparkFun_BlueSMiRF-v2>; product page: <https://www.sparkfun.com/sparkfun-bluesmirf-v2.html> |
| `VantageSerialProtocolDocs_v261.pdf` | Davis *Vantage Serial Protocol* reference, rev 2.6.1 (2013) | Davis Instruments; originally <http://www.davisnet.com/support/weather/download/VantageSerialProtocolDocs_v261.pdf> (now via <https://www.davisinstruments.com/pages/support>) |
| `VantageSerialProtocolDocs_v250.pdf` | same, rev 2.5.0 | Davis Instruments, same download area as above |
| `VantageSerialProtocolDocs_v230.pdf` | same, rev 2.3.0 | Davis Instruments; a public mirror: <https://wiki.greengaragedetroit.com/images/e/e4/VantageSerialProtocolDocs_v230.pdf> |
| `VP2_Fan_Aspirated_ISS_Rev_C.pdf` | VP2 fan-aspirated ISS spec sheet, rev C | Davis Instruments; originally <http://www.davisnet.com/product_documents/weather/spec_sheets/VP2_Fan_Aspirated_ISS_Rev_C.pdf> |

Notes:

- The Davis PDFs were carried over from the predecessor project
  (`sensorcast-vantage-pro2`, ca. 2011–2017), which downloaded them from
  `davisnet.com`; that domain has since been folded into
  `davisinstruments.com`, so the original URLs are historical.
- The wxforum capture is a rendered snapshot (styles and images inlined)
  of the live page, made because the thread is this project's primary
  wiring reference and forum content of that age has a habit of
  vanishing.
- The BlueSMiRF v2 hookup guide capture is a rendered snapshot of
  SparkFun's live documentation site (their docs repo carries the
  license terms); the live site remains the authoritative version.

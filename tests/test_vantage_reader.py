import struct

from vantage_reader import crc, packets
from weather_report import is_valid, time_of


def test_crc16_is_xmodem():
    # Davis CRC-16 == CRC-16/XMODEM; standard check value for "123456789"
    assert crc.crc16(b"123456789") == 0x31C3


def test_crc_of_packet_with_trailing_crc_is_zero():
    body = bytes(range(97))
    packet = body + struct.pack(">H", crc.crc16(body))
    assert crc.check(packet)
    assert not crc.check(packet[:-1] + b"\x00")


def _blank_packet(kind: int) -> bytearray:
    p = bytearray(99)
    p[0:3] = b"LOO"
    p[3] = 0  # bar trend: steady
    p[4] = kind
    p[95], p[96] = 0x0A, 0x0D
    # everything "dashed" where a sentinel exists
    struct.pack_into("<h", p, 9, 32767)   # inside temp
    struct.pack_into("<h", p, 12, 32767)  # outside temp
    p[11] = p[33] = 255                   # humidities
    p[43] = 255                           # UV
    struct.pack_into("<H", p, 44, 32767)  # solar
    struct.pack_into("<H", p, 48, 0xFFFF)  # storm start
    for i in range(18, 33):               # extra/soil/leaf temp bytes
        p[i] = 255
    for i in range(62, 70):               # soil moisture / leaf wetness
        p[i] = 255
    return p


def _sealed(p: bytearray) -> bytes:
    struct.pack_into(">H", p, 97, crc.crc16(bytes(p[:97])))
    return bytes(p)


def test_decode_loop_fields_and_sentinels():
    p = _blank_packet(0)
    struct.pack_into("<H", p, 7, 30160)   # barometer 30.16
    struct.pack_into("<h", p, 12, 459)    # 45.9 F
    p[33] = 47                            # humidity
    p[14] = 2                             # wind mph
    struct.pack_into("<H", p, 16, 134)    # wind dir
    struct.pack_into("<H", p, 50, 12)     # day rain 0.12
    struct.pack_into("<H", p, 52, 100)    # month rain 1.00
    p[25] = 45 + 90                       # soil temp 1
    p[62] = 39                            # soil moisture 1
    d = packets.decode_loop(_sealed(p))
    assert d["barometer_inhg"] == 30.16
    assert d["temp_out_f"] == 45.9
    assert d["humidity_out_pct"] == 47
    assert d["wind_mph"] == 2 and d["wind_dir_deg"] == 134
    assert d["rain_day_in"] == 0.12 and d["rain_month_in"] == 1.0
    assert d["soil_temp_f"] == [45, None, None, None]
    assert d["soil_moisture_cb"] == [39, None, None, None]
    # dashed sentinels
    assert d["temp_in_f"] is None and d["humidity_in_pct"] is None
    assert d["uv_index"] is None and d["solar_wm2"] is None
    assert d["storm_start"] is None
    assert d["bar_trend"] == "steady"


def test_decode_loop2_fields():
    p = _blank_packet(1)
    struct.pack_into("<h", p, 30, 27)     # dew point
    struct.pack_into("<H", p, 20, 46)     # 2-min avg 4.6
    struct.pack_into("<H", p, 22, 110)    # 10-min gust 11.0
    struct.pack_into("<H", p, 24, 135)    # gust dir
    struct.pack_into("<H", p, 54, 25)     # last hour rain 0.25
    p[43] = 25                            # UV 2.5
    struct.pack_into("<H", p, 44, 512)    # solar
    d = packets.decode_loop2(_sealed(p))
    assert d["dewpoint_f"] == 27
    assert d["wind_avg_2min_mph"] == 4.6
    assert d["wind_gust_10min_mph"] == 11.0
    assert d["wind_gust_10min_dir_deg"] == 135
    assert d["rain_hour_in"] == 0.25
    assert d["uv_index"] == 2.5 and d["solar_wm2"] == 512


def test_storm_start_date_decoding():
    p = _blank_packet(0)
    # month=8 (bits 15-12), day=2 (bits 11-7), year offset 26 (bits 6-0)
    struct.pack_into("<H", p, 48, (8 << 12) | (2 << 7) | 26)
    assert packets.decode_loop(_sealed(p))["storm_start"] == "2026-08-02"


def test_build_report_merges_pair():
    loop_p = _blank_packet(0)
    struct.pack_into("<H", loop_p, 52, 100)  # month rain 1.00
    loop2_p = _blank_packet(1)
    struct.pack_into("<h", loop2_p, 12, 459)
    struct.pack_into("<H", loop2_p, 54, 25)  # last hour 0.25
    report = packets.build_report(packets.decode_loop(_sealed(loop_p)),
                                  packets.decode_loop2(_sealed(loop2_p)),
                                  "test-station")
    assert is_valid(report)
    assert report["station"]["id"] == "test-station"
    assert report["outdoor"]["temp_f"] == 45.9      # from LOOP2
    assert report["rain"]["month_in"] == 1.0        # from LOOP
    assert report["rain"]["last_hour_in"] == 0.25   # from LOOP2
    assert time_of(report).tzinfo is not None

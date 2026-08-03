from datetime import timezone

from weather_report import dumps_line, loads_line, new_report
from wu_uploader.mapping import report_to_observation


def _sample_report():
    r = new_report("test-station")
    r["outdoor"].update({"temp_f": 45.9, "humidity_pct": 47, "dewpoint_f": 27})
    r["wind"].update({"dir_deg": 134, "speed_mph": 2, "avg_2min_mph": 4.6,
                      "gust_10min_mph": 11.0, "gust_10min_dir_deg": 135})
    r["pressure"]["sea_level_inhg"] = 30.16
    r["rain"].update({"rate_in_hr": 0.5, "last_hour_in": 0.02, "day_in": 0.1})
    r["indoor"].update({"temp_f": 72.3, "humidity_pct": 25})
    r["soil"]["temp_f"][0] = 45
    r["soil"]["moisture_cb"][0] = 39
    r["leaf"]["wetness"][0] = 0
    return r


def test_jsonl_roundtrip():
    r = _sample_report()
    assert loads_line(dumps_line(r)) == r


def test_loads_line_rejects_garbage():
    assert loads_line("not json\n") is None
    assert loads_line('{"schema": "something-else/9"}\n') is None


def test_mapping_fixes_java_bugs():
    obs = report_to_observation(_sample_report())
    # rainin is last-hour accumulation, NOT the instantaneous rate
    assert obs.rainin == 0.02
    # dateutc is the acquisition time from the report, not "now"/upload time
    assert obs.dateutc is not None and obs.dateutc.tzinfo == timezone.utc


def test_mapping_field_parity():
    obs = report_to_observation(_sample_report())
    params = obs.to_params()
    assert params["tempf"] == "45.9"
    assert params["windspdmph_avg2m"] == "4.6"
    assert params["windgustmph_10m"] == "11"
    assert params["windgustdir_10m"] == "135"
    assert params["soiltempf"] == "45"
    assert params["soilmoisture"] == "39"
    assert params["leafwetness"] == "0"
    assert params["indoortempf"] == "72.3"
    # unset sensors are simply absent
    assert "solarradiation" not in params and "UV" not in params

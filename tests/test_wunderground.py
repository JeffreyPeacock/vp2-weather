from datetime import datetime, timezone

import pytest

from wu_uploader.wunderground import Observation, UploadError, upload


def test_default_dateutc_is_now():
    assert Observation().to_params() == {"dateutc": "now"}


def test_explicit_dateutc_formatted_utc():
    ts = datetime(2026, 8, 2, 10, 32, 35, tzinfo=timezone.utc)
    assert Observation(dateutc=ts).to_params()["dateutc"] == "2026-08-02 10:32:35"


def test_only_set_fields_sent_and_uv_case():
    params = Observation(tempf=70.2, winddir=230, uv=3.0).to_params()
    assert params == {
        "dateutc": "now",
        "tempf": "70.2",
        "winddir": "230",
        "UV": "3",
    }


class _FakeResponse:
    def __init__(self, status_code=200, text="success\n"):
        self.status_code = status_code
        self.text = text


class _FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        return self.response


def test_upload_success_builds_expected_request():
    session = _FakeSession(_FakeResponse())
    upload("KCASANFR5", "secret", Observation(tempf=70.0), session=session)
    url, params = session.calls[0]
    assert "weatherstation.wunderground.com" in url
    assert params["ID"] == "KCASANFR5"
    assert params["PASSWORD"] == "secret"
    assert params["action"] == "updateraw"
    assert params["tempf"] == "70"


def test_upload_realtime_endpoint_and_params():
    session = _FakeSession(_FakeResponse())
    upload("ID", "KEY", Observation(), realtime=True, rtfreq=10, session=session)
    url, params = session.calls[0]
    assert "rtupdate.wunderground.com" in url
    assert params["realtime"] == "1"
    assert params["rtfreq"] == "10"


def test_upload_failure_raises():
    session = _FakeSession(_FakeResponse(text="INVALIDPASSWORDID"))
    with pytest.raises(UploadError):
        upload("ID", "KEY", Observation(), session=session)

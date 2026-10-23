"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from OCCTO, with
    a fake system information service that answers the requests of the
    information download screen as the real one does.
"""

import datetime
import json
from typing import ClassVar

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import occto

SCREEN_PAGE = """
<form id="mainForm" method="post" action="/public/dfw/RP11/OCCTO/SD/CF01S010C">
  <input type="hidden" name="requestToken" value="first-token">
  <input type="hidden" name="fwExtention.actionType" value="reference">
  <input type="hidden" name="fwExtention.actionSubType" value="init">
  <input type="radio" name="areaDataKnd" value="01" checked>
  <input type="text" name="areaNngpFrom">
  <input type="checkbox" name="kns" value="06">
  <input type="checkbox" name="areaSum" value="11" checked>
  <select name="monthCd2"><option value="01">1</option></select>
  <input type="button" name="csvBtn" value="CSV">
</form>
"""

CSV = (
    "年月日,時間帯,北海道,関西,１０エリア計\n"
    "2024/01/01,00:00～01:00,3811,11820.484,\n"
    "2024/01/01,01:00～02:00,3917,11405.202,\n"
    "2024/01/01,日電力量(MWh),7728,23225.686,\n"
    "2024/01/01,日最大電力(MW),3917,11820.484,\n"
).encode("cp932")


class _FakeResponse:
    """A response of the service."""

    def __init__(self, content, content_type="text/html"):
        self.content = (
            content.encode() if isinstance(content, str) else content
        )
        self.text = self.content.decode("utf-8", errors="replace")
        self.headers = {"content-type": content_type}

    def raise_for_status(self):
        """Do nothing: the fake responses succeed."""

    def json(self):
        """
        Get the content as JSON.

        Returns
        -------
        dict
            The content.
        """
        return json.loads(self.text)


class _FakeSession:
    """A session of the service, which keeps the forms it receives."""

    forms: ClassVar[list[dict]] = []
    refuse = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, **_):
        """
        Get the menu.

        Returns
        -------
        _FakeResponse
            The menu.
        """
        assert url.endswith("LOGIN_login")
        return _FakeResponse("menu")

    def post(self, url, data, headers=None, **_):
        """
        Answer the screen, the checks and the download.

        Returns
        -------
        _FakeResponse
            The response of the service.
        """
        if "pathInfo" in url:
            assert data == {}
            return _FakeResponse(SCREEN_PAGE)
        form = dict(data)
        _FakeSession.forms.append(form)
        action = form["fwExtention.actionSubType"]
        if action == "download":
            assert "sdReqType" not in headers
            if form.get("requestToken") != "second-token":
                return _FakeResponse("不正なリクエストです。")
            return _FakeResponse(CSV, "application/octet-stream")
        assert headers == {"sdReqType": "AJAX"}
        error = ["error"] if _FakeSession.refuse else None
        header = (
            {
                "downloadKey": {"name": "downloadKey", "value": "key"},
                "requestToken": {
                    "name": "requestToken",
                    "value": "second-token",
                },
            }
            if action == "ok"
            else {}
        )
        return _FakeResponse(
            json.dumps(
                {"root": {"errMessage": error, "bizRoot": {"header": header}}}
            )
        )


@pytest.fixture
def fake_service(monkeypatch):
    """
    Replace the service of OCCTO with the fake one.

    Returns
    -------
    type[_FakeSession]
        The fake session, with the forms it received.
    """
    _FakeSession.forms = []
    _FakeSession.refuse = False
    monkeypatch.setattr(occto.requests, "Session", _FakeSession)
    return _FakeSession


def test_get_available_requests():
    """Test that the requests are the years of the data."""
    requests = occto.get_available_requests(
        "JPN_Kansai", datetime.date(2016, 4, 1), datetime.date(2018, 3, 1)
    )

    assert requests == [
        (pd.Timestamp("2016-04-01"), pd.Timestamp("2017-01-01")),
        (pd.Timestamp("2017-01-01"), pd.Timestamp("2018-01-01")),
        (pd.Timestamp("2018-01-01"), pd.Timestamp("2018-03-01")),
    ]


def test_download_and_extract_data_for_request(fake_service, assert_demand):
    """Test that the hours of an area are read, at their ends."""
    time_series = occto.download_and_extract_data_for_request(
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")), "JPN_Kansai"
    )

    # The hours end in Japanese time, 9 hours ahead of UTC.
    assert_demand(
        time_series,
        "Asia/Tokyo",
        {"2023-12-31 16:00": 11820.484, "2023-12-31 17:00": 11405.202},
    )
    # The form has the daily demand of the year and the area, and the
    # download sends the key and token of the confirmation.
    print_form, ok_form, download_form = fake_service.forms
    assert print_form["areaDataKnd"] == occto.DAILY_DEMAND
    assert print_form["areaNngpFrom"] == "2024/01/01"
    assert print_form["areaNngpTo"] == "2024/12/31"
    assert print_form["kns"] == "06"
    assert print_form["areaSum"] == "11"
    assert print_form["monthCd2"] == "01"
    assert "csvBtn" not in print_form
    assert [
        form["fwExtention.actionSubType"] for form in fake_service.forms
    ] == [
        "print",
        "ok",
        "download",
    ]
    assert ok_form["requestToken"] == "first-token"
    assert download_form["downloadKey"] == "key"
    assert download_form["requestToken"] == "second-token"


def test_download_refused(fake_service):
    """Test that an error of the service stops the retrieval."""
    fake_service.refuse = True

    with pytest.raises(ValueError, match="OCCTO refused the download"):
        occto.download_and_extract_data_for_request(
            (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
            "JPN_Kansai",
        )


@pytest.mark.usefixtures("fake_service")
def test_download_without_the_file(monkeypatch):
    """Test that a page instead of the file stops the retrieval."""

    class _Session(_FakeSession):
        def post(self, url, data, headers=None, **kwargs):
            if "pathInfo" not in url and (
                dict(data)["fwExtention.actionSubType"] == "download"
            ):
                return _FakeResponse("不正なリクエストです。")
            return super().post(url, data, headers, **kwargs)

    monkeypatch.setattr(occto.requests, "Session", _Session)

    with pytest.raises(ValueError, match="gave a page instead of the file"):
        occto.download_and_extract_data_for_request(
            (pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")),
            "JPN_Kansai",
        )

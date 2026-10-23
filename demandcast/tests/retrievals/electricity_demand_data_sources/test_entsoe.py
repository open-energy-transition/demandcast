"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ENTSO-E.
"""

import datetime
import traceback
import zoneinfo
from unittest.mock import patch

import pandas as pd
import pytest
import requests
import utils.config
from entsoe.exceptions import NoMatchingDataError
from entsoe.mappings import Area
from retrievals.electricity_demand_data_sources import entsoe


def test_get_available_requests():
    """Test that the requests are periods of one year at most."""
    requests = entsoe.get_available_requests(
        "BEL", datetime.date(2014, 11, 24), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (
        pd.Timestamp("2014-11-24"),
        pd.Timestamp("2015-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-01-01"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 12


# entsoe-py parses the XML of the responses with the HTML parser.
@pytest.mark.filterwarnings("ignore::bs4.XMLParsedAsHTMLWarning")
def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that the actual load is read and marks the ends of steps."""
    monkeypatch.setenv("ENTSOE_API_KEY", "test-key")
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)
    fake_downloads.serve("https://web-api.tp.entsoe.eu/api", "entsoe.xml")

    time_series = entsoe.download_and_extract_data_for_request(
        (pd.Timestamp("2024-03-31 00:00"), pd.Timestamp("2024-03-31 02:00")),
        "BEL",
    )

    # The client of ENTSO-E asks for the actual total load of Belgium.
    assert {
        "documentType": "A65",
        "processType": "A16",
        "outBiddingZone_Domain": "10YBE----------2",
        "periodStart": "202403310000",
        "periodEnd": "202403310200",
        "securityToken": "test-key",
    }.items() <= fake_downloads.requests[0][2]["params"].items()
    # The response is in UTC, and the client converts it to the time of
    # Brussels, where daylight saving time starts at 01:00 UTC. The
    # times are the starts of the 15 minutes, which move 15 minutes
    # later to mark their ends.
    assert_demand(
        time_series,
        "Europe/Brussels",
        {
            "2024-03-31 00:15": 8000.25,
            "2024-03-31 00:30": 7900.5,
            "2024-03-31 00:45": 7800.75,
            "2024-03-31 01:00": 7700.0,
            "2024-03-31 01:15": 7650.25,
            "2024-03-31 01:30": 7600.5,
            "2024-03-31 01:45": 7550.75,
            "2024-03-31 02:00": 7500.0,
        },
    )


@pytest.mark.filterwarnings("ignore::bs4.XMLParsedAsHTMLWarning")
def test_download_and_extract_data_for_request_with_change_of_time_step(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that each time moves to the end of its own time step."""
    monkeypatch.setenv("ENTSOE_API_KEY", "test-key")
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)
    # Poland changed from hourly to 15-minute data on 13 June 2024. The
    # 15-minute period has a single point, which holds for the whole
    # period, since its curve leaves out the repeated values.
    fake_downloads.serve(
        "https://web-api.tp.entsoe.eu/api", "entsoe_change_of_time_step.xml"
    )

    time_series = entsoe.download_and_extract_data_for_request(
        (pd.Timestamp("2024-06-12 21:00"), pd.Timestamp("2024-06-13 01:00")),
        "POL",
    )

    # The hours end one hour after their starts, and the 15 minutes 15
    # minutes after theirs.
    assert_demand(
        time_series,
        "Europe/Warsaw",
        {
            "2024-06-12 22:00": 17700.5,
            "2024-06-12 23:00": 16600.25,
            "2024-06-13 00:00": 15900.75,
            "2024-06-13 00:15": 15500.5,
            "2024-06-13 00:30": 15500.5,
            "2024-06-13 00:45": 15500.5,
            "2024-06-13 01:00": 15500.5,
        },
    )


@pytest.mark.parametrize("api_key", [None, ""])
def test_download_and_extract_data_for_request_without_api_key(
    monkeypatch, api_key
):
    """Test that the error says how to set a missing or empty key."""
    monkeypatch.delenv("ENTSOE_API_KEY", raising=False)
    if api_key is not None:
        monkeypatch.setenv("ENTSOE_API_KEY", api_key)
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)

    with pytest.raises(ValueError, match="ENTSOE_API_KEY"):
        entsoe.download_and_extract_data_for_request(
            (pd.Timestamp("2024-03-31"), pd.Timestamp("2024-04-01")), "BEL"
        )


@pytest.mark.parametrize(
    ("code", "domain"),
    [("GBR_GB", "10YGB----------A"), ("GBR_NIR", "10Y1001A1001A016")],
)
@pytest.mark.filterwarnings("ignore::bs4.XMLParsedAsHTMLWarning")
def test_download_and_extract_data_for_request_of_area(
    fake_downloads, monkeypatch, code, domain
):
    """Test that the subdivisions of the UK ask for their own areas."""
    monkeypatch.setenv("ENTSOE_API_KEY", "test-key")
    # Ignore a local .env file with a real key.
    monkeypatch.setattr(utils.config, "load_dotenv", lambda **_: None)
    fake_downloads.serve("https://web-api.tp.entsoe.eu/api", "entsoe.xml")

    time_series = entsoe.download_and_extract_data_for_request(
        (pd.Timestamp("2024-03-31 00:00"), pd.Timestamp("2024-03-31 02:00")),
        code,
    )

    params = fake_downloads.requests[0][2]["params"]
    assert params["outBiddingZone_Domain"] == domain
    assert not time_series.empty


@pytest.mark.parametrize(
    ("code", "times", "expected"),
    [
        # The winter times of Northern Ireland are an hour late, not
        # those of its summer.
        (
            "GBR_NIR",
            ["2024-01-15 12:00", "2024-07-15 12:00"],
            ["2024-01-15 11:00", "2024-07-15 12:00"],
        ),
        # The summer of 2018 of Ukraine is an hour late, and its winter
        # of 2018 to 2019 an hour early.
        (
            "UKR",
            ["2018-07-01 12:00", "2018-10-28 00:30", "2018-10-28 01:00"],
            ["2018-07-01 11:00", "2018-10-27 23:30", "2018-10-28 02:00"],
        ),
        # When the summer of 2018 starts, its first hour moves onto the
        # hour before it, which is kept once.
        (
            "UKR",
            ["2018-03-25 00:30", "2018-03-25 01:30", "2018-03-25 02:30"],
            ["2018-03-25 00:30", "2018-03-25 01:30"],
        ),
        # The times of other countries stay as they are.
        ("FRA", ["2024-01-15 12:00"], ["2024-01-15 12:00"]),
    ],
)
def test_correct_times(code, times, expected):
    """Test that the times that are wrong on ENTSO-E are corrected."""
    time_series = pd.Series(
        range(len(times)), index=pd.DatetimeIndex(times, tz="UTC")
    )

    corrected = entsoe._correct_times(time_series, code)

    times = pd.DatetimeIndex(corrected.index).tz_convert("UTC")
    assert times.strftime("%Y-%m-%d %H:%M").tolist() == expected


def test_fetch_demand():
    """
    Test fetching demand data from ENTSOE.

    This test mocks the EntsoePandasClient to return a pandas.Series
    with a time series of demand data.
    """
    # Define a mock series to simulate demand data.
    mock_series = pd.Series(
        [1, 2], index=pd.date_range("2023-01-01", periods=2, freq="h")
    )

    # Patch the EntsoePandasClient to return the mock series.
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.return_value = pd.DataFrame(
            {"Actual Load": mock_series}
        )

        # Test fetching demand data for a valid country code.
        result = entsoe._fetch_demand(
            "dummy",
            "FRA",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)

        # Test with a country code that is added manually.
        result = entsoe._fetch_demand(
            "dummy",
            "XKX",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)

        # Test with an area of ENTSO-E in place of the country.
        entsoe._fetch_demand(
            "dummy",
            "GBR_NIR",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
            area="GB_NIR",
        )
        assert mock_client.return_value.query_load.call_args.args[0] == (
            "GB_NIR"
        )


def test_fetch_demand_errors():
    """
    Test fetching demand data from ENTSOE with errors.

    This test mocks the EntsoePandasClient to raise a connection error
    and NoMatchingDataError, and checks that the _fetch_demand
    function lets the client retry the first and skips the second.
    """
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        # Test the EntsoePandasClient to raise a connection error after
        # its retries.
        mock_client.return_value.query_load.side_effect = (
            requests.exceptions.ConnectionError("Connection failed")
        )
        with pytest.raises(requests.exceptions.ConnectionError):
            entsoe._fetch_demand(
                "dummy",
                "FRA",
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
                retries=2,
                retry_delay=0,
            )
        mock_client.assert_called_once_with(
            api_key="dummy", retry_count=2, retry_delay=0
        )

        # Test the EntsoePandasClient to raise NoMatchingDataError.
        mock_client.return_value.query_load.side_effect = NoMatchingDataError(
            "No data"
        )
        result = entsoe._fetch_demand(
            "dummy",
            "FRA",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)
        assert result.empty


def _query_load_failing(status_code: int):
    """
    Make a query of the load that fails on 2025-10-09 with an error.

    Returns
    -------
    Callable
        The query, which gives a load of 1 MW a day, and raises the
        error for the periods with 2025-10-09, and no data in December.
    """

    def query_load(_area, start, end):
        if start <= pd.Timestamp("2025-10-09", tz="UTC") < end:
            response = requests.Response()
            response.status_code = status_code
            raise requests.exceptions.HTTPError("Error", response=response)
        if start >= pd.Timestamp("2025-12-01", tz="UTC"):
            raise NoMatchingDataError
        times = pd.date_range(start, end, freq="D", inclusive="left")
        return pd.DataFrame({"Actual Load": 1.0}, index=times)

    return query_load


def test_fetch_demand_with_failing_days(caplog):
    """Test that the days that ENTSO-E fails to give are left out."""
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            400
        )
        result = entsoe._fetch_demand(
            "dummy",
            "CYP",
            pd.Timestamp("2025-09-01", tz="UTC"),
            pd.Timestamp("2026-01-01", tz="UTC"),
        )

    # The period is split into months, and October into days, so only
    # 2025-10-09 is left out, and December has no data.
    assert len(result) == 30 + 30 + 30
    assert pd.Timestamp("2025-10-09", tz="UTC") not in result.index
    assert "2025-10-09 00:00:00+00:00" in caplog.text
    assert "left out" in caplog.text

    # A period whose only day fails gives no data.
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            400
        )
        result = entsoe._fetch_demand(
            "dummy",
            "CYP",
            pd.Timestamp("2025-10-09", tz="UTC"),
            pd.Timestamp("2025-10-10", tz="UTC"),
        )
    assert result.empty


def test_fetch_demand_with_other_errors():
    """Test that an error of ENTSO-E other than 400 is raised."""
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            500
        )
        with pytest.raises(requests.exceptions.HTTPError):
            entsoe._fetch_demand(
                "dummy",
                "CYP",
                pd.Timestamp("2025-09-01", tz="UTC"),
                pd.Timestamp("2025-11-01", tz="UTC"),
            )


def test_time_zones_of_entsoe_areas():
    """
    Test that the time zones of the areas of ENTSO-E can be read.

    The client of ENTSO-E gives old names, such as Europe/Kiev, which
    the time zones of some systems leave out, so they are read from the
    package tzdata.
    """
    unknown = []
    for area in Area:
        try:
            zoneinfo.ZoneInfo(area.tz)
        except zoneinfo.ZoneInfoNotFoundError:
            unknown.append(area.tz)

    assert unknown == []


def test_fetch_demand_errors_without_api_key():
    """Test that the errors of ENTSO-E do not show the API key."""
    # The key is made when the test runs, since the tracebacks of recent
    # versions of Python show the source of the test.
    api_key = "-".join(["secret", "key"])
    with patch.object(entsoe, "EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = (
            requests.exceptions.ConnectionError(
                f"Max retries exceeded with url: /api?securityToken={api_key}"
            )
        )
        with pytest.raises(requests.exceptions.ConnectionError) as error:
            entsoe._fetch_demand(
                api_key,
                "FRA",
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
            )

    # The error and its traceback do not have the API key.
    traceback_text = "".join(traceback.format_exception(error.value))
    assert api_key not in traceback_text
    assert "securityToken=***" in traceback_text

"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the Wholesale Electricity Market (WEM).
"""

import datetime

import pandas as pd
import pytest
import utils.fetcher
from retrievals.electricity_demand_data_sources import aemo_wem

DAILY_URL = (
    "https://data.wa.aemo.com.au/public/market-data/wemde/"
    "operationalDemandWithdrawal/dailyFiles/"
    "OperationalDemandAndWithdrawal_2025-01-{:02d}.json"
)


def test_get_available_requests():
    """Test that the requests are years, then months after 2023."""
    requests = aemo_wem.get_available_requests(
        "AUS_WA", datetime.date(2006, 9, 20), datetime.date(2025, 12, 28)
    )

    assert requests[:2] == [(True, 2006, None, None), (True, 2007, None, None)]
    assert requests[17:19] == [
        (True, 2023, None, None),
        (False, 2023, 10, None),
    ]
    # The last month, after the end date, is requested until it.
    assert requests[-2:] == [(False, 2025, 11, None), (False, 2025, 12, 28)]
    assert len(requests) == 18 + 27


def test_get_available_requests_of_the_last_week():
    """Test that a month ending in the last week has its last day."""
    requests = aemo_wem.get_available_requests(
        "AUS_WA", datetime.date(2006, 9, 20), datetime.date(2026, 1, 5)
    )

    assert requests[-3:] == [
        (False, 2025, 11, None),
        (False, 2025, 12, 31),
        (False, 2026, 1, 5),
    ]


def test_download_and_extract_data_for_request_before_reform(
    fake_downloads, assert_demand
):
    """Test that the timestamps are in AWST, UTC+8 all year."""
    # Perth trialled daylight saving from 3 December 2006 at 02:00.
    fake_downloads.serve(
        "https://data.wa.aemo.com.au/datafiles/operational-demand/"
        "operational-demand-2006.csv",
        "aemo_wem_2006.csv",
    )

    time_series = aemo_wem.download_and_extract_data_for_request(
        (True, 2006, None, None), "AUS_WA"
    )

    # The timestamps mark the end of the 30-minute trading intervals.
    assert_demand(
        time_series,
        "UTC",
        {
            "2006-12-02 18:30": 1500.5,
            "2006-12-02 19:00": 1490.0,
            "2006-12-10 06:30": 2500.25,
        },
    )


def test_download_and_extract_data_with_dpv_before_reform(
    fake_downloads, assert_demand
):
    """Test that the distributed solar is added from its first value."""
    fake_downloads.serve(
        "https://data.wa.aemo.com.au/datafiles/operational-demand/"
        "operational-demand-2020.csv",
        "aemo_wem_2020.csv",
    )
    fake_downloads.serve(
        aemo_wem.DATA_FILES_URL + "distributed-pv/distributed-pv-2020.csv",
        "aemo_wem_dpv_2020.csv",
    )

    time_series = aemo_wem.download_and_extract_data_for_request(
        (True, 2020, None, None), "AUS_WA"
    )

    # The interval before the first estimate, at 05:30, keeps its
    # operational demand, the intervals with an estimate get it added,
    # and the interval at 12:30 without one is left out.
    assert_demand(
        time_series,
        "UTC",
        {
            "2020-11-03 22:00": 1700.5,
            "2020-11-03 22:30": 1758.5,
            "2020-11-04 04:30": 2400.25,
        },
    )


def test_download_and_extract_data_for_request_after_reform(
    fake_downloads, assert_demand, monkeypatch
):
    """Test that a month gets the distributed solar of 5 minutes."""
    monkeypatch.setattr(
        aemo_wem,
        "_get_trading_days",
        lambda *_: [pd.Timestamp("2025-01-15")],
    )
    fake_downloads.serve(DAILY_URL.format(15), "aemo_wem_2025-01-15.json")
    fake_downloads.serve(
        aemo_wem.DATA_FILES_URL
        + "estimated-dpv-csv/distributed-pv-new-2025.csv",
        "aemo_wem_dpv_new_2025.csv",
    )

    time_series = aemo_wem.download_and_extract_data_for_request(
        (False, 2025, 1, None), "AUS_WA"
    )

    # The starts of the 5-minute intervals move to their ends, with the
    # estimate of the same interval added.
    assert_demand(
        time_series,
        "UTC",
        {"2025-01-15 00:05": 2900.75, "2025-01-15 00:10": 2930.5},
    )


@pytest.mark.usefixtures("frozen_now")
def _fetch_without_day(monkeypatch, missing_day):
    """
    Serve empty files, except the daily file of a day, which is missing.

    Returns
    -------
    list[str]
        The URLs fetched.
    """
    fetched = []

    def fetch(url, *_args, **_kwargs):
        fetched.append(url)
        if url.endswith(f"-{missing_day:02d}.json"):
            raise utils.fetcher.DataNotFoundError("HTTP error 404")
        return pd.DataFrame(
            {
                "operationalDemand": [],
                "dispatchInterval": [],
                "Timestamp": [],
                "Estimated DPV Generation(MW)": [],
            }
        )

    monkeypatch.setattr(aemo_wem.utils.fetcher, "fetch_dataframe", fetch)
    return fetched


@pytest.mark.parametrize(
    ("request_", "missing_day", "skipped"),
    [
        ((False, 2025, 12, 31), 24, True),
        ((False, 2025, 12, 31), 23, False),
        ((False, 2025, 11, None), 30, False),
    ],
)
def test_download_and_extract_data_with_missing_day(
    monkeypatch, request_, missing_day, skipped
):
    """Test that only the missing days of the last week are skipped."""
    _fetch_without_day(monkeypatch, missing_day)

    if skipped:
        time_series = aemo_wem.download_and_extract_data_for_request(
            request_, "AUS_WA"
        )
        assert time_series.empty
    else:
        with pytest.raises(utils.fetcher.DataNotFoundError):
            aemo_wem.download_and_extract_data_for_request(request_, "AUS_WA")


@pytest.mark.parametrize("now", ["2025-12-03", "2026-03-01"])
def test_requests_do_not_depend_on_today(monkeypatch, now):
    """Test that a request gets the same days whenever it is run."""
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp(now)
    )
    fetched = _fetch_without_day(monkeypatch, 2)

    aemo_wem.download_and_extract_data_for_request(
        (False, 2025, 12, 2), "AUS_WA"
    )

    assert [url[-7:-5] for url in fetched if url.endswith(".json")] == [
        "01",
        "02",
    ]


def test_get_trading_days():
    """Test that the trading days are those of the month until a day."""
    # The reform is on 2023-10-01.
    assert len(aemo_wem._get_trading_days(2025, 12, None)) == 31
    assert aemo_wem._get_trading_days(2026, 1, 2)[-1] == pd.Timestamp(
        "2026-01-02"
    )
    assert aemo_wem._get_trading_days(2023, 10, None)[0] == pd.Timestamp(
        "2023-10-01"
    )


def test_download_and_extract_data_without_month():
    """Test that a request after the reform needs its month."""
    with pytest.raises(ValueError, match="month"):
        aemo_wem.download_and_extract_data_for_request(
            (False, 2025, None, None), "AUS_WA"
        )

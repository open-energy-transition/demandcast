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
    assert requests[-1] == (False, 2025, 12, None)
    assert len(requests) == 18 + 27


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
@pytest.mark.parametrize("day", [1, 30])
def test_download_and_extract_data_with_missing_day(monkeypatch, day):
    """Test that only a missing day of the last week is left out."""
    # Today is 2026-01-02 in the tests.
    month = (2025, 12) if day == 30 else (2025, 11)
    monkeypatch.setattr(
        aemo_wem,
        "_get_trading_days",
        lambda *_: [pd.Timestamp(year=month[0], month=month[1], day=day)],
    )

    def fetch(*_args, **_kwargs):
        raise utils.fetcher.DataNotFoundError("HTTP error 404")

    monkeypatch.setattr(aemo_wem.utils.fetcher, "fetch_dataframe", fetch)

    if day == 30:
        time_series = aemo_wem.download_and_extract_data_for_request(
            (False, *month, None), "AUS_WA"
        )
        assert time_series.empty
    else:
        with pytest.raises(utils.fetcher.DataNotFoundError):
            aemo_wem.download_and_extract_data_for_request(
                (False, *month, None), "AUS_WA"
            )


@pytest.mark.usefixtures("frozen_now")
def test_get_trading_days():
    """Test that the trading days are those of the month until today."""
    # Today is 2026-01-02 in the tests, and the reform is on 2023-10-01.
    assert len(aemo_wem._get_trading_days(2025, 12)) == 31
    assert aemo_wem._get_trading_days(2026, 1)[-1] == pd.Timestamp(
        "2026-01-02"
    )
    assert aemo_wem._get_trading_days(2023, 10)[0] == pd.Timestamp(
        "2023-10-01"
    )


def test_download_and_extract_data_without_month():
    """Test that a request after the reform needs its month."""
    with pytest.raises(ValueError, match="month"):
        aemo_wem.download_and_extract_data_for_request(
            (False, 2025, None, None), "AUS_WA"
        )

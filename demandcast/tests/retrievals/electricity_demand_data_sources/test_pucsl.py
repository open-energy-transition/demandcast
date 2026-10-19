"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from PUCSL.
"""

import datetime

import pandas as pd
from retrievals.electricity_demand_data_sources import pucsl


def test_get_available_requests():
    """Test that the requests are the weeks of the data."""
    requests = pucsl.get_available_requests(
        "LKA", datetime.date(2023, 1, 1), datetime.date(2025, 12, 28)
    )

    assert requests[0] == (
        pd.Timestamp("2023-01-01"),
        pd.Timestamp("2023-01-08"),
    )
    assert requests[-1] == (
        pd.Timestamp("2025-12-21"),
        pd.Timestamp("2025-12-28"),
    )
    assert len(requests) == 156


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the dispatch of all power plants is summed."""
    fake_downloads.serve(
        "https://gendata.pucsl.gov.lk/api/actual-system-dispatch?"
        "dateAggregation=15min&from=2025-12-21T00:00:00.000Z"
        "&to=2025-12-28T00:00:00.000Z",
        "pucsl.json",
    )

    time_series = pucsl.download_and_extract_data_for_request(
        (pd.Timestamp("2025-12-21"), pd.Timestamp("2025-12-28")), "LKA"
    )

    # The times mark the end of each quarter of an hour.
    assert_demand(
        time_series,
        "Asia/Colombo",
        {"2025-12-21 00:15": 300.75, "2025-12-21 00:30": 110.0},
    )


def test_download_and_extract_data_without_dispatch(
    fake_downloads, assert_demand, tmp_path
):
    """Test that a time without any dispatch has no demand."""
    # The rooftop solar has no dispatch at night, and the latest time is
    # not published yet, without the dispatch of any plant.
    file_path = tmp_path / "pucsl.json"
    file_path.write_text(
        '{"data": ['
        '{"reportTimestamp": "2025-12-21T00:00:00.000Z", '
        '"powerPlantId": 1, "dispatchValueInMW": 300.5},'
        '{"reportTimestamp": "2025-12-21T00:00:00.000Z", '
        '"powerPlantId": 68, "dispatchValueInMW": null},'
        '{"reportTimestamp": "2025-12-21T00:15:00.000Z", '
        '"powerPlantId": 1, "dispatchValueInMW": null},'
        '{"reportTimestamp": "2025-12-21T00:15:00.000Z", '
        '"powerPlantId": 68, "dispatchValueInMW": null}'
        '], "message": "ok"}',
        encoding="utf-8",
    )
    fake_downloads.serve(
        "https://gendata.pucsl.gov.lk/api/actual-system-dispatch?"
        "dateAggregation=15min&from=2025-12-21T00:00:00.000Z"
        "&to=2025-12-28T00:00:00.000Z",
        file_path,
    )

    time_series = pucsl.download_and_extract_data_for_request(
        (pd.Timestamp("2025-12-21"), pd.Timestamp("2025-12-28")), "LKA"
    )

    assert_demand(
        time_series.dropna(), "Asia/Colombo", {"2025-12-21 00:15": 300.5}
    )
    assert time_series.isna().sum() == 1

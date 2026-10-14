"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from
    Hydro-Québec.
"""

import datetime

from retrievals.electricity_demand_data_sources import hydroquebec


def test_get_available_requests():
    """Test that the data is retrieved with a single request."""
    requests = hydroquebec.get_available_requests(
        "CAN_QC", datetime.date(2019, 1, 1), datetime.date(2024, 12, 31)
    )

    assert requests == [None]


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, caplog
):
    """Test that the hourly demand is read in UTC, once per hour."""
    fake_downloads.serve(
        "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/"
        "historique-demande-electricite-quebec/exports/csv?"
        "lang=en&timezone=America%2FToronto&use_labels=true&delimiter=%2C",
        "hydroquebec.csv",
    )

    time_series = hydroquebec.download_and_extract_data_for_request(
        None, "CAN_QC"
    )

    # The export starts with a byte order mark and is not in order, and
    # each time marks the end of its hour. When daylight saving time
    # ends, the export gives both hours that end at 01:00 the offset of
    # standard time, and the first of them in the export ends at 05:00
    # UTC. Of the two values at 00:00 on 1 January 2023, the one that
    # fits the hours around it is kept.
    assert_demand(
        time_series,
        "UTC",
        {
            "2023-01-01 04:00": 21000.5,
            "2023-01-01 05:00": 20500.5,
            "2023-01-01 06:00": 20300.75,
            "2023-03-12 06:00": 24100.25,
            "2023-03-12 07:00": 24000.5,
            "2023-11-05 04:00": 19000.5,
            "2023-11-05 05:00": 18500.25,
            "2023-11-05 06:00": 18400.5,
            "2023-11-05 07:00": 18000.75,
        },
    )
    assert "[22900.25, 20500.5]" in caplog.text

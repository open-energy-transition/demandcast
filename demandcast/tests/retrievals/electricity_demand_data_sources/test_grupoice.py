"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Grupo ICE.
"""

import pytest
from retrievals.electricity_demand_data_sources import grupoice


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    assert grupoice.get_available_requests() == list(range(2012, 2026))


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the demand of every 15 minutes of a year is read."""
    fake_downloads.serve(
        "https://apps.grupoice.com/CenceWeb/data/sen/csv/DemandaMW?"
        "intervalo=15&inicio=20240101&fin=20241231",
        "grupoice_2024.csv",
    )

    time_series = grupoice.download_and_extract_data_for_request(2024)

    # The times are the starts of the 15 minutes, which move 15 minutes
    # later to mark their ends, and the file includes the last day.
    assert_demand(
        time_series,
        "America/Costa_Rica",
        {
            "2024-01-01 06:15": 1000.25,
            "2024-01-01 06:30": 990.5,
            "2025-01-01 06:00": 1050.75,
        },
    )

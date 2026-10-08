"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NESO.
"""

import pytest
from retrievals.electricity_demand_data_sources import neso


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    assert neso.get_available_requests() == list(range(2009, 2026))


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the records are numbered from the start of the year."""
    fake_downloads.serve(
        "https://api.neso.energy/api/3/action/datastore_search_sql?"
        "sql=SELECT%20*%20FROM%20%22b2bde559-3455-4021-b179-dfe60c0337b0%22"
        "%20ORDER%20BY%20%22_id%22%20ASC%20LIMIT%20100000",
        "neso.json",
    )

    time_series = neso.download_and_extract_data_for_request(2025)

    # The times come from the order of the records, every 30 minutes,
    # not from their settlement dates and periods.
    assert_demand(
        time_series,
        "Europe/London",
        {"2025-01-01 00:30": 25000, "2025-01-01 01:00": 24500},
        dtype="int64",
    )

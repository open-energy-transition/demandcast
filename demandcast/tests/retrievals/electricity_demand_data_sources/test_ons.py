"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ONS.
"""

import numpy as np
import pytest
from retrievals.electricity_demand_data_sources import ons


@pytest.mark.usefixtures("frozen_now")
def test_get_available_requests():
    """Test that the requests are the years of the data."""
    assert ons.get_available_requests("BRA_SE") == list(range(2000, 2026))


def test_download_and_extract_data_for_request(fake_downloads, assert_demand):
    """Test that the demand of one subsystem is read."""
    fake_downloads.serve(
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
        "curva-carga-ho/CURVA_CARGA_2018.csv",
        "ons_2018.csv",
    )

    time_series = ons.download_and_extract_data_for_request(2018, "BRA_SE")

    # The 23:00 that repeats when daylight saving time ends, which the
    # file has only once, and the 00:00 that is skipped when it starts,
    # whose value is empty, get no time.
    np.testing.assert_array_equal(
        time_series[time_series.index.isna()].to_numpy(), [38000.25, np.nan]
    )
    # Each year runs from 0:00 to 23:00, the starts of the hours, which
    # move one hour later to mark their ends.
    assert_demand(
        time_series[time_series.index.notna()],
        "America/Sao_Paulo",
        {
            "2018-02-18 01:00": 39500.5,
            "2018-02-18 04:00": 34000.75,
            "2018-11-04 03:00": 35000.5,
            "2018-11-04 04:00": 33000.25,
        },
    )

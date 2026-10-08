"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the Wholesale Electricity Market (WEM).
"""

from unittest.mock import patch

import pandas as pd
from retrievals.electricity_demand_data_sources import aemo_wem


def test_download_and_extract_data_for_request_before_reform():
    """Test that the timestamps are in AWST, UTC+8 all year."""
    # Perth trialled daylight saving from 3 December 2006 at 02:00.
    dataset = pd.DataFrame(
        {
            "Trading Interval": ["2006-12-03 02:00:00", "2006-12-10 14:00:00"],
            "Operational Demand (MW)": [1500.0, 2500.0],
        }
    )

    with patch("utils.fetcher.fetch_data", return_value=dataset):
        time_series = aemo_wem.download_and_extract_data_for_request(
            True, 2006, None, None
        )

    # The timestamps mark the end of the 30-minute trading intervals.
    assert time_series.index.tolist() == [
        pd.Timestamp("2006-12-02 18:30", tz="UTC"),
        pd.Timestamp("2006-12-10 06:30", tz="UTC"),
    ]

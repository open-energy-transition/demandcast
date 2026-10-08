"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from AEMO for
    the National Electricity Market (NEM).
"""

from unittest.mock import patch

import pandas as pd
from retrievals.electricity_demand_data_sources import aemo_nem


def test_download_and_extract_data_for_request():
    """Test that the timestamps are in NEM time, UTC+10 all year."""
    # Daylight saving starts in Sydney on 5 October 2025 at 02:00.
    dataset = pd.DataFrame(
        {
            "SETTLEMENTDATE": ["2025/10/05 02:00:00", "2025/10/05 14:00:00"],
            "TOTALDEMAND": [6000.0, 7000.0],
        }
    )

    with patch("utils.fetcher.fetch_data", return_value=dataset):
        time_series = aemo_nem.download_and_extract_data_for_request(
            2025, 10, "AUS_NSW"
        )

    assert time_series.index.tolist() == [
        pd.Timestamp("2025-10-04 16:00", tz="UTC"),
        pd.Timestamp("2025-10-05 04:00", tz="UTC"),
    ]

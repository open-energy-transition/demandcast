"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from
    Hydro-Québec.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import hydroquebec


def test_download_and_extract_data(fake_downloads, assert_demand):
    """Test that the hourly demand is read in UTC and sorted."""
    fake_downloads.serve(
        "https://donnees.hydroquebec.com/api/explore/v2.1/catalog/datasets/"
        "historique-demande-electricite-quebec/exports/csv?"
        "lang=en&timezone=America%2FToronto&use_labels=true&delimiter=%2C",
        "hydroquebec.csv",
    )

    time_series = hydroquebec.download_and_extract_data()

    # The export starts with a byte order mark and is not in order, and
    # each time marks the end of its hour. When daylight saving time
    # ends, the export gives both hours that end at 01:00 the offset of
    # standard time, so the one that ends at 05:00 UTC is also placed at
    # 06:00 UTC.
    is_duplicated = time_series.index.duplicated(keep=False)
    duplicated = time_series[is_duplicated]
    assert (duplicated.index == pd.Timestamp("2023-11-05 06:00Z")).all()
    assert sorted(duplicated) == [18400.5, 18500.25]
    assert_demand(
        time_series[~is_duplicated],
        "UTC",
        {
            "2023-03-12 06:00": 24100.25,
            "2023-03-12 07:00": 24000.5,
            "2023-11-05 04:00": 19000.5,
            "2023-11-05 07:00": 18000.75,
        },
    )

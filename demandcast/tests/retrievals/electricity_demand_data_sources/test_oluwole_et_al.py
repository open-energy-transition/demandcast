"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from Oluwole et
    al.
"""

import pandas as pd
from retrievals.electricity_demand_data_sources import oluwole_et_al

URL = (
    "https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1."
    "amazonaws.com/0766cdca-14a5-4522-9380-a15094e0c4c6"
)


def test_download_and_extract_data(fake_downloads, assert_demand, tmp_path):
    """Test that the unsuppressed demand is read on whole hours."""
    file_path = tmp_path / "Nigeria demand.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame([["Demand Timeseries"], [None], [None]]).to_excel(
            writer, sheet_name="Demand Timeseries", header=False, index=False
        )
        pd.DataFrame(
            {
                "date time": pd.to_datetime(
                    [
                        "2016-01-01 00:00:00",
                        "2016-04-09 10:59:59.999",
                        "2016-12-31 22:59:59.998",
                    ],
                    format="ISO8601",
                ),
                "Year": [2016, 2016, 2016],
                "Quarter": ["Q1", "Q2", "Q4"],
                "National Unsuppressed Demand": [4600.5, 5000.25, 5100.125],
                "National Suppressed Demand": [2500.5, 2900.25, 2925.125],
            }
        ).to_excel(
            writer, sheet_name="Demand Timeseries", startrow=3, index=False
        )
    fake_downloads.serve(URL, file_path)

    time_series = oluwole_et_al.download_and_extract_data_for_request(
        None, "NGA"
    )

    # From April, the times of the file are 1 or 2 ms before the start
    # of the hours. They are rounded, and move one hour later to mark
    # the ends of the hours, in Lagos (UTC+1).
    assert_demand(
        time_series,
        "Africa/Lagos",
        {
            "2016-01-01 00:00": 4600.5,
            "2016-04-09 11:00": 5000.25,
            "2016-12-31 23:00": 5100.125,
        },
    )

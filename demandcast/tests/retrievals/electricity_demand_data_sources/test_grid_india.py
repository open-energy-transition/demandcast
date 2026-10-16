"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data of Grid-India
    from its dataset on Mendeley Data.
"""

import datetime

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import grid_india

# The URL of the files of the dataset in the API of Mendeley Data.
FILES_URL = "https://data.mendeley.com/public-api/datasets/y58jknpgs8"


def _file_url(file_id):
    """
    Get the URL of a file of the dataset.

    Returns
    -------
    str
        The URL of the file.
    """
    return (
        "https://data.mendeley.com/public-files/datasets/y58jknpgs8/"
        f"files/{file_id}/file_downloaded"
    )


def test_get_available_requests(fake_downloads):
    """Test that the requests are the files, by the months in names."""
    fake_downloads.serve(FILES_URL, "grid_india_files.json")

    requests = grid_india.get_available_requests(
        "IND", datetime.date(2021, 9, 1), datetime.date(2025, 6, 24)
    )

    # The file of November 2023 is named "Novemeber 2023.xlsx".
    assert requests == [
        (
            pd.Timestamp("2021-09-01"),
            pd.Timestamp("2021-09-30"),
            "file-2021-09",
        ),
        (
            pd.Timestamp("2021-12-01"),
            pd.Timestamp("2021-12-31"),
            "file-2021-12",
        ),
        (
            pd.Timestamp("2023-11-01"),
            pd.Timestamp("2023-11-30"),
            "file-2023-11",
        ),
        (
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2025-06-30"),
            "file-2024-2025",
        ),
    ]


def test_get_available_requests_between_dates(fake_downloads):
    """Test that only the files with data between the dates are kept."""
    fake_downloads.serve(FILES_URL, "grid_india_files.json")

    requests = grid_india.get_available_requests(
        "IND", datetime.date(2023, 11, 30), datetime.date(2024, 1, 1)
    )

    assert [file_id for _, _, file_id in requests] == [
        "file-2023-11",
        "file-2024-2025",
    ]


def test_read_periods_without_month():
    """Test that a file without a month in its name is rejected."""
    with pytest.raises(ValueError, match="has no month"):
        grid_india._read_periods("README.txt")


def test_download_and_extract_monthly_data(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the readings every 5 minutes are kept, in India."""
    file_path = tmp_path / "January 2023.xlsx"
    times = pd.date_range("2023-01-01 00:00", periods=33, freq="10s")
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame([["{}"]]).to_excel(
            writer, sheet_name="_osi_config", header=False, index=False
        )
        pd.DataFrame(
            [
                ["Time", "SCADA/ANALOG/044MQ068/0", grid_india.DEMAND_TAG],
                [None, "TOTAL_THM_ONLY|P", "NLDC_DEMAND|P"],
            ]
            + [
                [time, 120000.0, 140000.5 + step]
                for step, time in enumerate(times)
            ]
        ).to_excel(writer, sheet_name="Sheet1", header=False, index=False)
    fake_downloads.serve(_file_url("file-2023-01"), file_path)

    time_series = grid_india.download_and_extract_data_for_request(
        (
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-31"),
            "file-2023-01",
        ),
        "IND",
    )

    # The readings are at their times in India (UTC+5:30), every 10
    # seconds, of which those every 5 minutes are kept.
    assert_demand(
        time_series,
        "Asia/Kolkata",
        {"2022-12-31 18:30": 140000.5, "2022-12-31 18:35": 140030.5},
    )


def test_download_and_extract_hourly_data(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hourly demand moves to the ends of the hours."""
    file_path = tmp_path / "January 2024- June 2025.xlsx"
    with pd.ExcelWriter(file_path) as writer:
        pd.DataFrame(
            {
                "Timestamp": [
                    "01-01-2024 00:00:00",
                    "01-01-2024 01:00:00",
                    "Sum",
                ],
                "Demand (MW)": [141981.26, 138675.49, 280656.75],
                "Wind (MW)": [9545.07, 9027.05, 18572.12],
            }
        ).to_excel(writer, sheet_name="Report", index=False)
        pd.DataFrame().to_excel(writer, sheet_name="Sheet2")
    fake_downloads.serve(_file_url("file-2024-2025"), file_path)

    time_series = grid_india.download_and_extract_data_for_request(
        (
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2025-06-30"),
            "file-2024-2025",
        ),
        "IND",
    )

    # The times are the starts of the hours in India (UTC+5:30), and the
    # summary rows at the bottom are left out.
    assert_demand(
        time_series,
        "Asia/Kolkata",
        {"2023-12-31 19:30": 141981.26, "2023-12-31 20:30": 138675.49},
    )

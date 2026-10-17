"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from NTDC, from
    manually downloaded files.
"""

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import ntdc


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hours and the loads with commas are read."""
    # The files have the date, the hour from 1 to 24 and the load.
    (manual_downloads_folder / "NTDC_2024.csv").write_text(
        'DATE,HOUR,SYSLOAD\n01/01/2024,1,"15,000"\n01/01/2024,24,"17,500.5"\n',
        encoding="utf-8",
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Asia/Karachi",
        {"2023-12-31 20:00": 15000.0, "2024-01-01 19:00": 17500.5},
    )


def test_download_and_extract_data_with_text(manual_downloads_folder, caplog):
    """Test that a value that is not a number is left out."""
    (manual_downloads_folder / "NTDC_2024.csv").write_text(
        'DATE,HOUR,SYSLOAD\n01/01/2024,1,"15,000"\n01/01/2024,2,meter\n',
        encoding="utf-8",
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    assert "such as 'meter'" in caplog.text
    assert time_series.tolist() == [15000.0]


def test_download_and_extract_data_with_other_days(
    manual_downloads_folder, assert_demand
):
    """Test that the rows labelled with another day are moved."""
    # The hour 24 has the date of the day before and the hour 1 of the
    # next day the date of the day, as in the file of NTDC, after a gap
    # of a day, which stays.
    rows = [("05/01/2015", 22), ("05/01/2015", 23), ("05/01/2015", 24)]
    rows += [("07/01/2015", hour) for hour in range(1, 24)]
    rows += [("06/01/2015", 24), ("07/01/2015", 1)]
    rows += [("08/01/2015", hour) for hour in range(2, 5)]
    lines = [
        f'{date},{hour},"8,{index:03d}"'
        for index, (date, hour) in enumerate(rows)
    ]
    (manual_downloads_folder / "NTDC_2015.csv").write_text(
        "DATE,HOUR,SYSLOAD\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )

    time_series = ntdc.download_and_extract_data_for_request(None, "PAK")

    # The times are the ends of the hours in Pakistan (UTC+5).
    times = pd.DatetimeIndex(
        pd.date_range("2015-01-05 17:00", periods=3, freq="h").append(
            pd.date_range("2015-01-06 20:00", periods=28, freq="h")
        )
    )
    assert_demand(
        time_series,
        "Asia/Karachi",
        dict(
            zip(
                times.strftime("%Y-%m-%d %H:%M"),
                [8000.0 + index for index in range(len(rows))],
                strict=True,
            )
        ),
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'NTD'"):
        ntdc.download_and_extract_data_for_request(None, "PAK")

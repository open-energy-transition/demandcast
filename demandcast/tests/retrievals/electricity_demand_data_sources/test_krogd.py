"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from KROGD, from
    manually downloaded files.
"""

import pytest
from retrievals.electricity_demand_data_sources import krogd


def test_download_and_extract_data(manual_downloads_folder, assert_demand):
    """Test that the hourly columns of the EUC-KR files are read."""
    # The files have one row per day and one column per hour.
    (manual_downloads_folder / "KROGD_2024.csv").write_text(
        "날짜,1시,2시,24시\n2024-01-01,60000.5,59000.25,65000.75\n",
        encoding="euc-kr",
    )

    time_series = krogd.download_and_extract_data()

    # The times mark the end of each hour.
    assert_demand(
        time_series,
        "Asia/Seoul",
        {
            "2023-12-31 16:00": 60000.5,
            "2023-12-31 17:00": 59000.25,
            "2024-01-01 15:00": 65000.75,
        },
    )


@pytest.mark.usefixtures("manual_downloads_folder")
def test_download_and_extract_data_without_files():
    """Test that the error says where to put the downloaded files."""
    with pytest.raises(FileNotFoundError, match="named starting with 'KRO'"):
        krogd.download_and_extract_data()

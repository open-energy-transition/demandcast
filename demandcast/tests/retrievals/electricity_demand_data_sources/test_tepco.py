"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from TEPCO.
"""

import datetime
import zipfile

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import tepco

MONTHLY_URL = (
    "https://www.tepco.co.jp/forecast/html/images/202512_power_usage.zip"
)


def _daily_file(day: str, values: list[int]) -> bytes:
    """
    Write a daily file of TEPCO, in Shift JIS.

    The file starts with the peak supply, then has the hourly values,
    and then the values every five minutes.

    Returns
    -------
    bytes
        The content of the file.
    """
    lines = [
        f"{day} 23:55 UPDATE",
        "ピーク時供給力(万kW),時間帯,供給力情報更新日,供給力情報更新時刻",
        # TEPCO writes the time ranges with a full-width tilde.
        "4607,13:00～14:00,12/1,23:40",  # noqa: RUF001
        "",
        "DATE,TIME,当日実績(万kW),予測値(万kW),使用率(%),供給力(万kW)",
        *[
            f"{day},{hour}:00,{value},{value},77,3359"
            for hour, value in enumerate(values)
        ],
        "",
        "DATE,TIME,当日実績(５分間隔値)(万kW),太陽光発電実績(５分間隔値)(万kW)",
        f"{day},0:00,9999,0",
    ]
    return "\r\n".join(lines).encode("cp932")


def test_get_available_requests():
    """Test that the requests are the years until 2024, then months."""
    requests = tepco.get_available_requests(
        "JPN_Kantō", datetime.date(2016, 4, 1), datetime.date(2025, 12, 28)
    )

    assert requests[:2] == [(2016, None), (2017, None)]
    assert requests[8:10] == [(2024, None), (2025, 1)]
    assert requests[-1] == (2025, 12)
    assert len(requests) == 21


def test_download_and_extract_data_for_request_of_a_year(
    fake_downloads, assert_demand, tmp_path
):
    """Test that a yearly file is read in Shift JIS, in 10 MW."""
    file_path = tmp_path / "juyo-2024.csv"
    file_path.write_bytes(
        "2025/7/22 5:40 UPDATE\r\n\r\nDATE,TIME,実績(万kW)\r\n"
        "2024/1/1,0:00,2402\r\n2024/1/1,1:00,2286\r\n".encode("cp932")
    )
    fake_downloads.serve(
        "https://www4.tepco.co.jp/forecast/html/images/juyo-2024.csv",
        file_path,
    )

    time_series = tepco.download_and_extract_data_for_request(
        (2024, None), "JPN_Kantō"
    )

    # The times mark the start of each hour in the file.
    assert_demand(
        time_series,
        "Asia/Tokyo",
        {"2023-12-31 16:00": 24020, "2023-12-31 17:00": 22860},
        dtype="int64",
    )


def test_download_and_extract_data_for_request_of_a_month(
    fake_downloads, assert_demand, tmp_path
):
    """Test that the hourly values of each day of a month are read."""
    file_path = tmp_path / "202512_power_usage.zip"
    with zipfile.ZipFile(file_path, "w") as archive:
        archive.writestr(
            "20251201_power_usage.csv",
            _daily_file("2025/12/1", [2500 + hour for hour in range(24)]),
        )
        archive.writestr(
            "20251202_power_usage.csv",
            _daily_file("2025/12/2", [2600 + hour for hour in range(24)]),
        )
    fake_downloads.serve(MONTHLY_URL, file_path)

    time_series = tepco.download_and_extract_data_for_request(
        (2025, 12), "JPN_Kantō"
    )

    # The website rejects the user agent of requests.
    assert fake_downloads.requests[0][2]["headers"] == {
        "User-Agent": "Mozilla/5.0"
    }
    # The hour that starts at 0:00 in Tokyo ends at 16:00 in UTC, and
    # the values every five minutes are not read.
    times = pd.date_range("2025-11-30 16:00", periods=48, freq="h")
    values = [10 * (2500 + hour) for hour in range(24)]
    values += [10 * (2600 + hour) for hour in range(24)]
    assert_demand(
        time_series,
        "Asia/Tokyo",
        dict(zip(times.strftime("%Y-%m-%d %H:%M"), values, strict=True)),
        dtype="int64",
    )


def test_download_and_extract_data_for_request_without_hourly_values(
    fake_downloads, tmp_path
):
    """Test that a daily file without hourly values is an error."""
    file_path = tmp_path / "202512_power_usage.zip"
    with zipfile.ZipFile(file_path, "w") as archive:
        archive.writestr(
            "20251201_power_usage.csv", "2025/12/1 23:55 UPDATE\r\n"
        )
    fake_downloads.serve(MONTHLY_URL, file_path)

    with pytest.raises(ValueError, match="No hourly values"):
        tepco.download_and_extract_data_for_request((2025, 12), "JPN_Kantō")

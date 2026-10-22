"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from ISO New
    England, with synthetic responses of its web services and a
    synthetic file of its estimate of the solar behind the meters.
"""

import datetime
import json

import pandas as pd
import pytest
from retrievals.electricity_demand_data_sources import isone


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    """Set the credentials of a test account of ISO Express."""
    monkeypatch.setenv("ISONE_USERNAME", "user")
    monkeypatch.setenv("ISONE_PASSWORD", "secret")


def _write_json(path, content: dict) -> str:
    """
    Write a JSON file.

    Parameters
    ----------
    path : pathlib.Path
        The path of the file.
    content : dict
        The content of the file.

    Returns
    -------
    str
        The path of the file.
    """
    path.write_text(json.dumps(content))
    return str(path)


def _serve_native_load(fake_downloads, tmp_path, day, offset, loads):
    """
    Serve the hourly system load of a day, from midnight.

    Parameters
    ----------
    fake_downloads : FakeDownloads
        The files to serve.
    tmp_path : pathlib.Path
        The folder of the files.
    day : str
        The day, as YYYY-MM-DD.
    offset : str
        The offset of the local time to UTC, such as "-04:00".
    loads : list[float]
        The native load of the first hours of the day.
    """
    rows = [
        {
            "BeginDate": f"{day}T{hour:02d}:00:00.000{offset}",
            "Location": {"@LocId": "32", "$": "NEPOOL AREA"},
            "Load": load + 100,
            "NativeLoad": load,
            "ArdDemand": 100,
        }
        for hour, load in enumerate(loads)
    ]
    fake_downloads.serve(
        isone.get_url("hourlysysload", pd.Timestamp(day)),
        _write_json(
            tmp_path / f"load_{day}.json",
            {"HourlySystemLoads": {"HourlySystemLoad": rows}},
        ),
    )


def _serve_forecast_solar(fake_downloads, tmp_path, day, outputs):
    """
    Serve the normalized output of the solar of a day, for the forecast.

    Parameters
    ----------
    fake_downloads : FakeDownloads
        The files to serve.
    tmp_path : pathlib.Path
        The folder of the files.
    day : str
        The day, as YYYY-MM-DD.
    outputs : dict[int, float]
        The normalized output by hour ending, zero in the other hours.
    """
    date = pd.Timestamp(day)
    rows = [
        {
            "Year": date.year,
            "Month": date.month,
            "Day": date.day,
            "HourEnding": hour,
            "ISONE": outputs.get(hour, 0.0),
        }
        for hour in range(1, 25)
    ]
    workbook = tmp_path / "btm_pv_data.xlsx"
    with pd.ExcelWriter(workbook) as writer:
        pd.DataFrame(rows).to_excel(
            writer, sheet_name="Normalized BTM PV", index=False
        )
    fake_downloads.serve(isone.BTM_PV_DATA_URL, workbook)


def test_get_available_requests():
    """Test that the data is retrieved one year at a time."""
    requests = isone.get_available_requests(
        "USA_NE", datetime.date(2019, 5, 31), datetime.date(2026, 10, 21)
    )

    assert requests[0] == (
        pd.Timestamp("2019-05-31"),
        pd.Timestamp("2020-01-01"),
    )
    assert requests[-1] == (
        pd.Timestamp("2026-01-01"),
        pd.Timestamp("2026-10-22"),
    )
    assert len(requests) == 8


def test_real_time_solar(fake_downloads, assert_demand, tmp_path):
    """
    Test that the solar in real time is added to the native load.

    The hours without samples take the solar of the load forecast.
    """
    _serve_native_load(
        fake_downloads,
        tmp_path,
        "2025-07-15",
        "-04:00",
        [1000.0, 2000.0, 3000.0],
    )
    _serve_forecast_solar(fake_downloads, tmp_path, "2025-07-15", {3: 0.1})
    # The eight zones, each with the same solar in each five minutes
    # that start in the first hour (04:00 to 05:00 UTC) and 10 MW more
    # in the second, and no samples in the third. The five minutes from
    # 01:30, without the last zone, are left out.
    samples = [
        {
            "interval_begin_date": (
                f"2025-07-15T{minutes // 60:02d}:{minutes % 60:02d}:00.000-04:00"
            ),
            "load_zone_id": zone,
            "load_zone_name": f".Z.ZONE{zone}",
            "estimated_load_mw": 500,
            "estimated_btm_pv_mw": 5.0 if minutes < 60 else 15.0,
        }
        for minutes in range(0, 120, 5)
        for zone in range(4001, 4009)
        if (minutes, zone) != (90, 4008)
    ]
    fake_downloads.serve(
        isone.get_url(
            "fiveminuteestimatedzonalload", pd.Timestamp("2025-07-15")
        ),
        _write_json(
            tmp_path / "solar.json",
            {
                "isone_web_services": {
                    "five_min_estimated_zonal_loads": {
                        "five_min_estimated_zonal_load": samples
                    }
                }
            },
        ),
    )

    time_series = isone.download_and_extract_data_for_request(
        (pd.Timestamp("2025-07-15"), pd.Timestamp("2025-07-16")), "USA_NE"
    )

    # The hour from 00:00 to 01:00 in local time ends at 05:00 UTC and
    # takes the five minutes that start from 00:00 to 00:55.
    third_hour = pd.DatetimeIndex([pd.Timestamp("2025-07-15 07:00", tz="UTC")])
    capacity = isone._get_distributed_solar_capacity(third_hour)[0]
    assert_demand(
        time_series,
        "UTC",
        {
            "2025-07-15 05:00": 1040.0,
            "2025-07-15 06:00": 2120.0,
            "2025-07-15 07:00": 3000.0 + 0.1 * capacity * 0.98,
        },
    )


def test_forecast_solar(fake_downloads, assert_demand, tmp_path):
    """Test that the solar of the load forecast is added before 2025."""
    _serve_native_load(
        fake_downloads, tmp_path, "2024-07-15", "-04:00", [1000.0] * 14
    )
    # The normalized output of the hours that end at 12:00 and 13:00 in
    # local time.
    _serve_forecast_solar(
        fake_downloads, tmp_path, "2024-07-15", {12: 0.5, 13: 0.25}
    )

    time_series = isone.download_and_extract_data_for_request(
        (pd.Timestamp("2024-07-15"), pd.Timestamp("2024-07-16")), "USA_NE"
    )

    noon = pd.DatetimeIndex([pd.Timestamp("2024-07-15 16:00", tz="UTC")])
    capacity = isone._get_distributed_solar_capacity(noon)[0]
    assert 6541.5 < capacity < 7634.0
    assert len(time_series) == 14
    assert_demand(
        time_series.take([10, 11, 13]),
        "UTC",
        {
            "2024-07-15 15:00": 1000.0,
            "2024-07-15 16:00": 1000.0 + 0.5 * capacity * 0.98,
            "2024-07-15 18:00": 1000.0,
        },
    )


def test_distributed_solar_capacity():
    """Test the capacity at the end of a year and between two years."""
    times = pd.DatetimeIndex(
        [
            pd.Timestamp("2025-01-01", tz="America/New_York"),
            pd.Timestamp("2025-07-02 12:00", tz="America/New_York"),
        ]
    ).tz_convert("UTC")

    capacity = isone._get_distributed_solar_capacity(times)

    assert capacity[0] == 7634.0
    assert capacity[1] == pytest.approx((7634.0 + 8361.0) / 2, rel=1e-3)


def test_without_credentials(monkeypatch):
    """Test that the retrieval needs the account of ISO Express."""
    monkeypatch.setenv("ISONE_PASSWORD", "")

    with pytest.raises(ValueError, match="ISONE_PASSWORD"):
        isone.download_and_extract_data_for_request(
            (pd.Timestamp("2025-07-15"), pd.Timestamp("2025-07-16")),
            "USA_NE",
        )

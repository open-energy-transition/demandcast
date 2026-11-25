"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from KOREM, with
    synthetic monthly files in the layouts of KOREM.
"""

import datetime as dt

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import korem

# The identifiers of the two versions of the month of the tests.
FIRST, SECOND = "100", "a1b2c3d4-0000-0000-0000-000000000000"


def _write_file(path, layout, zones, offset=0.0):
    """
    Write a file of KOREM with two days of two metering points by zone.

    The consumption of an hour in kWh is 1000 times its number of hours
    since the start of the month, plus 1000 times the offset, at each
    of the two metering points, so that their sum in MW is twice that.
    """
    rows = []
    for zone in zones:
        for point in ("A", "B"):
            for day in (1, 2):
                for hour in range(24):
                    if layout == "old":
                        date, label = f"2024-02-0{day} 00:00:00.000", str(hour)
                    else:
                        date = f"0{day}.02.2024"
                        label = f"{hour}-{(hour + 1) % 24}"
                    rows.append(
                        {
                            "БИН субъекта": "000000000000",
                            "Наименование субъекта": point,
                            "Зона балансирования": zone,
                            "Дата" if layout == "old" else "День": date,
                            "Час": label,
                            "Код объекта": point,
                            "План (Покупка)(кВт.ч.)": 0,
                            "Факт (Потребление)(кВт.ч.)": 1000
                            * (24 * (day - 1) + hour + offset),
                            "Факт (Генерация)(кВт.ч.)": 5,
                        }
                    )
    pd.DataFrame(rows).to_excel(path, index=False)


@pytest.fixture
def month(fake_downloads, tmp_path, monkeypatch):
    """
    Serve two versions of February 2024, in the two layouts of KOREM.

    The first version has only the North-South zone, and the second,
    with values 0.5 MWh higher, both zones.
    """
    monkeypatch.setattr(korem, "FILES", {"2024-02": [FIRST, SECOND]})
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    _write_file(first, "old", ["Зона Север-Юг"])
    _write_file(second, "new", ["Зона Север-Юг", "Зона Запад"], offset=0.25)
    fake_downloads.serve(korem.get_url(FIRST), first)
    fake_downloads.serve(korem.get_url(SECOND), second)


def test_get_available_requests(monkeypatch):
    """Test that the requests are the months with files in the dates."""
    monkeypatch.setattr(
        korem, "FILES", {"2024-01": ["1"], "2024-02": ["2"], "2024-04": ["3"]}
    )

    requests = korem.get_available_requests(
        "KAZ_WEST", dt.date(2024, 2, 10), dt.date(2024, 12, 31)
    )

    assert requests == ["2024-02", "2024-04"]


def test_get_url():
    """Test that the files of korem.kz and rcbre.korem.kz have URLs."""
    assert korem.get_url("8463") == "https://korem.kz/file/download/8463"
    assert korem.get_url(SECOND) == (
        f"https://rcbre.korem.kz/download/bre?uid={SECOND}"
    )


@pytest.mark.usefixtures("month")
@pytest.mark.parametrize(
    ("code", "offset"), [("KAZ_NORTH-SOUTH", 0.25), ("KAZ_WEST", 0.25)]
)
def test_download_and_extract_data(
    fake_downloads, assert_demand, code, offset
):
    """
    Test that the demand of a zone is the sum of its metering points.

    The two versions of the month are downloaded as a browser, and the
    second gives the values of both zones. The hour 0 of 1 February
    starts at midnight in Moscow (UTC+3), and ends at 22:00 of 31
    January in UTC.
    """
    time_series = korem.download_and_extract_data_for_request("2024-02", code)

    assert [request[2]["headers"] for request in fake_downloads.requests] == [
        {"User-Agent": "Mozilla/5.0"}
    ] * 2
    times = pd.date_range("2024-01-31 22:00", periods=48, freq="h")
    assert_demand(
        time_series,
        "Europe/Moscow",
        {
            time: 2 * (hour + offset)
            for hour, time in enumerate(times.strftime("%Y-%m-%d %H:%M"))
        },
    )


def test_earlier_version_fills_the_hours_of_the_later(
    fake_downloads, tmp_path, monkeypatch
):
    """Test that an earlier version gives the hours the later lacks."""
    monkeypatch.setattr(korem, "FILES", {"2024-02": [FIRST, SECOND]})
    first, second = tmp_path / "first.xlsx", tmp_path / "second.xlsx"
    _write_file(first, "old", ["Зона Запад"])
    _write_file(second, "new", ["Зона Север-Юг"])
    fake_downloads.serve(korem.get_url(FIRST), first)
    fake_downloads.serve(korem.get_url(SECOND), second)

    time_series = korem.download_and_extract_data_for_request(
        "2024-02", "KAZ_WEST"
    )

    assert len(time_series) == 48
    assert time_series.iloc[0] == 0.0


def test_file_without_consumption(fake_downloads, tmp_path, monkeypatch):
    """Test that a file without a column of the data is an error."""
    monkeypatch.setattr(korem, "FILES", {"2024-02": [FIRST]})
    path = tmp_path / "file.xlsx"
    pd.DataFrame({"Зона балансирования": ["Зона Запад"]}).to_excel(
        path, index=False
    )
    fake_downloads.serve(korem.get_url(FIRST), path)

    with pytest.raises(ValueError, match="no column"):
        korem.download_and_extract_data_for_request("2024-02", "KAZ_WEST")

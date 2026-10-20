"""
License: AGPL-3.0.

Description:

    Tests for the flags of the cleaned electricity demand, with
    synthetic demand that leaves out a solar generation that grows,
    that is shifted in time, or whose annual demand is too large.
"""

import os

import cleaning.flags
import geopandas
import numpy as np
import pandas as pd
import pytest
import shapely
import utils.config
import utils.shapes

pytestmark = pytest.mark.usefixtures("tmp_folders")

# The longitude of the synthetic country, whose solar time is 3 hours
# ahead of UTC.
LONGITUDE = 45.0


def _demand(solar_capacity: dict[int, float]) -> pd.Series:
    """
    Make an hourly demand without the solar generation of each year.

    The demand of the consumers is 1000 MW at night and up to 1100 MW in
    the day, and the solar generation is up to its capacity at solar
    noon, from 6:00 to 18:00 in solar time.

    Returns
    -------
    pandas.Series
        The demand, at the ends of the hours in UTC, from December 2019
        to November 2023.
    """
    times = pd.date_range("2019-12-01 01:00", "2023-12-01 00:00", freq="1h")
    middle = times - pd.Timedelta(minutes=30) + pd.Timedelta(hours=3)
    hours = middle.hour + middle.minute / 60
    daylight = np.clip(np.sin(np.pi * (hours - 6) / 12), 0, None)
    # The capacity of solar of the year that the quarter belongs to.
    year = middle.year + (middle.month == 12)
    capacity = pd.Series(year).map(solar_capacity).to_numpy()
    values = 1000 + 100 * daylight - capacity * daylight
    return pd.Series(np.asarray(values), index=times, name="Load (MW)")


def _flag(demand: pd.Series, monkeypatch, code: str = "IND") -> pd.DataFrame:
    """
    Save a cleaned demand of a place at 45 degrees east and flag it.

    Returns
    -------
    pandas.DataFrame
        The flagged periods.
    """
    shape = geopandas.GeoDataFrame(
        geometry=[shapely.box(LONGITUDE - 1, 10, LONGITUDE + 1, 12)],
        crs=4326,
    )
    monkeypatch.setattr(
        utils.shapes, "get_entity_shape", lambda *_, **__: shape
    )
    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, "test"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    demand.index.name = "Time (UTC)"
    demand.to_frame().to_parquet(file_path)

    flags = cleaning.flags.flag_data(code, "test")

    saved = pd.read_parquet(
        file_path.removesuffix(".parquet") + "_flags.parquet"
    )
    pd.testing.assert_frame_equal(saved, flags)
    return flags


def test_midday_dip(monkeypatch):
    """Test that the quarters of a year with more solar are flagged."""
    # The solar of 2022 lowers the midday index by less than 0.05, and
    # that of 2023 by more.
    demand = _demand({2020: 0, 2021: 0, 2022: 80, 2023: 200})

    flags = _flag(demand, monkeypatch)

    assert flags["period"].tolist() == [
        "DJF 2023",
        "MAM 2023",
        "JJA 2023",
        "SON 2023",
    ]
    assert flags["flag"].unique().tolist() == ["midday_dip"]
    assert flags.loc[0, "start"] == pd.Timestamp("2022-12-01")
    assert flags.loc[0, "end"] == pd.Timestamp("2023-02-28")
    assert flags.loc[3, "end"] == pd.Timestamp("2023-11-30")
    assert (flags["reference"] - flags["value"] > 0.05).all()


def test_midday_rise(monkeypatch):
    """Test that the quarters that add the solar are flagged."""
    # The solar is left out until 2022, and added in 2023, such as when
    # a system operator starts to estimate it.
    demand = _demand({2020: 200, 2021: 200, 2022: 200, 2023: 0})

    flags = _flag(demand, monkeypatch)

    assert flags[["flag", "period"]].to_numpy().tolist() == [
        ["midday_rise", "DJF 2023"],
        ["midday_rise", "MAM 2023"],
        ["midday_rise", "JJA 2023"],
        ["midday_rise", "SON 2023"],
    ]


def test_no_midday_dip(monkeypatch):
    """Test that a demand with all its solar is not flagged."""
    demand = _demand({2020: 0, 2021: 0, 2022: 0, 2023: 0})

    flags = _flag(demand, monkeypatch)

    assert flags.empty
    assert flags.columns.tolist() == [
        "start",
        "end",
        "flag",
        "period",
        "value",
        "reference",
    ]


def test_midday_dip_without_enough_days(monkeypatch):
    """Test that a quarter with too few days is not flagged."""
    demand = _demand({2020: 0, 2021: 0, 2022: 0, 2023: 200})
    # Keep 59 days of September to November 2023, and leave an hour of
    # the midday of a day in June.
    demand = demand.drop(demand["2023-09-01":"2023-10-02"].index)
    demand = demand.drop(pd.Timestamp("2023-06-15 09:00"))

    flags = _flag(demand, monkeypatch)

    assert flags["period"].tolist() == ["DJF 2023", "MAM 2023", "JJA 2023"]


def _demand_by_clock(time_zone: str, start: str, end: str) -> pd.Series:
    """
    Make an hourly demand that follows the clocks of a time zone.

    The demand has a peak in the morning and a higher one in the
    evening, at the same local hours every day.

    Returns
    -------
    pandas.Series
        The demand, at the ends of the hours in UTC.
    """
    times = pd.date_range(start, end, freq="1h")
    local = (
        (times - pd.Timedelta(minutes=30))
        .tz_localize("UTC")
        .tz_convert(time_zone)
    )
    hours = np.asarray(local.hour + local.minute / 60)
    values = (
        1000
        + 150 * np.exp(-((hours - 9) ** 2) / 4)
        + 300 * np.exp(-((hours - 19) ** 2) / 8)
    )
    return pd.Series(values, index=times, name="Load (MW)")


def test_time_lag(monkeypatch):
    """Test that a quarter read an hour early is flagged."""
    demand = _demand_by_clock(
        "Asia/Kolkata", "2019-12-01 01:00", "2023-12-01 00:00"
    )
    # The values of June to August 2022 are those of an hour later.
    summer = (demand.index >= "2022-06-01") & (demand.index < "2022-09-01")
    demand[summer] = demand.shift(-1)[summer]

    flags = _flag(demand, monkeypatch)

    assert flags[["flag", "period", "value"]].to_numpy().tolist() == [
        ["time_lag", "JJA 2022", 1.0]
    ]


@pytest.mark.parametrize(
    ("time_zone", "gap", "expected"),
    [
        ("Europe/London", None, []),
        # Without daylight saving time, the profile in the local time of
        # London is an hour late after the change of March, and an hour
        # early after that of October.
        (
            "UTC",
            None,
            [
                ["daylight_saving", "2021-03-28", -1.0],
                ["daylight_saving", "2021-10-31", 1.0],
            ],
        ),
        # The change of March is not checked without the days after it.
        (
            "UTC",
            ("2021-03-29", "2021-04-20"),
            [["daylight_saving", "2021-10-31", 1.0]],
        ),
    ],
)
def test_daylight_saving(monkeypatch, time_zone, gap, expected):
    """Test that a demand without daylight saving time is flagged."""
    # A demand that follows the clocks of London, or those of UTC,
    # without daylight saving time.
    demand = _demand_by_clock(
        time_zone, "2021-01-01 01:00", "2022-01-01 00:00"
    )
    if gap:
        demand = demand.drop(demand[gap[0] : gap[1]].index)

    flags = _flag(demand, monkeypatch, code="GBR_GB")

    assert flags[["flag", "period", "value"]].to_numpy().tolist() == expected


def _save_annual_values(
    code: str, per_capita: float | dict[int, float], population: float
) -> None:
    """Save an annual demand per capita and population for 2020-2023."""
    times = pd.date_range("2020-01-01", "2023-12-31 23:00", freq="1h")
    per_capita_values = (
        pd.Series(times.year).map(per_capita).to_numpy()
        if isinstance(per_capita, dict)
        else per_capita
    )
    folders = utils.config.read_folders_structure()
    for folder, column, value in [
        (
            "annual_electricity_demand_per_capita_folder",
            "Annual electricity demand per capita (kWh)",
            per_capita_values,
        ),
        ("population_folder", "Population", population),
    ]:
        os.makedirs(folders[folder], exist_ok=True)
        pd.DataFrame(
            {column: value}, index=pd.Index(times, name="Time (UTC)")
        ).to_parquet(os.path.join(folders[folder], f"{code}.parquet"))


@pytest.mark.parametrize("code", ["IND", "IND_KL"])
def test_annual_errors(monkeypatch, code):
    """Test that a year with too much demand is flagged."""
    # A demand of 1000 MW, of about 8.8 TWh a year, which is 1.5 times
    # more in 2022.
    demand = _demand_by_clock(
        "Asia/Kolkata", "2020-01-01 01:00", "2024-01-01 00:00"
    )
    demand[:] = 1000.0
    starts = pd.DatetimeIndex(demand.index) - pd.Timedelta(hours=1)
    demand[starts.year == 2022] *= 1.5
    _save_annual_values(code, per_capita=8760, population=1e6)

    flags = _flag(demand, monkeypatch, code=code)

    # The demand of 2022 is too far from that expected only for the
    # country, and the ratio changes in 2022 and 2023.
    rows = flags[["flag", "period"]].to_numpy().tolist()
    assert rows == (
        [["annual_change", "2022"], ["annual_total", "2022"]]
        if code == "IND"
        else [["annual_change", "2022"]]
    ) + [["annual_change", "2023"]]
    total = flags[flags["flag"] == "annual_total"]
    if code == "IND":
        assert total["value"].iloc[0] == pytest.approx(13.14)
        assert total["reference"].iloc[0] == pytest.approx(8.76)


@pytest.mark.parametrize(
    ("code", "factor", "per_capita", "flagged"),
    [
        # A change of 15% of the demand is flagged for a country, not
        # for a subdivision, whose demand changes more.
        ("IND", 1.15, 8760, True),
        ("IND_KL", 1.15, 8760, False),
        # A change of 15% of the annual demand per capita alone is not.
        ("IND", 1.0, {2020: 8760, 2021: 8760, 2022: 10074, 2023: 8760}, False),
    ],
)
def test_annual_change(monkeypatch, code, factor, per_capita, flagged):
    """Test that a change of the demand and of its ratio is flagged."""
    demand = _demand_by_clock(
        "Asia/Kolkata", "2020-01-01 01:00", "2024-01-01 00:00"
    )
    demand[:] = 1000.0
    starts = pd.DatetimeIndex(demand.index) - pd.Timedelta(hours=1)
    demand[starts.year == 2022] *= factor
    _save_annual_values(code, per_capita=per_capita, population=1e6)

    flags = _flag(demand, monkeypatch, code=code)

    assert flags[["flag", "period"]].to_numpy().tolist() == (
        [["annual_change", "2022"], ["annual_change", "2023"]]
        if flagged
        else []
    )


def test_annual_errors_without_annual_values(monkeypatch):
    """Test that the annual demand is not checked without its data."""
    demand = _demand_by_clock(
        "Asia/Kolkata", "2020-01-01 01:00", "2024-01-01 00:00"
    )
    demand[pd.DatetimeIndex(demand.index).year == 2022] *= 1.5

    flags = _flag(demand, monkeypatch)

    assert flags.empty


def _demand_of_years(time_zone_of_year: dict[int, str]) -> pd.Series:
    """
    Make an hourly demand from 2019 to 2022 that follows some clocks.

    Returns
    -------
    pandas.Series
        The demand, at the ends of the hours in UTC, which follows the
        clocks of the time zone of each year.
    """
    parts = [
        _demand_by_clock(
            time_zone, f"{year}-01-01 01:00", f"{year + 1}-01-01 00:00"
        )
        for year, time_zone in time_zone_of_year.items()
    ]
    return pd.concat(parts)


@pytest.mark.parametrize(
    ("time_zones", "late_in_winter", "expected"),
    [
        # A demand that follows the sun (UTC) more than the clocks in
        # every year moves against every change, which is not flagged.
        (["UTC"] * 4, False, []),
        # A year whose times leave out daylight saving time moves
        # against its changes, unlike the other years.
        (
            ["Europe/London", "Europe/London", "UTC", "Europe/London"],
            False,
            [["2021-03-28", -1.0], ["2021-10-31", 1.0]],
        ),
        # Winters an hour late in every year move with every change,
        # which a demand cannot do.
        (
            ["Europe/London"] * 4,
            True,
            [
                [day, value]
                for year, spring, autumn in [
                    (2019, "03-31", "10-27"),
                    (2020, "03-29", "10-25"),
                    (2021, "03-28", "10-31"),
                    (2022, "03-27", "10-30"),
                ]
                for day, value in [
                    (f"{year}-{spring}", 1.0),
                    (f"{year}-{autumn}", -1.0),
                ]
            ],
        ),
    ],
)
def test_daylight_saving_against_other_years(
    monkeypatch, time_zones, late_in_winter, expected
):
    """Test that the changes are compared with those of other years."""
    demand = _demand_of_years(
        dict(zip(range(2019, 2023), time_zones, strict=True))
    )
    if late_in_winter:
        times = pd.DatetimeIndex(demand.index)
        winter = (
            times.tz_localize("UTC")
            .tz_convert("Europe/London")
            .tz_localize(None)
            == times
        )
        demand.index = times + pd.to_timedelta(
            np.asarray(winter, dtype=int), unit="h"
        )
        demand = demand[~demand.index.duplicated()].sort_index()

    flags = _flag(demand, monkeypatch, code="GBR_GB")

    daylight_saving = flags[flags["flag"] == "daylight_saving"]
    assert daylight_saving[["period", "value"]].to_numpy().tolist() == expected

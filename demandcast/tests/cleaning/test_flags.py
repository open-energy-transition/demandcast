"""
License: AGPL-3.0.

Description:

    Tests for the flags of the cleaned electricity demand, with
    synthetic demand that leaves out a solar generation that grows.
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


def _flag(demand: pd.Series, monkeypatch) -> pd.DataFrame:
    """
    Save a cleaned demand of a country at 45 degrees east and flag it.

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
        "cleaned", "IND", "test"
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    demand.index.name = "Time (UTC)"
    demand.to_frame().to_parquet(file_path)

    flags = cleaning.flags.flag_data("IND", "test")

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

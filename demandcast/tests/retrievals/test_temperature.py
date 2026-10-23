"""
License: AGPL-3.0.

Description:

    Tests for the extraction of the temperature of the most populous
    grid cells, with synthetic gridded data.
"""

import datetime
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import pytz
import xarray
from retrievals import temperature


def _grid(values: list[list[float]], step: float = 1.0) -> xarray.DataArray:
    """
    Make gridded data, with rows of y and columns of x.

    Returns
    -------
    xarray.DataArray
        The data, at x and y from 0 by the step.
    """
    array = np.asarray(values)
    return xarray.DataArray(
        array,
        coords={
            "y": np.arange(array.shape[0]) * step,
            "x": np.arange(array.shape[1]) * step,
        },
        dims=("y", "x"),
    )


def _most_populous(population: xarray.DataArray, number: int):
    """
    Get the most populous cells, as get_largest_values_in_shape does.

    Returns
    -------
    xarray.DataArray
        The cells, along a stacked dimension.
    """
    stacked = population.stack(z=("y", "x"))  # noqa: PD013
    return stacked.sortby(stacked).tail(number)


def test_most_populous_cells_are_selected_in_pairs():
    """
    Test that the cells are selected by their pairs of coordinates.

    The three cells of the diagonal, in different rows and columns,
    are not mixed into the nine cells of their rows and columns.
    """
    population = _grid([[10, 0, 0], [0, 20, 0], [0, 0, 30]])
    temperatures = _grid([[270, 310, 310], [310, 280, 310], [310, 310, 290]])

    cells = temperature._extract_temperature_in_most_populous_cells(
        temperatures, _most_populous(population, 3)
    )

    assert sorted(cells.to_numpy().tolist()) == [270, 280, 290]
    assert float(cells.mean(dim="cell")) == pytest.approx(280)


def test_cells_that_share_the_closest_cell():
    """
    Test that populous cells count their closest cell once each.

    The two most populous cells of a fine grid are closest to the same
    cell of a coarse grid of temperatures, which counts twice.
    """
    population = _grid([[10, 20, 0, 0], [0, 0, 0, 30]], step=0.2)
    temperatures = _grid([[270, 290], [300, 300]], step=0.5)

    cells = temperature._extract_temperature_in_most_populous_cells(
        temperatures, _most_populous(population, 3)
    )

    assert sorted(cells.to_numpy().tolist()) == [270, 270, 290]


def _daily_temperatures(calendar: str) -> xarray.DataArray:
    """
    Make daily temperatures of a climate model, from 2029 to 2031.

    They follow the season, by the share of the year in the calendar.

    Returns
    -------
    xarray.DataArray
        The temperatures of a grid of one cell.
    """
    if calendar == "standard":
        times = xarray.date_range("2029-01-01", "2031-12-31", freq="D")
    else:
        times = xarray.date_range(
            "2029-01-01",
            "2031-12-30" if calendar == "360_day" else "2031-12-31",
            freq="D",
            calendar=calendar,
            use_cftime=True,
        )
    days_in_year = 360 if calendar == "360_day" else 365.25
    share_of_year = np.asarray(times.dayofyear - 1) / days_in_year
    values = 280 + 10 * np.sin(2 * np.pi * share_of_year)
    return xarray.DataArray(
        values[:, None, None],
        coords={"time": times, "y": [50.0], "x": [10.0]},
        dims=("time", "y", "x"),
    )


def _projected_temperature(calendar: str) -> pd.Series:
    """
    Get the hourly temperature of 2030 of a climate model.

    Returns
    -------
    pandas.Series
        The temperature of the most populous cell, in UTC.
    """
    population = _grid([[1.0]])
    with (
        patch.object(
            temperature,
            "_load_gridded_temperature_data",
            return_value=_daily_temperatures(calendar),
        ),
        patch.object(
            temperature,
            "_load_gridded_population_data",
            return_value=population,
        ),
        patch.object(temperature.utils.shapes, "get_entity_shape"),
        patch.object(
            temperature.utils.geospatial,
            "get_largest_values_in_shape",
            return_value=_most_populous(
                population.assign_coords(y=[50.0], x=[10.0]), 1
            ),
        ),
    ):
        (series,) = temperature._get_temperature_in_most_populous_cells(
            "DEU",
            2030,
            list(range(2026, 2101)),
            "CESM2",
            "SSP2-4.5",
            datetime.UTC,
        )
    return series


@pytest.mark.parametrize("calendar", ["noleap", "360_day", "standard"])
def test_calendars_of_climate_models(calendar):
    """
    Test that the calendars of climate models give hours of 2030.

    The days that a calendar does not have are interpolated, and the
    seasons stay where they are in the standard calendar.
    """
    series = _projected_temperature(calendar)

    assert len(series) == 8760
    assert series.notna().all()
    reference = _projected_temperature("standard")
    assert (series - reference).abs().max() < 0.5


@pytest.mark.parametrize(
    ("time_zone", "first_end"),
    [
        ("Europe/Paris", "2024-01-01 00:00"),
        ("Asia/Kolkata", "2023-12-31 20:00"),
    ],
)
def test_hourly_mean_of_the_local_year(time_zone, first_end):
    """
    Test that each hour has the mean temperature of the hour.

    The temperatures rise by 1 K an hour, so the mean of an hour is the
    temperature at its half hour. The hours are those that start in the
    local year: in India, the hour from 18:00 to 19:00 in UTC starts at
    23:30 in local time, in the year before, and the first hour of the
    year ends at 20:00 in UTC.
    """
    times = pd.date_range("2023-12-30", "2025-01-02", freq="h")
    hours = (times - times[0]) / pd.Timedelta(hours=1)
    data = xarray.DataArray(
        np.asarray(250 + hours)[:, None],
        coords={"time": times, "cell": [0]},
        dims=("time", "cell"),
    )

    hourly = temperature._extract_temperature_in_local_year(
        data, 2024, pytz.timezone(time_zone), projections=False
    ).to_series()

    ends = pd.DatetimeIndex(hourly.index.get_level_values("time"))
    assert ends[0] == pd.Timestamp(first_end)
    assert len(ends) == 8784
    half_hours = (ends - pd.Timedelta(minutes=30) - times[0]) / pd.Timedelta(
        hours=1
    )
    assert hourly.to_numpy() == pytest.approx(250 + np.asarray(half_hours))


def test_calendar_of_the_hours():
    """
    Test that the hour, day, month and year are those of the starts.

    The hour from 23:00 to midnight on Friday 2024-12-27 in Paris is on
    a Friday, and that from 23:00 to midnight on 2024-12-31 in 2024.
    """
    ends = pd.date_range("2024-12-27 21:00", "2025-01-01 01:00", freq="h")
    series = pd.Series(280.0, index=ends)

    database = temperature._build_temperature_database(
        series, series, pytz.timezone("Europe/Paris")
    )

    friday_end = database.loc[pd.Timestamp("2024-12-27 23:00")]
    assert friday_end["Local hour of the day"] == 23
    assert friday_end["Local weekend indicator"] == 0
    saturday_start = database.loc[pd.Timestamp("2024-12-28 00:00")]
    assert saturday_start["Local hour of the day"] == 0
    assert saturday_start["Local weekend indicator"] == 1
    year_end = database.loc[pd.Timestamp("2024-12-31 23:00")]
    assert year_end["Local year"] == 2024
    assert year_end["Local month of the year"] == 12
    assert database.loc[pd.Timestamp("2025-01-01 00:00"), "Local year"] == 2025


def test_points_give_the_temperature_of_the_grid():
    """
    Test that the points and the grid give the same temperature.

    The series of the points of the most populous cells are those of
    the cells of the grid, so both sources give the same hourly means.
    """
    population = _grid([[10, 0, 0], [0, 20, 0], [0, 0, 30]], step=0.25)
    population = population.assign_coords(
        x=population["x"] + 2.0, y=population["y"] + 48.0
    )
    times = pd.date_range("2023-12-30", "2025-01-02", freq="h")
    hours = np.asarray((times - times[0]) / pd.Timedelta(hours=1))
    values = (
        280
        + 0.01 * hours[:, None, None]
        + population["y"].to_numpy()[None, :, None]
        + population["x"].to_numpy()[None, None, :]
    )
    grid = xarray.DataArray(
        values,
        coords={
            "valid_time": times,
            "y": population["y"].to_numpy(),
            "x": population["x"].to_numpy(),
        },
        dims=("valid_time", "y", "x"),
    )

    def points_series(_variable, points):
        return [
            grid.sel(x=longitude, y=latitude).to_series()
            for longitude, latitude in points
        ]

    results = {}
    with (
        patch.object(
            temperature,
            "_load_gridded_population_data",
            return_value=population,
        ),
        patch.object(
            temperature, "_load_gridded_temperature_data", return_value=grid
        ),
        patch.object(temperature.utils.shapes, "get_entity_shape"),
        patch.object(
            temperature.utils.geospatial,
            "get_largest_values_in_shape",
            side_effect=lambda _shape, data, number: _most_populous(
                data, number
            ),
        ),
        patch.object(
            temperature.retrievals.era5_points,
            "get_points_series",
            side_effect=points_series,
        ),
    ):
        for source in ("points", "cds"):
            results[source] = (
                temperature._get_temperature_in_most_populous_cells(
                    "FRA",
                    2024,
                    list(range(1990, 2027)),
                    None,
                    None,
                    pytz.timezone("Europe/Paris"),
                    numbers_of_grid_cells=(1, 3),
                    reanalysis_source=source,
                )
            )

    for from_points, from_grid in zip(
        results["points"], results["cds"], strict=True
    ):
        assert len(from_points) == 8784
        assert np.allclose(from_points.to_numpy(), from_grid.to_numpy())


@pytest.mark.usefixtures("frozen_now")
def test_reanalysis_of_the_last_complete_year():
    """
    Test that the last complete year reads the current one too.

    The reanalysis ends with 2025, but the first hours of 2026 in UTC
    end the local year 2025 west of UTC, so its grid is retrieved too.
    """
    retrieved = []
    grid = xarray.Dataset(
        {
            "t2m": (
                ("valid_time", "latitude", "longitude"),
                np.zeros((1, 2, 2)),
            )
        },
        coords={
            "valid_time": [np.datetime64("2025-01-01T00:00")],
            "latitude": [34.0, 35.0],
            "longitude": [-119.0, -118.0],
        },
    )
    with (
        patch.object(
            temperature.retrievals.gridded_weather,
            "retrieve_reanalysis",
            side_effect=lambda _code, year, *_: retrieved.append(year),
        ),
        patch.object(temperature.xarray, "open_mfdataset", return_value=grid),
    ):
        temperature._load_gridded_temperature_data(
            "USA_CAL",
            2025,
            temperature.utils.catalogue.get_reanalysis_years(),
            None,
            None,
        )

    assert retrieved == [2024, 2025, 2026]

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
    stacked = population.stack(z=("y", "x"))
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
            return_value=_most_populous(population.assign_coords(y=[50.0], x=[10.0]), 1),
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

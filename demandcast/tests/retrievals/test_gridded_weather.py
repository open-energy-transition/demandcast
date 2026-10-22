"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of gridded weather data, with the downloads
    mocked: when a file of weather data is retrieved again.
"""

import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import xarray
from retrievals import gridded_weather

pytestmark = pytest.mark.usefixtures("frozen_now")


def _write(file_path: str, written: str) -> str:
    """
    Write an empty file with the given time of modification.

    Returns
    -------
    str
        The path of the file.
    """
    with open(file_path, "w"):
        pass
    seconds = pd.Timestamp(written).timestamp()
    os.utime(file_path, (seconds, seconds))
    return file_path


@pytest.mark.parametrize(
    ("year", "written", "model", "outdated"),
    [
        # The year in progress, written more than a day ago, and less.
        (2026, "2026-01-01 00:00", None, True),
        (2026, "2026-01-02 00:00", None, False),
        # The last year, written before its data was complete.
        (2025, "2025-12-20 00:00", None, True),
        # A complete year.
        (2024, "2025-01-10 00:00", None, False),
        # The projections do not change.
        (2030, "2025-12-20 00:00", "CESM2", False),
    ],
)
def test_is_outdated(tmp_path, year, written, model, outdated):
    """Test which files of weather data are retrieved again."""
    file_path = _write(str(tmp_path / "data.nc"), written)
    scenario = "SSP2-4.5" if model else None

    assert (
        gridded_weather.is_outdated(file_path, year, model, scenario)
        is outdated
    )
    assert gridded_weather.is_outdated(
        str(tmp_path / "missing.nc"), year, model, scenario
    )


def test_few_codes_complete_the_last_year(tmp_folders):
    """
    Test that a year retrieved while in progress is completed.

    With few codes, the data of each code is downloaded on its own.
    """
    folder = tmp_folders["gridded_weather_folder"]
    os.makedirs(folder)
    _write(os.path.join(folder, "DEU_temperature_2024.nc"), "2025-01-10")
    _write(os.path.join(folder, "DEU_temperature_2025.nc"), "2025-12-20")

    with (
        patch.object(gridded_weather.utils.shapes, "get_entity_shape"),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            return_value=[5.0, 47.0, 15.0, 55.0],
        ),
        patch.object(gridded_weather, "_download_data") as download,
    ):
        gridded_weather.run_data_retrieval(
            code="DEU",
            file=None,
            year=None,
            start_year=2024,
            end_year=2025,
            variable="temperature",
            model=None,
            scenario=None,
        )

    assert [call.args[1] for call in download.call_args_list] == [[2025]]


def test_file_names():
    """Test the names of the files of weather data."""
    assert (
        gridded_weather.get_file_name("temperature", 2024, None, None, "DEU")
        == "DEU_temperature_2024"
    )
    assert (
        gridded_weather.get_file_name("temperature", 2030, "CESM2", "SSP2-4.5")
        == "temperature_2030_CESM2_SSP2_4_5"
    )


def _arco_store() -> xarray.Dataset:
    """
    Make a store like that of ARCO-ERA5, with data until 2024-01-10.

    The longitudes go from 0 to 359 and the latitudes down from 60, as
    in ARCO-ERA5, and the temperature of a cell at an hour is its
    longitude plus its latitude plus the hours since 2024.

    Returns
    -------
    xarray.Dataset
        The store, until 2024-01-31.
    """
    times = pd.date_range("2024-01-01", "2024-01-31 23:00", freq="h")
    longitudes = np.arange(0.0, 360.0, 1.0)
    latitudes = np.arange(60.0, 39.0, -1.0)
    hours = np.arange(len(times), dtype=float)
    values = (
        hours[:, None, None]
        + latitudes[None, :, None]
        + np.where(longitudes > 180, longitudes - 360, longitudes)[
            None, None, :
        ]
    )
    return xarray.Dataset(
        {"2m_temperature": (("time", "latitude", "longitude"), values)},
        coords={"time": times, "latitude": latitudes, "longitude": longitudes},
        attrs={
            "valid_time_stop": "2024-01-05",
            "valid_time_stop_era5t": "2024-01-10",
        },
    )


# netCDF4 sets the shape of NumPy arrays when it writes compressed
# variables, which NumPy 2.5 deprecates.
@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)
def test_arco_era5(tmp_folders):
    """
    Test the gridded data of ARCO-ERA5, like the files of the CDS.

    The data of each code is cut from the same hours, until the last day
    with data, and is not read again once complete.
    """
    store = _arco_store()
    bounds = {"FRA": [-5.0, 42.0, 8.0, 51.0], "DEU": [6.0, 47.0, 15.0, 55.0]}
    with (
        patch.object(
            gridded_weather.utils.entities,
            "check_and_get_codes_with",
            return_value=list(bounds),
        ),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_shape",
            side_effect=lambda code, **_: code,
        ),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            side_effect=bounds.get,
        ),
        patch.object(
            gridded_weather.xarray, "open_zarr", return_value=store
        ) as open_zarr,
        patch.object(gridded_weather, "_download_data") as download,
    ):
        for _ in range(2):
            gridded_weather.run_data_retrieval(
                code=None,
                file=None,
                year=2024,
                start_year=None,
                end_year=None,
                variable="temperature",
                model=None,
                scenario=None,
                source="arco",
            )

    assert open_zarr.call_count == 1
    download.assert_not_called()
    folder = tmp_folders["gridded_weather_folder"]
    for code, (west, south, east, north) in bounds.items():
        data = xarray.open_dataset(
            os.path.join(folder, f"{code}_temperature_2024.nc")
        )["t2m"]
        assert data.dims == ("valid_time", "y", "x")
        assert data["valid_time"].to_numpy()[-1] == np.datetime64(
            "2024-01-10T23:00"
        )
        assert np.allclose(data["x"].to_numpy(), np.arange(west, east + 1))
        assert np.allclose(data["y"].to_numpy(), np.arange(south, north + 1))
        first_hour = data.isel(valid_time=0)
        expected = (
            data["y"].to_numpy()[:, None] + data["x"].to_numpy()[None, :]
        )
        assert np.allclose(first_hour.to_numpy(), expected)

"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of gridded weather data, with the downloads
    mocked: when a file of weather data is retrieved again, and how the
    global data of many countries is split into each of them.
"""

import os
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import xarray

import utils.paths
from retrievals import gridded_weather

pytestmark = pytest.mark.usefixtures("frozen_now")


def _write(file_path: str, written: str, last: str | None = None) -> str:
    """
    Write a file of weather data with the given time of modification.

    The data has the hours until the last time, or no time if it is not
    given.

    Returns
    -------
    str
        The path of the file.
    """
    times = (
        pd.date_range(
            pd.Timestamp(last) - pd.Timedelta(hours=2), last, freq="h"
        )
        if last
        else pd.DatetimeIndex([])
    )
    xarray.Dataset(
        {"t2m": ("valid_time", np.zeros(len(times)))},
        coords={"valid_time": times},
    ).to_netcdf(file_path)
    seconds = pd.Timestamp(written).timestamp()
    os.utime(file_path, (seconds, seconds))
    return file_path


@pytest.mark.parametrize(
    ("year", "written", "last", "model", "outdated"),
    [
        # The year in progress, written more than a day ago, and less.
        (2026, "2026-01-01 00:00", "2025-12-31 23:00", None, True),
        (2026, "2026-01-02 00:00", "2026-01-01 00:00", None, False),
        # The last year, written before its data was complete.
        (2025, "2025-12-20 00:00", "2025-12-13 23:00", None, True),
        # A complete year.
        (2024, "2025-01-10 00:00", "2024-12-31 23:00", None, False),
        # A part of a year copied after the year, such as from a bucket,
        # and a file without data, once they are a day old.
        (2024, "2026-01-01 00:00", "2024-06-30 23:00", None, True),
        (2024, "2026-01-01 00:00", None, None, True),
        (2024, "2026-01-01 12:00", "2024-06-30 23:00", None, False),
        # The projections do not change.
        (2030, "2025-12-20 00:00", None, "CESM2", False),
    ],
)
def test_is_outdated(tmp_path, year, written, last, model, outdated):
    """Test which files of weather data are retrieved again."""
    file_path = _write(str(tmp_path / "data.nc"), written, last)
    scenario = "SSP2-4.5" if model else None

    assert (
        gridded_weather.is_outdated(file_path, year, model, scenario)
        is outdated
    )
    assert gridded_weather.is_outdated(
        str(tmp_path / "missing.nc"), year, model, scenario
    )


def test_other_files_are_checked_by_their_time(tmp_path, caplog):
    """
    Test that a file that is not netCDF is checked by its time only.

    The temperature of a local year is a Parquet file, which xarray
    cannot read, and which ends before the last hour of the year in UTC
    east of UTC: a complete year is not retrieved again.
    """
    file_path = tmp_path / "JPN_Kantō_2024.parquet"
    file_path.write_bytes(b"parquet")
    seconds = pd.Timestamp("2025-01-10 00:00").timestamp()
    os.utime(file_path, (seconds, seconds))

    with caplog.at_level("WARNING"):
        assert not gridded_weather.is_outdated(
            str(file_path), 2024, None, None
        )

    assert caplog.text == ""


def test_broken_file_is_retrieved_again(tmp_path, caplog):
    """Test that a weather file that cannot be read is outdated."""
    file_path = tmp_path / "data.nc"
    file_path.write_bytes(b"not a netCDF file")
    seconds = pd.Timestamp("2026-01-01 00:00").timestamp()
    os.utime(file_path, (seconds, seconds))

    with caplog.at_level("WARNING"):
        assert gridded_weather.is_outdated(str(file_path), 2024, None, None)

    assert "cannot be read, so it is retrieved again" in caplog.text


def test_few_codes_complete_the_last_year():
    """
    Test that a year retrieved while in progress is completed.

    With few codes, the data of each code is downloaded on its own.
    """
    folder = utils.paths.get_gridded_folder("weather", "processed")
    os.makedirs(folder)
    _write(
        os.path.join(folder, "DEU_temperature_2024.nc"),
        "2025-01-10",
        "2024-12-31 23:00",
    )
    _write(
        os.path.join(folder, "DEU_temperature_2025.nc"),
        "2025-12-20",
        "2025-12-13 23:00",
    )

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


def test_reanalysis_of_cds_in_a_new_data_folder():
    """Test that the CDS writes its file in a new data folder."""
    folder = utils.paths.get_gridded_folder("weather", "processed")
    assert not os.path.exists(folder)

    class _Client:
        """A client of the CDS that writes the requested file."""

        def retrieve(self, _dataset, _request, target):
            """Write the file, as the CDS does."""
            _write(target, "2026-01-02", "2024-12-31 23:00")

    with (
        patch.object(gridded_weather.utils.shapes, "get_entity_shape"),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            return_value=[5.0, 47.0, 15.0, 55.0],
        ),
        patch.object(
            gridded_weather, "get_cds_client", return_value=_Client()
        ),
    ):
        gridded_weather.retrieve_reanalysis("DEU", 2024, "temperature")

    assert os.path.exists(os.path.join(folder, "DEU_temperature_2024.nc"))


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


# The bounds of the countries of the global retrieval, west, south,
# east and north.
BOUNDS = {
    "DEU": [5.0, 47.0, 15.0, 55.0],
    "FRA": [-5.0, 42.0, 8.0, 51.0],
    "ITA": [6.0, 36.0, 19.0, 47.0],
    "ESP": [-10.0, 36.0, 4.0, 44.0],
    "AUT": [9.0, 46.0, 17.0, 49.0],
    "BEL": [2.0, 49.0, 6.0, 52.0],
}


def _download_global_data(file_path, *_args, **_kwargs):
    """Write a global grid of temperature, from 0 to 359 degrees E."""
    longitudes = np.arange(0.0, 360.0, 1.0)
    latitudes = np.arange(30.0, 61.0, 1.0)
    xarray.Dataset(
        {
            "t2m": (
                ("latitude", "longitude"),
                np.add.outer(latitudes, longitudes / 1000),
            )
        },
        coords={"latitude": latitudes, "longitude": longitudes},
    ).to_netcdf(file_path + ".nc")


# The netCDF4 library sets the shape of arrays, which NumPy 2.5
# deprecates.
@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)
def test_many_codes_split_the_global_data(monkeypatch):
    """
    Test that the global data is downloaded once and split by country.

    A country is extracted again only when the global data is newer.
    """
    monkeypatch.setattr(
        gridded_weather.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: list(BOUNDS),
    )
    monkeypatch.setattr(
        gridded_weather.utils.shapes,
        "get_entity_shape",
        lambda code, **_: code,
    )
    monkeypatch.setattr(
        gridded_weather.utils.shapes, "get_entity_bounds", BOUNDS.get
    )

    def retrieve():
        with patch.object(
            gridded_weather,
            "_download_data",
            side_effect=_download_global_data,
        ) as download:
            gridded_weather.run_data_retrieval(
                None, None, 2020, None, None, "temperature", None, None
            )
        return download

    download = retrieve()

    raw_folder = utils.paths.get_gridded_folder("weather", "raw")
    processed_folder = utils.paths.get_gridded_folder("weather", "processed")
    assert download.call_args.args[0] == os.path.join(
        raw_folder, "temperature_2020"
    )
    assert os.listdir(raw_folder) == ["temperature_2020.nc"]
    assert sorted(os.listdir(processed_folder)) == sorted(
        f"{code}_temperature_2020.nc" for code in BOUNDS
    )
    with xarray.open_dataset(
        os.path.join(processed_folder, "FRA_temperature_2020.nc")
    ) as france:
        assert (float(france.x.min()), float(france.x.max())) == (
            pytest.approx(-5.0),
            pytest.approx(8.0),
        )
        assert (float(france.y.min()), float(france.y.max())) == (42.0, 51.0)

    # The global data of a past year is not downloaded again, and the
    # countries are extracted again only from newer global data.
    france_path = os.path.join(processed_folder, "FRA_temperature_2020.nc")
    os.utime(france_path, (0, 0))
    written = {
        code: os.path.getmtime(
            os.path.join(processed_folder, f"{code}_temperature_2020.nc")
        )
        for code in BOUNDS
    }
    download = retrieve()

    assert download.call_count == 0
    for code, mtime in written.items():
        new_mtime = os.path.getmtime(
            os.path.join(processed_folder, f"{code}_temperature_2020.nc")
        )
        assert (new_mtime != mtime) == (code == "FRA")


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
def test_arco_era5():
    """
    Test the gridded data of ARCO-ERA5, like the files of the CDS.

    The data of each code is cut from the same hours, until the last day
    with data, and is not read again once complete.
    """
    store = _arco_store()
    bounds = {"FRA": [-5.0, 42.0, 8.0, 51.0], "DEU": [6.0, 47.0, 15.0, 55.0]}
    with (
        patch.object(
            gridded_weather.utils.availability,
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
    folder = gridded_weather.utils.paths.get_gridded_folder(
        "weather", "processed"
    )
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

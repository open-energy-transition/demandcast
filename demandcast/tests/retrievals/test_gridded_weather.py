"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of gridded weather data, with the downloads
    mocked: when a file of weather data is retrieved again, and how the
    global data of many countries is split into each of them.
"""

import os
import zipfile
from unittest.mock import patch

import netCDF4
import numpy as np
import pandas as pd
import pytest
import xarray

import utils.paths
from retrievals import gridded_weather
from retrievals.gridded import BOUNDS_KEY, record_bounds

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
        # A complete year, written after its data was final, and one
        # written before, whose last months were preliminary.
        (2024, "2025-05-10 00:00", "2024-12-31 23:00", None, False),
        (2024, "2025-01-10 00:00", "2024-12-31 23:00", None, True),
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


def test_is_outdated_in_utc(tmp_path, monkeypatch, frozen_now):
    """
    Test that a file written less than a day ago in UTC is kept.

    The local time is 14 hours ahead of UTC, so the file was written
    more than a day ago on the local clock.
    """
    file_path = _write(
        str(tmp_path / "data.nc"), "2026-01-01 12:00", "2026-01-01 00:00"
    )
    utc_now = frozen_now.tz_localize("UTC")
    monkeypatch.setattr(
        pd.Timestamp,
        "now",
        lambda *_, tz=None: (
            utc_now.tz_convert(tz)
            if tz
            else utc_now.tz_convert("Pacific/Kiritimati").tz_localize(None)
        ),
    )

    assert not gridded_weather.is_outdated(file_path, 2026, None, None)


@pytest.mark.parametrize(
    ("retrieved", "now", "outdated"),
    [
        # Retrieved complete in January, with the preliminary data of
        # its last months, which is kept until it is final.
        ("2026-01-20", "2026-03-01", False),
        # Then retrieved again once, when the data is final.
        ("2026-01-20", "2026-05-10", True),
        ("2026-05-10", "2026-09-01", False),
    ],
)
def test_preliminary_data_is_replaced_once(
    tmp_path, monkeypatch, retrieved, now, outdated
):
    """
    Test that a year is retrieved again once its data is final.

    ERA5 replaces its preliminary data (ERA5T) with the final data two
    to three months later, so the files of 2025 retrieved before May
    2026 are retrieved again once after it.
    """
    file_path = _write(
        str(tmp_path / "data.nc"), "2020-01-01", "2025-12-31 23:00"
    )
    with netCDF4.Dataset(file_path, "a") as dataset:
        dataset.setncattr(gridded_weather.RETRIEVED_KEY, retrieved)
    monkeypatch.setattr(
        pd.Timestamp, "now", lambda *_, **__: pd.Timestamp(now)
    )

    assert gridded_weather.is_outdated(file_path, 2025, None, None) == (
        outdated
    )


@pytest.mark.parametrize("extension", [".nc", ".parquet"])
@pytest.mark.parametrize(
    ("year", "retrieved", "outdated"),
    [
        # Retrieved before the year was complete, and before its data
        # was final.
        (2025, "2025-12-20T00:00:00", True),
        (2024, "2025-01-10T00:00:00", True),
        # Retrieved when its data was final.
        (2024, "2025-05-10T00:00:00", False),
    ],
)
def test_copies_keep_the_time_of_their_retrieval(
    tmp_path, extension, year, retrieved, outdated
):
    """
    Test that a copy is checked by when its data was retrieved.

    The files record the time of the retrieval of their data, which a
    copy, such as from a bucket, keeps, while its time of modification
    is that of the copy, after the data of 2024 was final.
    """
    file_path = str(tmp_path / f"data{extension}")
    if extension == ".nc":
        _write(file_path, "2025-12-31", f"{year}-12-31 23:00")
        with netCDF4.Dataset(file_path, "a") as dataset:
            dataset.setncattr(gridded_weather.RETRIEVED_KEY, retrieved)
    else:
        data = pd.DataFrame({"Temperature - Top 1 (K)": [280.0]})
        data.attrs = {gridded_weather.RETRIEVED_KEY: retrieved}
        data.to_parquet(file_path)
    seconds = pd.Timestamp("2025-12-31").timestamp()
    os.utime(file_path, (seconds, seconds))

    assert gridded_weather.get_retrieval_time(file_path) == pd.Timestamp(
        retrieved
    )
    assert gridded_weather.is_outdated(file_path, year, None, None) == (
        outdated
    )


def test_other_files_are_checked_by_their_time(tmp_path, caplog):
    """
    Test that a file that is not netCDF is checked by its time only.

    The temperature of a local year is a Parquet file, which xarray
    cannot read, and which ends before the last hour of the year in UTC
    east of UTC: a complete year is not retrieved again. A file without
    the time of its retrieval, which cannot be read here, is checked by
    the time of its last modification.
    """
    file_path = tmp_path / "JPN_Kantō_2024.parquet"
    file_path.write_bytes(b"parquet")
    seconds = pd.Timestamp("2025-05-10 00:00").timestamp()
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


@pytest.mark.parametrize("code", [None, "DEU"])
def test_broken_projection_of_a_code_is_retrieved_again(tmp_path, code):
    """
    Test that a broken grid of a code is outdated, even a projection.

    The projections do not change, but a grid of a code that cannot be
    read cannot show its bounds; another file is checked by its time.
    """
    file_path = tmp_path / "data.nc"
    file_path.write_bytes(b"not a netCDF file")

    assert gridded_weather.is_outdated(
        str(file_path), 2030, "CESM2", "SSP2-4.5", code
    ) == (code is not None)


@pytest.mark.parametrize(
    ("recorded", "outdated"),
    [
        # The bounds of another shape, and those of the current one.
        ([5.0, 47.0, 16.0, 55.0], True),
        ([5.0, 47.0, 15.0, 55.0], False),
        # A grid downloaded before the bounds were recorded is kept.
        (None, False),
    ],
)
def test_grid_of_another_shape_is_outdated(tmp_path, recorded, outdated):
    """
    Test that a grid cut with other bounds than the shape's is outdated.

    The projections do not change otherwise, so only the bounds decide.
    """
    file_path = str(tmp_path / "DEU_temperature_2030.nc")
    grid = xarray.Dataset({"tas": ("x", np.zeros(3))})
    (record_bounds(grid, recorded) if recorded else grid).to_netcdf(file_path)

    with (
        patch.object(gridded_weather.utils.shapes, "get_entity_shape"),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            return_value=[5.0, 47.0, 15.0, 55.0],
        ),
    ):
        assert (
            gridded_weather.is_outdated(
                file_path, 2030, "CESM2", "SSP2-4.5", "DEU"
            )
            == outdated
        )


def test_few_codes_complete_the_last_year():
    """
    Test that a year retrieved while in progress is completed.

    With few codes, the data of each code is downloaded on its own.
    """
    folder = utils.paths.get_gridded_folder("weather", "processed")
    os.makedirs(folder)
    _write(
        os.path.join(folder, "DEU_temperature_2024.nc"),
        "2025-05-10",
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
    """
    Test that the CDS writes its file in a new data folder.

    The file then records the bounds of the shape of its code.
    """
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

    with xarray.open_dataset(
        os.path.join(folder, "DEU_temperature_2024.nc")
    ) as data:
        assert data.attrs[BOUNDS_KEY].tolist() == [5.0, 47.0, 15.0, 55.0]
        assert (
            data.attrs[gridded_weather.RETRIEVED_KEY] == "2026-01-02T03:04:05"
        )


def _zip_of_projections(target: str, netcdf_names: list[str]) -> None:
    """
    Write a zip file of projections, as the CDS gives them.

    The zip file has a NetCDF file of daily temperatures in a grid of
    2.8 degrees for each name, and a text file.
    """
    folder = os.path.dirname(target)
    for name in netcdf_names:
        xarray.Dataset(
            {"tas": (("time", "lat", "lon"), np.full((2, 2, 2), 290.0))},
            coords={
                "time": pd.date_range("2030-01-01 12:00", periods=2),
                "lat": [46.2, 49.0],
                "lon": [5.6, 8.4],
            },
        ).to_netcdf(os.path.join(folder, name))
    with zipfile.ZipFile(target, "w") as archive:
        for name in netcdf_names:
            archive.write(os.path.join(folder, name), name)
            os.remove(os.path.join(folder, name))
        archive.writestr("provenance.txt", "CMIP6")


@pytest.mark.parametrize("netcdf_names", [["tas_day.nc"], ["a.nc", "b.nc"]])
def test_projections_of_a_code_replace_an_empty_grid(netcdf_names):
    """
    Test that the projections of a code replace its grid without cells.

    The grid of Liechtenstein, smaller than the cells of the climate
    model, has no cell, so it is downloaded again, within its bounds and
    a margin around them. The NetCDF file of the zip file replaces it,
    and the zip file is removed; a zip file of two NetCDF files is an
    error.
    """
    bounds = [9.47, 47.05, 9.64, 47.27]
    folder = utils.paths.get_gridded_folder("weather", "processed")
    os.makedirs(folder)
    file_path = os.path.join(folder, "LIE_temperature_2030_CESM2_SSP2_4_5.nc")
    record_bounds(
        xarray.Dataset(
            {"tas": (("time", "lat", "lon"), np.zeros((1, 0, 0)))},
            coords={"time": [0], "lat": [], "lon": []},
        ),
        bounds,
    ).to_netcdf(file_path)
    requests = []

    class _Client:
        """A client of the CDS that writes a zip file of projections."""

        def retrieve(self, _dataset, request, target):
            """Write the zip file, as the CDS does."""
            requests.append(request)
            _zip_of_projections(target, netcdf_names)

    with (
        patch.object(
            gridded_weather.utils.availability,
            "check_and_get_codes_with",
            return_value=["LIE"],
        ),
        patch.object(gridded_weather.utils.shapes, "get_entity_shape"),
        patch.object(
            gridded_weather.utils.shapes,
            "get_entity_bounds",
            return_value=bounds,
        ),
        patch.object(
            gridded_weather, "get_cds_client", return_value=_Client()
        ),
    ):
        if len(netcdf_names) > 1:
            with pytest.raises(ValueError, match=r"2 \.nc files"):
                gridded_weather.run_data_retrieval(
                    "LIE",
                    None,
                    2030,
                    None,
                    None,
                    "temperature",
                    "CESM2",
                    "SSP2-4.5",
                )
            return
        gridded_weather.run_data_retrieval(
            "LIE", None, 2030, None, None, "temperature", "CESM2", "SSP2-4.5"
        )

    assert requests[0]["area"] == pytest.approx([48.77, 7.97, 45.55, 11.14])
    assert not os.path.exists(file_path.removesuffix(".nc") + ".zip")
    with xarray.open_dataset(file_path) as grid:
        assert grid.sizes["lat"] == grid.sizes["lon"] == 2
        assert grid.attrs[BOUNDS_KEY].tolist() == bounds


def test_margin_stays_on_the_globe():
    """Test that the margin of bounds stays within the globe."""
    assert gridded_weather._add_margin([179.0, -89.0, 180.0, 90.0], 1.5) == [
        177.5,
        -90.0,
        180.0,
        90.0,
    ]


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
    """
    Write a global grid of temperature, from 0 to 359 degrees E.

    The grid records the time of its retrieval, as a download does.
    """
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
        attrs={gridded_weather.RETRIEVED_KEY: "2026-01-02T03:04:05"},
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
        """
        Retrieve the data of 2020, with the global data written.

        Returns
        -------
        unittest.mock.MagicMock
            The mock of the download.
        """
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
        # The grid of a code has the time of the retrieval of the global
        # data.
        assert (
            france.attrs[gridded_weather.RETRIEVED_KEY]
            == "2026-01-02T03:04:05"
        )

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
        dataset = xarray.open_dataset(
            os.path.join(folder, f"{code}_temperature_2024.nc")
        )
        assert dataset.attrs[BOUNDS_KEY].tolist() == bounds[code]
        assert (
            dataset.attrs[gridded_weather.RETRIEVED_KEY]
            == "2026-01-02T03:04:05"
        )
        data = dataset["t2m"]
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

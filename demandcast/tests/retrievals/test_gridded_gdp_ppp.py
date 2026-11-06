"""
License: AGPL-3.0.

Description:

    Tests for the download of the gridded GDP PPP from Zenodo, for the
    reading of its rasters and for the extraction of the GDP PPP of
    each country and subdivision, with small synthetic rasters and
    archives in place of the downloaded ones.
"""

import io
import os
from typing import Any

import numpy as np
import py7zr
import pytest
import requests

# Imported for the rio accessor of xarray, which writes the rasters.
import rioxarray  # noqa: F401
import xarray

import utils.paths
from retrievals import gridded_gdp_ppp

# The URL of the archive of the gridded GDP PPP on Zenodo.
ZENODO_URL = (
    "https://zenodo.org/records/7898409/files/"
    "GDP_025d%20(2000-2100).7z?download=1"
)

# The netCDF4 library sets the shape of arrays, which NumPy 2.5
# deprecates.
IGNORE_NETCDF_SHAPE_WARNING = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)


def _serve(
    monkeypatch: pytest.MonkeyPatch, content: bytes, status_code: int = 200
) -> list[str]:
    """
    Replace the downloads of requests with a content served on Zenodo.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The fixture that replaces the download function.
    content : bytes
        The content served at the URL of the archive on Zenodo.
    status_code : int, optional
        The HTTP status code of the response.

    Returns
    -------
    list[str]
        The URL of each download, filled in as the downloads are made.
    """
    downloads: list[str] = []

    def get(url: str, **_kwargs: Any) -> requests.Response:
        """
        Record a download and get the content served at its URL.

        Returns
        -------
        requests.Response
            The response, with the content served at the URL.

        Raises
        ------
        AssertionError
            If the URL is not that of the archive on Zenodo.
        """
        downloads.append(url)
        if url != ZENODO_URL:
            raise AssertionError(f"Unexpected download: {url}")
        response = requests.Response()
        response.status_code = status_code
        response.url = url
        response.raw = io.BytesIO(content)
        return response

    monkeypatch.setattr(requests, "get", get)
    return downloads


def _write_raster(path: str, values: np.ndarray) -> None:
    """
    Write a GeoTIFF file of one band, with cells of one degree.

    Parameters
    ----------
    path : str
        The path of the file.
    values : numpy.ndarray
        The values of the band, with rows of y from 2 degrees north to
        the equator and columns of x from 10 degrees east.
    """
    rows, columns = values.shape
    xarray.DataArray(
        values,
        coords={
            "y": 2 - (np.arange(rows) + 0.5),
            "x": 10 + (np.arange(columns) + 0.5),
        },
        dims=("y", "x"),
    ).rio.write_crs("EPSG:4326").rio.to_raster(path)


def _archive(tmp_path, values: np.ndarray) -> bytes:
    """
    Make a 7z archive with the GDP PPP of 2020 in the folder 025d.

    Returns
    -------
    bytes
        The content of the archive.
    """
    raster_path = os.path.join(tmp_path, "GDP2020.tif")
    _write_raster(raster_path, values)
    buffer = io.BytesIO()
    with py7zr.SevenZipFile(buffer, mode="w") as archive:
        archive.write(raster_path, arcname="025d/GDP2020.tif")
    return buffer.getvalue()


def test_download_gdp_ppp(tmp_path, monkeypatch):
    """
    Test that the archive is extracted into the raw folder.

    The archive has the rasters in a folder named 025d, which becomes
    the raw folder.
    """
    downloads = _serve(monkeypatch, _archive(tmp_path, np.ones((2, 3))))
    raw_folder = os.path.join(tmp_path, "gdp_ppp", "raw")
    os.makedirs(os.path.dirname(raw_folder))

    gridded_gdp_ppp._download_gdp_ppp(raw_folder)

    assert downloads == [ZENODO_URL]
    assert os.listdir(os.path.dirname(raw_folder)) == ["raw"]
    assert os.listdir(raw_folder) == ["GDP2020.tif"]


def test_download_gdp_ppp_exists(tmp_path, monkeypatch):
    """Test that the raw folder that exists is kept as it is."""
    downloads = _serve(monkeypatch, b"")
    (tmp_path / "raw").mkdir()

    gridded_gdp_ppp._download_gdp_ppp(str(tmp_path / "raw"))

    assert downloads == []
    assert os.listdir(tmp_path / "raw") == []


def test_download_gdp_ppp_failed(tmp_path, monkeypatch):
    """Test that a failed download raises an error and adds nothing."""
    _serve(monkeypatch, b"Not Found", status_code=404)

    with pytest.raises(requests.HTTPError):
        gridded_gdp_ppp._download_gdp_ppp(str(tmp_path / "raw"))

    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    ("year_scenario", "file_name"),
    [("2020", "GDP2020.tif"), ("2030_SSP2", "GDP2030_ssp2.tif")],
)
def test_read_gdp_ppp(tmp_path, year_scenario, file_name):
    """
    Test that the GDP PPP of a year and scenario is read from its file.

    The scenario is in lower case in the name of the file. The rows of
    the raster go from north to south, and are sorted from south to
    north. The band and the attributes of the raster are dropped, and
    the data is named gdp_ppp.
    """
    _write_raster(
        os.path.join(tmp_path, file_name), np.arange(6.0).reshape(2, 3)
    )

    gdp_ppp = gridded_gdp_ppp._read_gdp_ppp(str(tmp_path), year_scenario)

    assert gdp_ppp.name == "gdp_ppp"
    assert gdp_ppp.dims == ("y", "x")
    assert set(gdp_ppp.coords) == {"x", "y"}
    assert gdp_ppp.attrs == {}
    assert gdp_ppp["x"].to_numpy().tolist() == [10.5, 11.5, 12.5]
    assert gdp_ppp["y"].to_numpy().tolist() == [0.5, 1.5]
    assert gdp_ppp.to_numpy().tolist() == [[3, 4, 5], [0, 1, 2]]


@IGNORE_NETCDF_SHAPE_WARNING
def test_run_data_retrieval_downloads(tmp_path, monkeypatch):
    """
    Test that the downloaded GDP PPP of an entity is saved as it is.

    The archive is extracted into the raw folder, and the grid of the
    entity has the cells of the raster of 2020 within its bounds.
    """
    downloads = _serve(
        monkeypatch, _archive(tmp_path, np.arange(6.0).reshape(2, 3))
    )
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA"],
    )
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_shape",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_bounds",
        lambda _: [11, 0, 13, 1],
    )

    gridded_gdp_ppp.run_data_retrieval("FRA", None, 2020, None, None, None)

    assert downloads == [ZENODO_URL]
    assert os.listdir(utils.paths.get_gridded_folder("gdp_ppp", "raw")) == [
        "GDP2020.tif"
    ]
    with xarray.open_dataarray(
        utils.paths.get_gridded_file("gdp_ppp", "FRA", 2020, None)
    ) as gdp_ppp:
        assert gdp_ppp.to_numpy().tolist() == [[4, 5]]


@IGNORE_NETCDF_SHAPE_WARNING
def test_run_data_retrieval(monkeypatch):
    """
    Test that the grid of each entity is saved in the processed folder.

    The global grid of each year and scenario is read from the raw
    folder, and a grid that exists is not extracted again.
    """
    global_grid = xarray.DataArray(
        np.arange(16.0).reshape(4, 4),
        coords={"y": [0.5, 1.5, 2.5, 3.5], "x": [0.5, 1.5, 2.5, 3.5]},
        dims=["y", "x"],
    )
    downloads: list[str] = []
    read: list[tuple[str, str]] = []

    def read_gdp_ppp(folder, year_scenario):
        """
        Record a read and give the global grid.

        Returns
        -------
        xarray.DataArray
            The global grid.
        """
        read.append((folder, year_scenario))
        return global_grid

    monkeypatch.setattr(
        gridded_gdp_ppp.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA", "DEU"],
    )
    monkeypatch.setattr(gridded_gdp_ppp, "_download_gdp_ppp", downloads.append)
    monkeypatch.setattr(gridded_gdp_ppp, "_read_gdp_ppp", read_gdp_ppp)
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_shape",
        lambda code, **_: code,
    )
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_bounds",
        {"FRA": (0, 0, 2, 2), "DEU": (2, 2, 4, 4)}.get,
    )

    gridded_gdp_ppp.run_data_retrieval(None, None, 2020, None, None, None)
    gridded_gdp_ppp.run_data_retrieval(None, None, 2030, None, None, "SSP2")

    raw_folder = utils.paths.get_gridded_folder("gdp_ppp", "raw")
    processed_folder = utils.paths.get_gridded_folder("gdp_ppp", "processed")
    assert downloads == [raw_folder, raw_folder]
    assert read == [(raw_folder, "2020"), (raw_folder, "2030_SSP2")]
    assert sorted(os.listdir(processed_folder)) == [
        "DEU_0.25_deg_2020.nc",
        "DEU_0.25_deg_2030_SSP2.nc",
        "FRA_0.25_deg_2020.nc",
        "FRA_0.25_deg_2030_SSP2.nc",
    ]
    with xarray.open_dataarray(
        os.path.join(processed_folder, "DEU_0.25_deg_2020.nc")
    ) as germany:
        assert germany.values.tolist() == [[10.0, 11.0], [14.0, 15.0]]

    path = os.path.join(processed_folder, "FRA_0.25_deg_2020.nc")
    os.utime(path, (0, 0))
    gridded_gdp_ppp.run_data_retrieval(None, None, 2020, None, None, None)

    assert os.path.getmtime(path) == 0

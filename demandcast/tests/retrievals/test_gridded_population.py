"""
License: AGPL-3.0.

Description:

    Tests for the download of the historical gridded population density
    from SEDAC and of the future gridded population from Figshare, for
    the reading of their rasters, and for the extraction of the
    population of each country and subdivision, with small synthetic
    rasters and archives in place of the downloaded ones.
"""

import io
import os
import zipfile
from typing import Any

import numpy as np
import pytest
import requests

# Imported for the rio accessor of xarray, which writes the rasters.
import rioxarray  # noqa: F401
import xarray

import utils.paths
from retrievals import gridded_population

# The URLs of the archives of the SSPs on the download server of
# Figshare.
FIGSHARE_URLS = {
    "SSP1": "https://ndownloader.figshare.com/files/34829160",
    "SSP2": "https://ndownloader.figshare.com/files/34829370",
    "SSP3": "https://ndownloader.figshare.com/files/45894312",
    "SSP4": "https://ndownloader.figshare.com/files/34829385",
    "SSP5": "https://ndownloader.figshare.com/files/34829391",
}

# The netCDF4 library sets the shape of arrays, which NumPy 2.5
# deprecates.
IGNORE_NETCDF_SHAPE_WARNING = pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)


def _sedac_url(year: int) -> str:
    """
    Get the URL of the population density of a year on SEDAC.

    Returns
    -------
    str
        The URL of the GeoTIFF file.
    """
    return (
        "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
        f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
    )


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[str, bytes],
    status_code: int = 200,
) -> list[tuple[str, dict[str, Any]]]:
    """
    Replace the downloads of requests with contents served at URLs.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The fixture that replaces the download function.
    files : dict[str, bytes]
        The content served at each URL.
    status_code : int, optional
        The HTTP status code of the responses.

    Returns
    -------
    list[tuple[str, dict[str, Any]]]
        The URL and the keyword arguments of each download, filled in
        as the downloads are made.
    """
    downloads: list[tuple[str, dict[str, Any]]] = []

    def get(url: str, **kwargs: Any) -> requests.Response:
        """
        Record a download and get the content served at its URL.

        Returns
        -------
        requests.Response
            The response, with the content served at the URL.

        Raises
        ------
        AssertionError
            If no content is served at the URL.
        """
        downloads.append((url, kwargs))
        if url not in files:
            raise AssertionError(f"Unexpected download: {url}")
        response = requests.Response()
        response.status_code = status_code
        response.url = url
        response.raw = io.BytesIO(files[url])
        return response

    monkeypatch.setattr(requests, "get", get)
    return downloads


def _write_raster(
    path: str,
    values: np.ndarray,
    west: float,
    north: float,
    resolution: float,
    crs: str | None = None,
) -> None:
    """
    Write a GeoTIFF file of one band, with its rows from north to south.

    Parameters
    ----------
    path : str
        The path of the file.
    values : numpy.ndarray
        The values of the band, with rows of y and columns of x.
    west : float
        The west edge of the raster.
    north : float
        The north edge of the raster.
    resolution : float
        The size of the cells in x and y.
    crs : str | None, optional
        The coordinate reference system of the raster, if any.
    """
    rows, columns = values.shape
    raster = xarray.DataArray(
        values.astype("float32"),
        coords={
            "y": north - resolution * (np.arange(rows) + 0.5),
            "x": west + resolution * (np.arange(columns) + 0.5),
        },
        dims=("y", "x"),
    )
    if crs is not None:
        raster = raster.rio.write_crs(crs)
    raster.rio.to_raster(path)


def _raster_bytes(
    tmp_path, values: np.ndarray, west: float, north: float, res: float
) -> bytes:
    """
    Get the content of a GeoTIFF file in geographic coordinates.

    Returns
    -------
    bytes
        The content of the file.
    """
    path = os.path.join(tmp_path, "raster.tif")
    _write_raster(path, values, west, north, res, crs="EPSG:4326")
    with open(path, "rb") as file:
        return file.read()


def _archive(files: dict[str, bytes]) -> bytes:
    """
    Make a zip archive of files.

    Parameters
    ----------
    files : dict[str, bytes]
        The content of each file, by its path in the archive.

    Returns
    -------
    bytes
        The content of the archive.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_download_historical_gridded_population_density(tmp_path, monkeypatch):
    """Test that the density of a year is saved in its own file."""
    downloads = _serve(monkeypatch, {_sedac_url(2015): b"density"})

    gridded_population._download_historical_gridded_population_density(
        str(tmp_path), 2015
    )

    assert [url for url, _ in downloads] == [_sedac_url(2015)]
    assert (tmp_path / "2015.tif").read_bytes() == b"density"


def test_download_historical_gridded_population_density_exists(
    tmp_path, monkeypatch
):
    """Test that the density of a year that exists is not downloaded."""
    downloads = _serve(monkeypatch, {})
    (tmp_path / "2015.tif").write_bytes(b"density")

    gridded_population._download_historical_gridded_population_density(
        str(tmp_path), 2015
    )

    assert downloads == []
    assert (tmp_path / "2015.tif").read_bytes() == b"density"


def test_download_historical_gridded_population_density_errors(
    tmp_path, monkeypatch
):
    """
    Test that a year without data or a failed download raises an error.

    The density is given every five years, so 2016 is not requested,
    and a failed download leaves no file, so that the next run
    downloads it again.
    """
    downloads = _serve(
        monkeypatch, {_sedac_url(2015): b"Not Found"}, status_code=404
    )

    with pytest.raises(ValueError, match="year must be one of"):
        gridded_population._download_historical_gridded_population_density(
            str(tmp_path), 2016
        )
    assert downloads == []

    with pytest.raises(requests.HTTPError):
        gridded_population._download_historical_gridded_population_density(
            str(tmp_path), 2015
        )
    assert os.listdir(tmp_path) == []


@pytest.mark.parametrize(
    ("scenario", "folder"),
    [
        ("SSP1", "SPP1"),
        ("SSP2", "SPP2"),
        ("SSP3", "SSP3"),
        ("SSP4", "SPP4"),
        ("SSP5", "SPP5"),
    ],
)
def test_download_future_gridded_population(
    tmp_path, monkeypatch, scenario, folder
):
    """
    Test that the archive of a scenario is extracted into its folder.

    The archive of each scenario is streamed from the download server
    of Figshare. The folders named SPP in the archives of SSP1, SSP2,
    SSP4 and SSP5 are renamed to the scenario, and the archive is
    removed.
    """
    url = FIGSHARE_URLS[scenario]
    downloads = _serve(
        monkeypatch, {url: _archive({f"{folder}/{scenario}_2030.tif": b"1"})}
    )
    data_folder = os.path.join(tmp_path, "raw")

    gridded_population._download_future_gridded_population(
        data_folder, scenario
    )

    assert len(downloads) == 1
    assert downloads[0][0] == url
    assert downloads[0][1]["stream"] is True
    assert os.listdir(data_folder) == [scenario]
    assert os.listdir(os.path.join(data_folder, scenario)) == [
        f"{scenario}_2030.tif"
    ]


def test_download_future_gridded_population_exists(tmp_path, monkeypatch):
    """Test that an existing folder of a scenario is not replaced."""
    downloads = _serve(monkeypatch, {})
    (tmp_path / "SSP2").mkdir()

    gridded_population._download_future_gridded_population(
        str(tmp_path), "SSP2"
    )

    assert downloads == []
    assert os.listdir(tmp_path / "SSP2") == []


def test_download_future_gridded_population_unknown_scenario(
    tmp_path, monkeypatch
):
    """Test that a scenario that is not an SSP raises an error."""
    downloads = _serve(monkeypatch, {})

    with pytest.raises(ValueError, match="ssp must be one of"):
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP6"
        )

    assert downloads == []


def test_download_future_gridded_population_failed(tmp_path, monkeypatch):
    """
    Test that a failed download raises an error and leaves no files.

    A response with an error and a response that is not an archive
    leave neither the archive nor the folder of the scenario, so that
    the next run downloads it again.
    """
    _serve(monkeypatch, {FIGSHARE_URLS["SSP3"]: b"Error"}, status_code=500)
    with pytest.raises(requests.HTTPError):
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP3"
        )
    assert os.listdir(tmp_path) == []

    _serve(monkeypatch, {FIGSHARE_URLS["SSP3"]: b"<html></html>"})
    with pytest.raises(zipfile.BadZipFile):
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP3"
        )
    assert os.listdir(tmp_path) == []


def test_read_historical_population_dataset(tmp_path):
    """
    Test that the density of a year is read with sorted coordinates.

    The rows of the raster go from north to south, and are sorted from
    south to north. The band and the attributes of the raster are
    dropped, and the data is named population.
    """
    values = np.arange(6.0).reshape(2, 3)
    _write_raster(
        os.path.join(tmp_path, "2020.tif"), values, 10, 2, 1, "EPSG:4326"
    )

    population = gridded_population._read_population_dataset(
        str(tmp_path), 2020, None
    )

    assert population.name == "population"
    assert population.dims == ("y", "x")
    assert set(population.coords) == {"x", "y"}
    assert population.attrs == {}
    assert population["x"].to_numpy().tolist() == [10.5, 11.5, 12.5]
    assert population["y"].to_numpy().tolist() == [0.5, 1.5]
    assert population.to_numpy().tolist() == [[3, 4, 5], [0, 1, 2]]


def test_read_future_population_dataset(tmp_path):
    """
    Test that the coordinates of a future raster are made geographic.

    The coordinates of the raster, which are not in degrees, are
    scaled to the centres of cells of 30 arc seconds that cover the
    longitudes of the whole world and the latitudes from 72 degrees
    south to 84 degrees north: the first and last centres are half a
    cell inside these limits.
    """
    values = np.arange(16.0).reshape(4, 4)
    os.makedirs(os.path.join(tmp_path, "SSP2"))
    _write_raster(
        os.path.join(tmp_path, "SSP2", "SSP2_2050.tif"),
        values,
        1000,
        5000,
        250,
    )

    population = gridded_population._read_population_dataset(
        str(tmp_path), 2050, "SSP2"
    )

    x = population["x"].to_numpy()
    y = population["y"].to_numpy()
    cell = 30 / 3600
    assert population.name == "population"
    assert x[0] == pytest.approx(-180 + cell / 2)
    assert x[-1] == pytest.approx(180 - cell / 2)
    assert y[0] == pytest.approx(-72 + cell / 2)
    assert y[-1] == pytest.approx(84 - cell / 2)
    assert np.allclose(np.diff(x), (360 - cell) / 3)
    assert np.allclose(np.diff(y), (156 - cell) / 3)
    assert population.to_numpy().tolist() == values[::-1].tolist()


@IGNORE_NETCDF_SHAPE_WARNING
def test_run_data_retrieval_historical(tmp_path, monkeypatch):
    """
    Test that a historical density is downloaded and saved as a count.

    The density of 2020, one person per square kilometre on cells of
    0.1 degrees, is downloaded into the raw folder, and the population
    of the entity, at 0.25 degrees, is the area of its bounds in square
    kilometres.
    """
    downloads = _serve(
        monkeypatch,
        {
            _sedac_url(2020): _raster_bytes(
                tmp_path, np.ones((5, 5)), 0, 0.5, 0.1
            )
        },
    )
    monkeypatch.setattr(
        gridded_population.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA"],
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_shape",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_bounds",
        lambda _: [0, 0, 0.5, 0.5],
    )

    gridded_population.run_data_retrieval("FRA", None, 2020, None, None, None)

    assert [url for url, _ in downloads] == [_sedac_url(2020)]
    assert os.listdir(utils.paths.get_gridded_folder("population", "raw")) == [
        "2020.tif"
    ]
    with xarray.open_dataarray(
        utils.paths.get_gridded_file("population", "FRA", 2020, None)
    ) as population:
        assert np.allclose(np.diff(population["x"]), 0.25)
        assert np.allclose(np.diff(population["y"]), 0.25)
        area = np.pi / 180 * 6371.0**2 * 0.5 * np.sin(np.deg2rad(0.5))
        assert float(population.sum()) == pytest.approx(area, rel=1e-4)


@IGNORE_NETCDF_SHAPE_WARNING
def test_run_data_retrieval_future(tmp_path, monkeypatch):
    """
    Test that a future population is downloaded, read and extracted.

    The archive of SSP2 is extracted into the raw folder, and the grid
    of the entity has the counts of the cells within its bounds, which
    are not converted from a density.
    """
    raster_path = os.path.join(tmp_path, "SSP2_2030.tif")
    _write_raster(raster_path, np.arange(16.0).reshape(4, 4), 0, 4, 1)
    with open(raster_path, "rb") as file:
        archive = _archive({"SPP2/SSP2_2030.tif": file.read()})
    _serve(monkeypatch, {FIGSHARE_URLS["SSP2"]: archive})
    monkeypatch.setattr(
        gridded_population.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA"],
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_shape",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_bounds",
        lambda _: [-100, -50, 100, 50],
    )
    monkeypatch.setattr(
        gridded_population.utils.geospatial,
        "coarsen",
        lambda grid, _bounds: grid,
    )

    gridded_population.run_data_retrieval(
        "FRA", None, 2030, None, None, "SSP2"
    )

    raw_folder = utils.paths.get_gridded_folder("population", "raw")
    assert os.listdir(raw_folder) == ["SSP2"]
    with xarray.open_dataarray(
        utils.paths.get_gridded_file("population", "FRA", 2030, "SSP2")
    ) as population:
        assert population.to_numpy().tolist() == [[9, 10], [5, 6]]


@IGNORE_NETCDF_SHAPE_WARNING
def test_run_data_retrieval(monkeypatch):
    """
    Test that the grid of each entity is saved in the processed folder.

    The density of the historical years is converted to a count, and
    the future grids, which are counts already, are kept.
    """
    global_grid = xarray.DataArray(
        np.ones((4, 4)),
        coords={"y": [0.5, 1.5, 2.5, 3.5], "x": [0.5, 1.5, 2.5, 3.5]},
        dims=["y", "x"],
    )
    read = []
    converted = []

    def read_population_dataset(folder, year, scenario):
        """
        Record a read and give the global grid.

        Returns
        -------
        xarray.DataArray
            The global grid.
        """
        read.append((folder, year, scenario))
        return global_grid

    def from_density_to_count(grid):
        """
        Record a conversion and keep the grid as it is.

        Returns
        -------
        xarray.DataArray
            The grid.
        """
        converted.append(grid)
        return grid

    monkeypatch.setattr(
        gridded_population.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA"],
    )
    for name in (
        "_download_historical_gridded_population_density",
        "_download_future_gridded_population",
    ):
        monkeypatch.setattr(gridded_population, name, lambda *_: None)
    monkeypatch.setattr(
        gridded_population,
        "_read_population_dataset",
        read_population_dataset,
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_shape",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        gridded_population.utils.shapes,
        "get_entity_bounds",
        lambda _: (0, 0, 4, 4),
    )
    monkeypatch.setattr(
        gridded_population.utils.geospatial,
        "from_density_to_count",
        from_density_to_count,
    )
    monkeypatch.setattr(
        gridded_population.utils.geospatial,
        "coarsen",
        lambda grid, _bounds: grid,
    )

    gridded_population.run_data_retrieval("FRA", None, 2020, None, None, None)
    gridded_population.run_data_retrieval(
        "FRA", None, 2030, None, None, "SSP2"
    )

    raw_folder = utils.paths.get_gridded_folder("population", "raw")
    assert read == [(raw_folder, 2020, None), (raw_folder, 2030, "SSP2")]
    assert len(converted) == 1
    assert sorted(
        os.listdir(utils.paths.get_gridded_folder("population", "processed"))
    ) == ["FRA_0.25_deg_2020.nc", "FRA_0.25_deg_2030_SSP2.nc"]

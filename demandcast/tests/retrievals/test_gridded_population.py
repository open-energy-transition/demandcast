"""
License: AGPL-3.0.

Description:

    Tests for the download of the future gridded population from
    Figshare, with a small archive in place of the real one, and for
    the extraction of the population of each country and subdivision,
    with a small global grid in place of the downloaded ones.
"""

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import utils.paths
import xarray
from retrievals import gridded_population


def _archive(folder: str) -> bytes:
    """
    Make a zip archive with a single file in a folder.

    Parameters
    ----------
    folder : str
        The folder of the file in the archive.

    Returns
    -------
    bytes
        The content of the archive.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{folder}/population.tif", b"data")
    return buffer.getvalue()


def _response(content: bytes) -> MagicMock:
    """
    Make a streamed response that returns the content in chunks.

    Parameters
    ----------
    content : bytes
        The content of the response.

    Returns
    -------
    unittest.mock.MagicMock
        The response, usable as a context manager.
    """
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [content[:10], content[10:]]
    return response


def test_download_future_gridded_population(tmp_path):
    """
    Test the download of the population of a scenario.

    The archive is downloaded from the download server of Figshare and
    extracted, its folder is renamed to the scenario, and the archive
    is removed.
    """
    with patch(
        "requests.get", return_value=_response(_archive("SPP1"))
    ) as get:
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP1"
        )

    url = get.call_args.args[0]
    assert url.startswith("https://ndownloader.figshare.com/files/")
    assert os.path.exists(tmp_path / "SSP1" / "population.tif")
    assert not os.path.exists(tmp_path / "SSP1.zip")


def test_download_future_gridded_population_not_a_zip(tmp_path):
    """
    Test that a response that is not an archive raises an error.

    The partial file is removed, so that the next run downloads again.
    """
    with (
        patch("requests.get", return_value=_response(b"<html></html>")),
        pytest.raises(zipfile.BadZipFile),
    ):
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP3"
        )

    assert not os.path.exists(tmp_path / "SSP3.zip")


# The netCDF4 library sets the shape of arrays, which NumPy 2.5
# deprecates.
@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)
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
        read.append((folder, year, scenario))
        return global_grid

    def from_density_to_count(grid):
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

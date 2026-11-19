"""
License: AGPL-3.0.

Description:

    Tests for the extraction of the grid of each country and
    subdivision from a global grid, with synthetic grids and shapes:
    when a grid is kept, and when it is extracted again.
"""

import os

import numpy as np
import pytest
import xarray

import retrievals.gridded
import utils.shapes


def _global_grid() -> xarray.DataArray:
    """
    Make a global grid of 6 by 6 cells of one degree.

    Returns
    -------
    xarray.DataArray
        The grid, with the coordinates x and y from 0 to 5.
    """
    return xarray.DataArray(
        np.ones((6, 6)),
        coords={"y": np.arange(6.0), "x": np.arange(6.0)},
        dims=["y", "x"],
    )


@pytest.fixture
def shape_bounds(monkeypatch):
    """
    Give the shapes of all the codes the bounds of a list.

    Returns
    -------
    list[float]
        The bounds, west, south, east and north, to change in place.
    """
    bounds = [0.0, 0.0, 2.0, 2.0]
    monkeypatch.setattr(
        utils.shapes, "get_entity_shape", lambda *_, **__: None
    )
    monkeypatch.setattr(
        utils.shapes, "get_entity_bounds", lambda _shape: list(bounds)
    )
    return bounds


def _extract(tmp_path, extracted: list[str]) -> str:
    """
    Extract the grid of FRA, and record each extraction.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The folder of the file of the grid.
    extracted : list[str]
        The codes extracted, to which FRA is added if it is.

    Returns
    -------
    str
        The path of the file of the grid.
    """
    file_path = os.path.join(tmp_path, "FRA.nc")

    def process(grid, _bounds):
        """
        Record the extraction and keep the grid as it is.

        Returns
        -------
        xarray.DataArray
            The grid.
        """
        extracted.append("FRA")
        return grid

    retrievals.gridded.extract_entity_grids(
        _global_grid(), ["FRA"], lambda _code: file_path, "test", process
    )
    return file_path


def test_grid_is_extracted_again_when_its_bounds_change(
    tmp_path, shape_bounds
):
    """
    Test that a grid is extracted again when the shape changes.

    The grid records the bounds of the shape that it was cut with, is
    kept while they stay the same, and is cut again with the new bounds
    once a change of the shape moves them, in a later run.
    """
    extracted: list[str] = []
    file_path = _extract(tmp_path, extracted)
    _extract(tmp_path, extracted)
    assert extracted == ["FRA"]

    shape_bounds[2:] = [4.0, 3.0]
    retrievals.gridded.get_bounds.cache_clear()
    _extract(tmp_path, extracted)

    assert extracted == ["FRA", "FRA"]
    with xarray.open_dataarray(file_path) as grid:
        assert grid.attrs[retrievals.gridded.BOUNDS_KEY].tolist() == [
            0.0,
            0.0,
            4.0,
            3.0,
        ]
        assert grid["x"].to_numpy().tolist() == [0, 1, 2, 3, 4]
        assert grid["y"].to_numpy().tolist() == [0, 1, 2, 3]


@pytest.mark.usefixtures("shape_bounds")
def test_grid_without_bounds_is_extracted_again(tmp_path):
    """
    Test that a grid that records no bounds is extracted again.

    Such a grid was saved before the bounds were recorded, so its shape
    is not known.
    """
    file_path = os.path.join(tmp_path, "FRA.nc")
    _global_grid().to_netcdf(file_path)
    assert not retrievals.gridded.is_current(file_path, "FRA")

    extracted: list[str] = []
    _extract(tmp_path, extracted)

    assert extracted == ["FRA"]
    assert retrievals.gridded.is_current(file_path, "FRA")


@pytest.mark.usefixtures("shape_bounds")
def test_bounds_of_a_dataset_and_of_a_missing_grid(tmp_path):
    """
    Test the bounds of a grid of several variables, and of no grid.

    A dataset records the bounds in its own attributes, and a grid
    without a file is not current.
    """
    file_path = os.path.join(tmp_path, "FRA.nc")
    assert not retrievals.gridded.is_current(file_path, "FRA")

    dataset = _global_grid().to_dataset(name="t2m")
    retrievals.gridded.record_bounds(dataset, [0, 0, 2, 2]).to_netcdf(
        file_path
    )

    with xarray.open_dataset(file_path) as saved:
        assert retrievals.gridded.BOUNDS_KEY in saved.attrs
    assert retrievals.gridded.is_current(file_path, "FRA")

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


def test_grids_of_several_codes_are_processed_and_saved(tmp_path, monkeypatch):
    """
    Test the grids of several codes, each cut to its own bounds.

    The processing gets the bounds of the shape of each code, the grid
    saved is the processed one, and a file that is not up to date is
    extracted again although it records the current bounds.
    """
    bounds_of = {"FRA": [0.0, 0.0, 2.0, 1.0], "DEU": [3.0, 2.0, 5.0, 5.0]}
    monkeypatch.setattr(
        utils.shapes, "get_entity_shape", lambda code, **_: code
    )
    monkeypatch.setattr(
        utils.shapes, "get_entity_bounds", lambda code: bounds_of[code]
    )
    processed: list[list[float]] = []

    def process(grid, bounds):
        """
        Record the bounds and double the grid.

        Returns
        -------
        xarray.DataArray
            The grid, doubled.
        """
        processed.append(bounds)
        return grid * 2

    def extract(is_up_to_date):
        """Extract the grids of FRA and DEU."""
        retrievals.gridded.extract_entity_grids(
            _global_grid(),
            ["FRA", "DEU"],
            lambda code: os.path.join(tmp_path, f"{code}.nc"),
            "test",
            process,
            is_up_to_date,
        )

    extract(os.path.exists)
    extract(os.path.exists)
    assert processed == [bounds_of["FRA"], bounds_of["DEU"]]
    extract(lambda _file_path: False)
    assert processed == 2 * [bounds_of["FRA"], bounds_of["DEU"]]

    for code, x, y in [
        ("FRA", [0, 1, 2], [0, 1]),
        ("DEU", [3, 4, 5], [2, 3, 4, 5]),
    ]:
        file_path = os.path.join(tmp_path, f"{code}.nc")
        with xarray.open_dataarray(file_path) as grid:
            assert grid["x"].to_numpy().tolist() == x
            assert grid["y"].to_numpy().tolist() == y
            assert (grid.to_numpy() == 2.0).all()
            assert (
                grid.attrs[retrievals.gridded.BOUNDS_KEY].tolist()
                == (bounds_of[code])
            )


def test_failed_code_does_not_stop_the_others(tmp_path, monkeypatch):
    """Test that the grids of the other codes are saved if one fails."""
    monkeypatch.setattr(
        utils.shapes, "get_entity_shape", lambda code, **_: code
    )

    def get_entity_bounds(code):
        """
        Give the bounds of FRA, and fail for the other codes.

        Returns
        -------
        list[float]
            The bounds of FRA.

        Raises
        ------
        ValueError
            For a code other than FRA.
        """
        if code != "FRA":
            raise ValueError(f"No shape for {code}")
        return [0.0, 0.0, 2.0, 2.0]

    monkeypatch.setattr(utils.shapes, "get_entity_bounds", get_entity_bounds)

    with pytest.raises(RuntimeError, match="1 of 2 codes: XXX"):
        retrievals.gridded.extract_entity_grids(
            _global_grid(),
            ["XXX", "FRA"],
            lambda code: os.path.join(tmp_path, f"{code}.nc"),
            "test",
        )

    assert sorted(os.listdir(tmp_path)) == ["FRA.nc"]
    assert retrievals.gridded.is_current(
        os.path.join(tmp_path, "FRA.nc"), "FRA"
    )


@pytest.mark.usefixtures("shape_bounds")
def test_unreadable_grid_is_extracted_again(tmp_path, caplog):
    """Test that a grid whose file cannot be read is extracted again."""
    file_path = os.path.join(tmp_path, "FRA.nc")
    with open(file_path, "wb") as file:
        file.write(b"not a NetCDF file")

    extracted: list[str] = []
    _extract(tmp_path, extracted)

    assert extracted == ["FRA"]
    assert "cannot be read, so it is retrieved again" in caplog.text
    assert retrievals.gridded.is_current(file_path, "FRA")


@pytest.mark.parametrize(
    ("bounds", "x", "y"),
    [
        # Bounds with cells inside them.
        ([0.5, 1.5, 3.5, 2.5], [1, 2, 3], [2]),
        # Bounds between two cells, nearer to one, or to each.
        ([1.1, 4.1, 1.3, 4.3], [1], [4]),
        ([1.2, 4.3, 1.8, 4.7], [1, 2], [4, 5]),
        # Bounds beyond the last cell.
        ([5.5, 0.0, 6.5, 0.4], [5], [0]),
    ],
)
def test_bounds_without_cells_get_the_nearest(bounds, x, y):
    """
    Test that bounds without a cell inside get the nearest cells.

    A grid coarser than the bounds, such as that of a climate model for
    a small island, has no cell inside them along x or y. The cells
    nearest to each of the two bounds are those nearest to any point
    between them.
    """
    grid = retrievals.gridded.select_bounds(_global_grid(), bounds)

    assert grid["x"].to_numpy().tolist() == x
    assert grid["y"].to_numpy().tolist() == y


def test_grid_without_cells_is_extracted_again(tmp_path, shape_bounds, caplog):
    """
    Test that a grid without cells is extracted again, with cells.

    The bounds of the shape are between two cells along x, so the grid
    has the nearest cell. A grid saved without a cell, with the same
    bounds, is not current.
    """
    shape_bounds[:] = [1.1, 0.0, 1.3, 2.0]
    file_path = os.path.join(tmp_path, "FRA.nc")
    retrievals.gridded.record_bounds(
        _global_grid().isel(x=[]), shape_bounds
    ).to_netcdf(file_path)

    with caplog.at_level("WARNING"):
        assert not retrievals.gridded.is_current(file_path, "FRA")
    assert "has no cell, so it is retrieved again" in caplog.text

    extracted: list[str] = []
    _extract(tmp_path, extracted)

    assert extracted == ["FRA"]
    with xarray.open_dataarray(file_path) as grid:
        assert grid["x"].to_numpy().tolist() == [1]
        assert grid["y"].to_numpy().tolist() == [0, 1, 2]

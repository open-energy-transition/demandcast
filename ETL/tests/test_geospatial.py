# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the geospatial module in the ETL
    utility package.
"""

import tempfile
from pathlib import Path

import geopandas
import numpy
import pytest
import utils.directories
import utils.geospatial
import xarray
from shapely import box


def test_harmonize_coords():
    """
    Test the harmonization of geospatial coordinates.

    This function tests the harmonize_coords function to ensure it
    correctly transforms coordinate names and values in an xarray
    Dataset..
    """
    # Test the renaming of longitude and latitude to x and y.
    ds = xarray.Dataset(coords={"longitude": [0, 20], "latitude": [50, 60]})
    result = utils.geospatial.harmonize_coords(ds)
    assert "x" in result.coords and "y" in result.coords

    # Test the renaming of lon and lat to x and y.
    ds = xarray.Dataset(coords={"lon": [0, 20], "lat": [50, 60]})
    result = utils.geospatial.harmonize_coords(ds)
    assert "x" in result.coords and "y" in result.coords

    # Test the remapping of longitudes from [0, 360] to [-180, 180].
    ds = xarray.Dataset(coords={"x": [0, 90, 270], "y": [50, 60]})
    result = utils.geospatial.harmonize_coords(ds)
    assert numpy.all(result["x"].values >= -180)
    assert numpy.all(result["x"].values <= 180)

    # Test the dropping of duplicate coordinates.
    ds = xarray.Dataset(coords={"x": [0, 0, 10], "y": [50, 60]})
    n_duplicates = len(ds["x"].values) - len(numpy.unique(ds["x"].values))
    result = utils.geospatial.harmonize_coords(ds)
    assert len(result["x"].values) == len(ds["x"].values) - n_duplicates

    # Test the handling of coordinates with values outside the valid
    # range.
    ds = xarray.Dataset(coords={"x": [-200, -170], "y": [50, 60]})
    with pytest.raises(ValueError):
        utils.geospatial.harmonize_coords(ds)
    ds = xarray.Dataset(coords={"x": [-10, 200], "y": [50, 60]})
    with pytest.raises(ValueError):
        utils.geospatial.harmonize_coords(ds)

    # Test the sorting of coordinates.
    ds = xarray.Dataset(coords={"x": [60, 50], "y": [60, 50]})
    result = utils.geospatial.harmonize_coords(ds)
    sorted_x = numpy.sort(ds["x"].values)
    assert numpy.allclose(result["x"].values, sorted_x)
    sorted_y = numpy.sort(ds["y"].values)
    assert numpy.allclose(result["y"].values, sorted_y)


def test_clean_raster():
    """
    Test the cleaning of raster data.

    This function tests the clean_raster utility function to ensure it
    correctly removes unnecessary dimensions and coordinates from an
    xarray DataArray.
    """
    # Create a mock DataArray with 'band' dimension and extra variables.
    data = xarray.DataArray(
        numpy.random.rand(1, 5, 5),
        dims=["band", "y", "x"],
        coords={"band": [1], "spatial_ref": 0},
        name="original_var",
        attrs={"description": "test raster"},
    )

    # Clean the raster data using the utility function.
    cleaned = utils.geospatial.clean_raster(data, "cleaned_var")

    # Check the properties of the cleaned DataArray.
    assert isinstance(cleaned, xarray.DataArray)
    assert cleaned.name == "cleaned_var"
    assert "band" not in cleaned.dims
    assert "band" not in cleaned.coords
    assert "spatial_ref" not in cleaned.coords
    assert cleaned.attrs == {}
    assert cleaned.shape == (5, 5)


def test_get_fraction_of_grid_cells_in_shape(monkeypatch):
    """
    Test the calculation of the fraction of grid cells in a shape.

    This function tests the get_fraction_of_grid_cells_in_shape utility
    function to ensure it correctly calculates the fraction of grid
    cells that fall within a specified shape and generates a plot.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        A pytest fixture that allows us to modify the behavior of the
        utils.directories.read_folders_structure function to return a
        temporary directory.
    """
    # Create a temporary directory for figure output.
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the utils.directories.read_folders_structure to return
        # the temp path.
        monkeypatch.setattr(
            utils.directories,
            "read_folders_structure",
            lambda: {"figures_folder": tmpdir},
        )

        # Create a simple square geometry over lat/lon coordinates.
        entity_shape = geopandas.GeoDataFrame(
            geometry=[box(0, 0, 1, 1)], crs="EPSG:4326", index=["test"]
        )

        # Run the function.
        fraction = utils.geospatial.get_fraction_of_grid_cells_in_shape(
            entity_shape, resolution=0.5, make_plot=True
        )

        # Validate the output.
        assert isinstance(fraction, xarray.DataArray)
        assert "x" in fraction.coords
        assert "y" in fraction.coords
        assert fraction.ndim == 2
        assert numpy.all(fraction.values >= 0.0)
        assert numpy.all(fraction.values <= 1.0)
        assert numpy.any(fraction.values > 0.0)

        # Assert that the figure was created.
        expected_path = (
            Path(tmpdir) / "fraction_of_grid_cells_in_shape_test.png"
        )
        assert expected_path.exists()
        assert expected_path.stat().st_size > 0


def test_get_largest_values_in_shape():
    """
    Test the extraction of the largest values in a shape.

    This function tests the get_largest_values_in_shape utility function
    to ensure it correctly extracts the largest grid cells within a
    specified shape from an xarray DataArray.
    """
    # Create a simple GeoDataFrame (1x1 degree box over lat/lon).
    shape = geopandas.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    # Create a small xarray.DataArray with made-up data.
    lat = numpy.array([0.0, 0.25, 0.5, 0.75, 1.0])
    lon = numpy.array([0.0, 0.25, 0.5, 0.75, 1.0])
    values = numpy.arange(25).reshape((5, 5))
    data = xarray.DataArray(
        data=values,
        coords={"y": lat, "x": lon},
        dims=["y", "x"],
        name="test_data",
    )

    # Call the function to extract largest grid cells inside the shape.
    number_of_cells = 3
    result = utils.geospatial.get_largest_values_in_shape(
        shape, data, number_of_cells
    )

    # Check the result.
    assert isinstance(result, xarray.DataArray)
    assert result.dims == ("z",)
    assert numpy.all(result.values == numpy.array([22, 23, 24]))


def test_coarsen_function():
    """
    Test the coarsening of geospatial data.

    This function tests the coarsen utility function to ensure it
    correctly reduces the resolution of an xarray DataArray within a
    specified bounding box and target resolution.
    """
    # Create fine-resolution sample data (0.1° x 0.1°).
    lon = numpy.arange(-1.0, 1.1, 0.1)
    lat = numpy.arange(-1.0, 1.1, 0.1)
    data = numpy.ones((len(lat), len(lon)))
    da = xarray.DataArray(
        data, coords={"y": lat, "x": lon}, dims=["y", "x"], name="test_var"
    )

    # Set bounds and target resolution for coarsening.
    bounds = [-0.75, -0.8, 0.75, 0.8]  # West, South, East, North
    target_resolution = 0.25

    # Apply the coarsening function.
    result = utils.geospatial.coarsen(da, bounds, target_resolution)

    # Check the result.
    assert isinstance(result, xarray.DataArray)
    assert "x" in result.coords and "y" in result.coords
    assert result.ndim == 2
    assert result.shape[0] < da.shape[0]
    assert result.shape[1] < da.shape[1]
    assert numpy.allclose(numpy.diff(result["x"].values), 0.25)
    assert numpy.allclose(numpy.diff(result["y"].values), 0.25)

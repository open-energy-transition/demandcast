"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the geospatial module.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import geopandas
import numpy as np
import pytest
import utils.geospatial
import utils.paths
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
    assert "x" in result.coords
    assert "y" in result.coords

    # Test the renaming of lon and lat to x and y.
    ds = xarray.Dataset(coords={"lon": [0, 20], "lat": [50, 60]})
    result = utils.geospatial.harmonize_coords(ds)
    assert "x" in result.coords
    assert "y" in result.coords

    # Test the remapping of longitudes from [0, 360] to [-180, 180].
    ds = xarray.Dataset(coords={"x": [0, 90, 270], "y": [50, 60]})
    result = utils.geospatial.harmonize_coords(ds)
    assert np.all(result["x"].to_numpy() >= -180)
    assert np.all(result["x"].to_numpy() <= 180)

    # Test the dropping of duplicate coordinates.
    ds = xarray.Dataset(coords={"x": [0, 0, 10], "y": [50, 60]})
    n_duplicates = len(ds["x"]) - len(np.unique(ds["x"]))
    result = utils.geospatial.harmonize_coords(ds)
    assert len(result["x"]) == len(ds["x"]) - n_duplicates

    # Test the handling of coordinates with values outside the valid
    # range.
    ds = xarray.Dataset(coords={"x": [-200, -170], "y": [50, 60]})
    with pytest.raises(ValueError, match="contains values less than -180"):
        utils.geospatial.harmonize_coords(ds)
    ds = xarray.Dataset(coords={"x": [-10, 200], "y": [50, 60]})
    with pytest.raises(ValueError, match="contains values greater than 180"):
        utils.geospatial.harmonize_coords(ds)

    # Test the sorting of coordinates.
    ds = xarray.Dataset(coords={"x": [60, 50], "y": [60, 50]})
    result = utils.geospatial.harmonize_coords(ds)
    sorted_x = np.sort(ds["x"])
    assert np.allclose(result["x"], sorted_x)
    sorted_y = np.sort(ds["y"])
    assert np.allclose(result["y"], sorted_y)


def test_clean_raster():
    """
    Test the cleaning of raster data.

    This function tests the clean_raster utility function to ensure it
    correctly removes unnecessary dimensions and coordinates from an
    xarray DataArray.
    """
    # Create a mock DataArray with 'band' dimension and extra variables.
    data = xarray.DataArray(
        np.random.default_rng(0).random((1, 5, 5)),
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

    This function tests the _get_fraction_of_grid_cells_in_shape utility
    function to ensure it correctly calculates the fraction of grid
    cells that fall within a specified shape and generates a plot.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        A pytest fixture that allows us to modify the behavior of the
        folder of the figures to return a temporary directory.
    """
    # Create a temporary directory for figure output.
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the figures in the temporary directory.
        monkeypatch.setattr(
            utils.paths,
            "get_results_folder",
            lambda _kind: tmpdir,
        )

        # Create a simple xarray.DataArray with made-up data.
        lat = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        lon = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        values = np.arange(25).reshape((5, 5))
        xarray_data = xarray.DataArray(
            data=values,
            coords={"y": lat, "x": lon},
            dims=["y", "x"],
            name="test_data",
        )

        # Create a simple square geometry over lat/lon coordinates.
        entity_shape = geopandas.GeoDataFrame(
            geometry=[box(0.5, 0.5, 1.5, 1.5)], crs="EPSG:4326", index=["test"]
        )

        # Run the function.
        fraction = utils.geospatial._get_fraction_of_grid_cells_in_shape(
            xarray_data, entity_shape, make_plot=True
        )

        # Validate the output.
        assert isinstance(fraction, xarray.DataArray)
        assert "x" in fraction.coords
        assert "y" in fraction.coords
        assert fraction.ndim == 2
        assert np.allclose(xarray_data.x.to_numpy(), fraction.x.to_numpy())
        assert np.allclose(xarray_data.y.to_numpy(), fraction.y.to_numpy())
        assert np.all(fraction.to_numpy() >= 0.0)
        assert np.all(fraction.to_numpy() <= 1.0)
        assert np.any(fraction.to_numpy() > 0.0)
        assert np.allclose(
            fraction.sel(x=1.0, y=1.0).to_numpy(), 1.0, atol=1e-2
        )
        assert np.allclose(
            fraction.sel(x=0.5, y=0.5).to_numpy(), 0.25, atol=1e-2
        )

        # Assert that the figure was created.
        expected_path = (
            Path(tmpdir) / "fraction_of_grid_cells_in_shape_test.png"
        )
        assert expected_path.exists()
        assert expected_path.stat().st_size > 0


def test_from_density_to_count():
    """
    Test the conversion from density to count.

    This function tests the from_density_to_count utility function to
    ensure it correctly converts a density grid (in counts per square
    kilometer) to a count grid based on the area of each grid cell.
    """
    # Create a simple 3x2 density grid in counts per sq km.
    lat = np.array([10, 10.5, 11])
    lon = np.array([20, 20.5])
    density_values = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    density_grid = xarray.DataArray(
        data=density_values,
        coords={"y": lat, "x": lon},
        dims=["y", "x"],
        name="density",
    )

    # Define constants for area calculation.
    resolution = 0.5  # degrees
    earth_radius = 6371.0

    # Calculate boundary latitudes.
    boundary_lat = np.concatenate(
        [
            [lat[0] - 0.5 * resolution],
            0.5 * (lat[1:] + lat[:-1]),
            [lat[-1] + 0.5 * resolution],
        ]
    )  # [9.75, 10.25, 10.75, 11.25]

    # For each latitude index, get lower and upper boundaries.
    lower_lat = boundary_lat[:-1]  # [9.75, 10.25, 10.75]
    upper_lat = boundary_lat[1:]  # [10.25, 10.75, 11.25]

    # Compute expected area for each grid cell.
    area = (
        (np.pi / 180)
        * earth_radius**2
        * resolution
        * (np.sin(np.deg2rad(upper_lat)) - np.sin(np.deg2rad(lower_lat)))
    )
    # Repeat area for each longitude (2 columns).
    expected_area = np.tile(area, (2, 1)).T  # Shape (3,2)

    # Calculate expected counts.
    expected_counts = density_values * expected_area

    # Run function to convert density to count.
    output = utils.geospatial.from_density_to_count(density_grid)

    # Assert shape and values are correct.
    assert output.shape == density_grid.shape
    np.testing.assert_allclose(output.to_numpy(), expected_counts, rtol=1e-6)

    # Assert output coordinates match input.
    assert np.all(output.x.to_numpy() == density_grid.x.to_numpy())
    assert np.all(output.y.to_numpy() == density_grid.y.to_numpy())


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
    lat = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    lon = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    values = np.arange(25).reshape((5, 5))
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
    assert np.all(result.to_numpy() == np.array([22, 23, 24]))


def test_coarsen_function():
    """
    Test the coarsening of geospatial data.

    This function tests the coarsen utility function to ensure it
    correctly reduces the resolution of an xarray DataArray within a
    specified bounding box and target resolution.
    """
    # Create fine-resolution sample data (0.1° x 0.1°).
    lon = np.arange(-1.0, 1.1, 0.1)
    lat = np.arange(-1.0, 1.1, 0.1)
    data = np.ones((len(lat), len(lon)))
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
    assert "x" in result.coords
    assert "y" in result.coords
    assert result.ndim == 2
    assert result.shape[0] < da.shape[0]
    assert result.shape[1] < da.shape[1]
    assert np.allclose(np.diff(result["x"]), 0.25)
    assert np.allclose(np.diff(result["y"]), 0.25)

    # Create a sample data with longitude coordinates beyond valid
    # range.
    lon = np.arange(-181.0, 181.0, 0.1)
    data = np.ones((len(lat), len(lon)))
    da = xarray.DataArray(
        data, coords={"y": lat, "x": lon}, dims=["y", "x"], name="test_var"
    )

    # Set bounds and target resolution for coarsening.
    bounds = [-180, -0.8, 180, 0.8]  # West, South, East, North
    target_resolution = 0.5

    # Apply the coarsening function.
    result = utils.geospatial.coarsen(da, bounds, target_resolution)

    # Check the result.
    assert result.x[0] == -180
    assert result.x[-1] == 180


def test_get_total_in_shape():
    """Test that the cells count for their fraction within the shape."""
    gridded_data = xarray.DataArray(
        np.array([[10.0, 20.0], [30.0, 40.0]]),
        coords={"y": [0.5, 1.5], "x": [0.5, 1.5]},
        dims=["y", "x"],
    )
    with patch(
        "utils.geospatial._get_fraction_of_grid_cells_in_shape",
        return_value=np.array([[1.0, 0.5], [0.0, 0.25]]),
    ):
        total = utils.geospatial.get_total_in_shape(
            gridded_data, geopandas.GeoDataFrame()
        )

    assert total == pytest.approx(10.0 + 10.0 + 10.0)

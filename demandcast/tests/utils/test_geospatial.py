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
import xarray
from shapely import box

import utils.geospatial
import utils.paths


def test_harmonize_coords():
    """Test the harmonization of geospatial coordinates."""
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

    # Test that longitudes in single precision, as in ARCO-ERA5, move
    # to the same points of the grid.
    ds = xarray.Dataset(
        coords={
            "x": np.array([2.25, 354.25], dtype="float32"),
            "y": [50, 60],
        }
    )
    result = utils.geospatial.harmonize_coords(ds)
    assert result["x"].to_numpy().tolist() == pytest.approx(
        [-5.75, 2.25], abs=1e-9
    )

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

    It removes the dimensions, coordinates and attributes that are not
    needed.
    """
    data = xarray.DataArray(
        np.random.default_rng(0).random((1, 5, 5)),
        dims=["band", "y", "x"],
        coords={"band": [1], "spatial_ref": 0},
        name="original_var",
        attrs={"description": "test raster"},
    )

    cleaned = utils.geospatial.clean_raster(data, "cleaned_var")

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

    It also makes a figure of the fractions.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the figures in the temporary directory.
        monkeypatch.setattr(
            utils.paths,
            "get_results_folder",
            lambda _kind: tmpdir,
        )

        lat = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        lon = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        values = np.arange(25).reshape((5, 5))
        xarray_data = xarray.DataArray(
            data=values,
            coords={"y": lat, "x": lon},
            dims=["y", "x"],
            name="test_data",
        )

        entity_shape = geopandas.GeoDataFrame(
            geometry=[box(0.5, 0.5, 1.5, 1.5)], crs="EPSG:4326", index=["test"]
        )

        fraction = utils.geospatial._get_fraction_of_grid_cells_in_shape(
            xarray_data, entity_shape, make_plot=True
        )

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

        expected_path = (
            Path(tmpdir) / "fraction_of_grid_cells_in_shape_test.png"
        )
        assert expected_path.exists()
        assert expected_path.stat().st_size > 0


def test_from_density_to_count():
    """
    Test the conversion from density to count.

    The density is in counts per square kilometre, and the count of
    each cell is its density times its area.
    """
    lat = np.array([10, 10.5, 11])
    lon = np.array([20, 20.5])
    density_values = np.array([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]])
    density_grid = xarray.DataArray(
        data=density_values,
        coords={"y": lat, "x": lon},
        dims=["y", "x"],
        name="density",
    )

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

    expected_counts = density_values * expected_area

    output = utils.geospatial.from_density_to_count(density_grid)

    assert output.shape == density_grid.shape
    np.testing.assert_allclose(output.to_numpy(), expected_counts, rtol=1e-6)
    assert np.all(output.x.to_numpy() == density_grid.x.to_numpy())
    assert np.all(output.y.to_numpy() == density_grid.y.to_numpy())


def test_get_largest_values_in_shape():
    """Test the extraction of the largest values in a shape."""
    shape = geopandas.GeoDataFrame(geometry=[box(0, 0, 1, 1)], crs="EPSG:4326")

    lat = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    lon = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    values = np.arange(25).reshape((5, 5))
    data = xarray.DataArray(
        data=values,
        coords={"y": lat, "x": lon},
        dims=["y", "x"],
        name="test_data",
    )

    number_of_cells = 3
    result = utils.geospatial.get_largest_values_in_shape(
        shape, data, number_of_cells
    )

    assert isinstance(result, xarray.DataArray)
    assert result.dims == ("z",)
    # The cells of the top row, 20 to 24, are half or a quarter in the
    # shape, so the largest values inside it are those of the full
    # cells below them.
    assert np.all(result.to_numpy() == np.array([16, 17, 18]))


def test_border_cell_ranks_by_its_values_inside():
    """
    Test that a cell at the border ranks by its part inside the shape.

    A cell of 1,000 people with 1% of its area in the shape has about
    10 people inside it, fewer than a cell of 100 people half inside it.
    """
    # Cells of 1 degree, centred on 0.5, 1.5 and 2.5 degrees, with
    # people in two of them, and a shape over half of the first and 1%
    # of the second.
    values = np.zeros((3, 3))
    values[1, 0] = 100.0
    values[1, 1] = 1000.0
    data = xarray.DataArray(
        data=values,
        coords={"y": [0.5, 1.5, 2.5], "x": [0.5, 1.5, 2.5]},
        dims=["y", "x"],
    )
    shape = geopandas.GeoDataFrame(
        geometry=[box(0.5, 1, 1.01, 2)], crs="EPSG:4326"
    )

    result = utils.geospatial.get_largest_values_in_shape(shape, data, 1)

    assert result["x"].to_numpy().tolist() == [0.5]
    assert result.to_numpy() == pytest.approx([50.0], rel=0.05)


def test_coarsen_function():
    """
    Test the coarsening of geospatial data.

    It reduces the resolution of the data within the bounds, also when
    the longitudes go beyond -180 and 180 degrees.
    """
    # Create fine-resolution sample data (0.1° x 0.1°).
    lon = np.arange(-1.0, 1.1, 0.1)
    lat = np.arange(-1.0, 1.1, 0.1)
    data = np.ones((len(lat), len(lon)))
    da = xarray.DataArray(
        data, coords={"y": lat, "x": lon}, dims=["y", "x"], name="test_var"
    )

    bounds = [-0.75, -0.8, 0.75, 0.8]  # West, South, East, North
    target_resolution = 0.25

    result = utils.geospatial.coarsen(da, bounds, target_resolution)

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

    bounds = [-180, -0.8, 180, 0.8]  # West, South, East, North
    target_resolution = 0.5

    result = utils.geospatial.coarsen(da, bounds, target_resolution)

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

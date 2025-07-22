# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to handle geospatial data.
"""

import atlite.gis
import geopandas
import numpy
import xarray

import utils.figures
import utils.shapes


def harmonize_coords(
    ds: xarray.DataArray | xarray.Dataset,
) -> xarray.DataArray | xarray.Dataset:
    """
    Rename coordinates and reset longitudes.

    This function renames the longitude and latitude coordinates to "x"
    and "y", respectively, and resets the longitudes from the range
    [0, 360] to [-180, 180]. It also sorts the dataset by the "y"
    coordinate to ensure a consistent order.

    Parameters
    ----------
    ds : xarray.Dataset or xarray.DataArray
        The xarray dataset or data array to harmonize.

    Returns
    -------
    xarray.Dataset or xarray.DataArray
        The harmonized xarray dataset or data array with renamed
        coordinates and reset longitudes.

    Raises
    ------
    ValueError
        If the x coordinate contains values less than -180 or greater
        than 180.
    """
    # Rename longitude and latitude coordinates to x and y coordinates.
    if "longitude" in ds.coords and "latitude" in ds.coords:
        ds = ds.rename({"longitude": "x", "latitude": "y"})
    elif "lon" in ds.coords and "lat" in ds.coords:
        ds = ds.rename({"lon": "x", "lat": "y"})

    # Reset longitudes from the range [0, 360] to [-180, 180].
    if ds["x"].min() >= 0:
        ds = ds.assign_coords(
            x=(ds["x"] + 179.99999) % 360 - 179.99999
        ).sortby("x")

    # Drop duplicate x coordinates if they exist.
    ds = ds.drop_duplicates("x")

    if ds["x"].min() < -180.01:
        raise ValueError(
            "The x coordinate contains values less than -180. "
            "Please ensure that the x coordinate is in the correct range."
        )
    elif float(ds["x"].max()) > 180.01:
        raise ValueError(
            "The x coordinate contains values greater than 180. "
            "Please ensure that the x coordinate is in the correct range."
        )

    # Sort the dataset by the y coordinate and return it.
    return ds.sortby("y")


def clean_raster(
    xarray_data: xarray.DataArray, variable_name: str
) -> xarray.DataArray:
    """
    Clean the xarray data imported from a raster file.

    This function cleans the xarray data imported from a raster file
    by dropping unnecessary variables, renaming the variable to the
    specified variable name, and removing the "band" and "spatial_ref"
    dimensions and attributes. It also squeezes the "band" dimension if
    it exists.

    Parameters
    ----------
    xarray_data : xarray.DataArray
        The xarray data to clean.
    variable_name : str
        The name of the variable to rename.

    Returns
    -------
    xarray.DataArray
        The cleaned xarray data.
    """
    # Drop unnecessary variables, rename the variable, and remove
    # unnecessary dimensions and attributes.
    xarray_data = xarray_data.squeeze("band")
    xarray_data = xarray_data.drop_vars(["band", "spatial_ref"])
    xarray_data = xarray_data.drop_attrs()
    return xarray_data.rename(variable_name)


def get_fraction_of_grid_cells_in_shape(
    entity_shape: geopandas.GeoDataFrame,
    resolution: float = 0.25,
    make_plot: bool = True,
) -> xarray.DataArray:
    """
    Calculate the fraction of each grid cell that is in the given shape.

    This function calculates the fraction of each grid cell that is
    contained within the specified country or subdivision shape. It
    creates a temporary cutout of the grid cells based on the bounds of
    the entity shape and computes the fraction of each grid cell that
    intersects with the shape. The resulting fraction is normalized to
    ensure that the values are between 0 and 1.

    Parameters
    ----------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the country or subdivision of interest.
    resolution : float, optional
        The resolution of the grid cells in degrees.
    make_plot : bool, optional
        Whether to make a plot of the fraction of the grid cells that
        are in the given country or subdivision.

    Returns
    -------
    fraction_of_grid_cells_in_shape : xarray.DataArray
        Fraction of each grid cell that is in the given shape.
    """
    # Calculate the lateral bounds for the cutout based on the lateral
    # bounds of the country or subdivision of interest.
    cutout_bounds = utils.shapes.get_entity_bounds(entity_shape)

    # Create a temporary cutout to have the grid cell of the country or
    # subdivision of interest.
    cutout = atlite.Cutout(
        "temporary_cutout",
        module="era5",
        bounds=cutout_bounds,
        dx=resolution,
        dy=resolution,
        time=slice("2013-01-01", "2013-01-02"),
    )

    # Calculate the fraction of each grid cell that is in the shape.
    fraction_of_grid_cells_in_shape_np = atlite.gis.compute_indicatormatrix(
        cutout.grid, entity_shape, orig_crs=4326, dest_crs=4326
    ).toarray()

    # Fix NaN and Inf values to 0.0 to avoid numerical issues.
    fraction_of_grid_cells_in_shape_np = numpy.nan_to_num(
        (
            fraction_of_grid_cells_in_shape_np.T
            / fraction_of_grid_cells_in_shape_np.sum(axis=1)
        ).T,
        nan=0.0,
        posinf=0.0,
        neginf=0.0,
    )

    # Convert the numpy array to a xarray DataArray.
    fraction_of_grid_cells_in_shape = xarray.DataArray(
        fraction_of_grid_cells_in_shape_np.reshape(
            len(cutout.data["y"]), len(cutout.data["x"])
        ),
        coords={"y": cutout.data["y"], "x": cutout.data["x"]},
    )

    # Clip the values between 0 and 1.
    fraction_of_grid_cells_in_shape = (
        fraction_of_grid_cells_in_shape / fraction_of_grid_cells_in_shape.max()
    )

    if make_plot:
        utils.figures.simple_plot(
            fraction_of_grid_cells_in_shape,
            f"fraction_of_grid_cells_in_shape_{entity_shape.index[0]}",
        )

    return fraction_of_grid_cells_in_shape


def get_largest_values_in_shape(
    entity_shape: geopandas.GeoDataFrame,
    xarray_data: xarray.DataArray,
    number_of_grid_cells: int,
) -> xarray.DataArray:
    """
    Get the grid cells with the largest values.

    This function extracts the grid cells with the largest values from
    the given xarray data within the specified country or subdivision
    shape. It first calculates the fraction of each grid cell that is
    contained within the shape, then stacks the xarray data to drop
    NaN values, and finally returns the grid cells with the largest
    values based on the specified number of grid cells.

    Parameters
    ----------
    entity_shape : geopandas.GeoDataFrame
        The shape of the country or subdivision of interest.
    xarray_data : xarray.DataArray
        The xarray data to extract the largest values from.
    number_of_grid_cells : int
        The number of grid cells to consider.

    Returns
    -------
    xarray.DataArray
        The grid cells with the largest values in the given shape.
    """
    # Calculate the fraction of each grid cell that is in the shapes.
    fraction_of_grid_cells_in_shape = get_fraction_of_grid_cells_in_shape(
        entity_shape, make_plot=False
    )

    # Rearrange the xarray data.
    xarray_data_rearranged = (
        xarray_data.where(fraction_of_grid_cells_in_shape > 0.0)
        .stack(z=("y", "x"))
        .dropna(dim="z")
    )

    # Return the grid cells with the largest values.
    return xarray_data_rearranged.sortby(xarray_data_rearranged).tail(
        number_of_grid_cells
    )


def coarsen(
    original_xarray: xarray.DataArray,
    bounds: list[float],
    target_resolution: float = 0.25,
) -> xarray.DataArray:
    """
    Coarsen the xarray data to the target resolution.

    This function coarsens the xarray data to the specified target
    resolution by aggregating the data into bins of the target
    resolution.

    Parameters
    ----------
    original_xarray : xarray.DataArray
        The xarray data to coarsen.
    bounds : list[float]
        The lateral bounds (West, South, East, North) used to clip the
        data.
    target_resolution : float, optional
        The target resolution of the coarsened data.

    Returns
    -------
    xarray.DataArray
        The coarsened xarray data.
    """
    # Get the original resolution of the xarray data.
    original_x_resolution = abs(
        original_xarray.x[1] - original_xarray.x[0]
    ).item()
    original_y_resolution = abs(
        original_xarray.y[1] - original_xarray.y[0]
    ).item()
    original_resolution = max(original_x_resolution, original_y_resolution)

    # Check if the target resolution is greater than the original
    # resolution.
    assert target_resolution > original_resolution, (
        "Target resolution must be greater than the original resolution."
    )

    # Check if the target resolution provides an integer number of bins.
    assert 360 % target_resolution == 0, (
        "Target resolution must result in an integer number when dividing 360."
    )

    # Define the new coarser resolution.
    x_list = numpy.linspace(-180, 180, int(360 / target_resolution) + 1)
    y_list = numpy.linspace(-90, 90, int(180 / target_resolution) + 1)

    # Calculate the left and right bounds of the x and y bins.
    x_left_bound = (
        next(x for x in x_list if x >= bounds[0]) - target_resolution / 2
    )
    x_right_bound = (
        next(x for x in x_list if x > bounds[2]) - target_resolution / 2
    )
    y_left_bound = (
        next(y for y in y_list if y >= bounds[1]) - target_resolution / 2
    )
    y_right_bound = (
        next(y for y in y_list if y > bounds[3]) - target_resolution / 2
    )

    # Define the bins where to aggregate the original data.
    x_bins = numpy.arange(
        x_left_bound,
        x_right_bound + target_resolution,
        target_resolution,
    )
    y_bins = numpy.arange(
        y_left_bound,
        y_right_bound + target_resolution,
        target_resolution,
    )

    # Calculate the midpoints of the bins in the x and y directions.
    x_bin_centers = (x_bins[:-1] + x_bins[1:]) / 2
    y_bin_centers = (y_bins[:-1] + y_bins[1:]) / 2

    # Aggregate the original data to the new coarser resolution, first
    # in the x direction and then in the y direction.
    coarsened_xarray = original_xarray.groupby_bins(
        "x", x_bins, labels=x_bin_centers
    ).sum()
    coarsened_xarray = coarsened_xarray.groupby_bins(
        "y", y_bins, labels=y_bin_centers
    ).sum()

    # Rename the bins to "x" and "y" and return the coarsened xarray.
    return coarsened_xarray.rename({"x_bins": "x", "y_bins": "y"})

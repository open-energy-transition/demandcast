# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to handle geospatial data.
"""

import importlib
import os

import geopandas
import numpy
import pandas
import xarray
from shapely import box

import utils.directories
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


def _get_fraction_of_grid_cells_in_shape(
    xarray_data: xarray.DataArray,
    entity_shape: geopandas.GeoDataFrame,
    make_plot: bool = True,
) -> xarray.DataArray:
    """
    Calculate the fraction of each grid cell that is in the given shape.

    This function calculates the fraction of each grid cell that is
    contained within the specified country or subdivision shape. It
    takes the grid cells defined by the xarray data and computes the
    intersection with the provided shape, returning a new xarray
    DataArray with the fraction of each grid cell that is in the shape.
    The resulting fraction is normalized to ensure that the values are
    between 0 and 1.

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
    # Ensure that the bounds of the entity shape are within gridded data
    # limits.
    assert (
        entity_shape.total_bounds[0] >= xarray_data.x.min().item()
        and entity_shape.total_bounds[2] <= xarray_data.x.max().item()
        and entity_shape.total_bounds[1] >= xarray_data.y.min().item()
        and entity_shape.total_bounds[3] <= xarray_data.y.max().item()
    ), (
        "The bounds of the entity shape must be within the bounds of the "
        "gridded data."
    )

    # Get the coordinates of the xarray data as a matrix.
    x_coords, y_coords = numpy.meshgrid(
        xarray_data.x.to_numpy(), xarray_data.y.to_numpy()
    )

    # Reshape the coordinates to a list of (x, y) pairs.
    coords = numpy.vstack([x_coords.ravel(), y_coords.ravel()]).T

    # Calculate half the grid cell size.
    half_cell = (coords[len(xarray_data.x) + 1] - coords[0]) / 2

    # Define the grid cells as boxes.
    grid_cells = [
        box(*c) for c in numpy.hstack((coords - half_cell, coords + half_cell))
    ]

    # Create the grid as a GeoDataFrame where each row has the
    # coordinates and the geometry of the grid cell.
    grid = geopandas.GeoDataFrame(
        {"x": coords[:, 0], "y": coords[:, 1], "geometry": grid_cells},
        crs="EPSG:4326",
    )

    # Calculate the cell area and the intersection area in an equal
    # area projection to get the fraction of each grid cell that is in
    # the shape.
    cell_area = grid.geometry.to_crs("+proj=cea").area
    intersection_area = (
        grid.geometry.intersection(entity_shape.union_all())
        .to_crs("+proj=cea")
        .area
    )

    # Calculate the fraction of each grid cell that is in the shape.
    fraction_of_grid_cells_in_shape_np = (
        intersection_area / cell_area
    ).to_numpy()

    # Some rounding errors can lead to fractions slightly above 1.
    # Set these values to 1.
    fraction_of_grid_cells_in_shape_np[
        numpy.isclose(fraction_of_grid_cells_in_shape_np, 1)
    ] = 1.0

    # Check that the fraction is between 0 and 1 and that there are
    # no NaN or infinite values.
    assert numpy.all(
        (fraction_of_grid_cells_in_shape_np >= 0)
        & (fraction_of_grid_cells_in_shape_np <= 1)
    ), "The fraction of grid cells in shape must be between 0 and 1."
    assert not numpy.any(numpy.isnan(fraction_of_grid_cells_in_shape_np)), (
        "The fraction of grid cells in shape must not contain NaN values."
    )
    assert not numpy.any(numpy.isinf(fraction_of_grid_cells_in_shape_np)), (
        "The fraction of grid cells in shape must not contain infinite values."
    )

    # Convert the numpy array to a xarray DataArray.
    fraction_of_grid_cells_in_shape = xarray.DataArray(
        fraction_of_grid_cells_in_shape_np.reshape(
            len(xarray_data.y), len(xarray_data.x)
        ),
        coords={"y": xarray_data.y, "x": xarray_data.x},
    )

    if make_plot:
        utils.figures.simple_plot(
            fraction_of_grid_cells_in_shape,
            f"fraction_of_grid_cells_in_shape_{entity_shape.index[0]}",
        )

    return fraction_of_grid_cells_in_shape


def from_density_to_count(
    density: xarray.DataArray,
) -> xarray.DataArray:
    """
    Convert density to count.

    This function converts a density xarray to a count xarray by
    calculating the area of each grid cell in square kilometers and
    multiplying the density by the area.

    Parameters
    ----------
    density : xarray.DataArray
        The density data in counts per square kilometer.

    Returns
    -------
    xarray.DataArray
        The counts in the grid cells.
    """
    # Calculate the x and y resolutions of the grid cells in degrees.
    x_resolution = density.x[1:].to_numpy() - density.x[:-1].to_numpy()
    y_resolution = density.y[1:].to_numpy() - density.y[:-1].to_numpy()

    # Check that the resolution of the grid cells is uniform along each
    # axis.
    assert numpy.allclose(x_resolution, x_resolution[0]), (
        "The x resolution must be uniform."
    )
    assert numpy.allclose(y_resolution, y_resolution[0]), (
        "The y resolution must be uniform."
    )

    # Check that the resolution is the same in both directions.
    assert numpy.allclose(x_resolution[0], y_resolution[0]), (
        "The x and y resolutions must be the same. "
        f"Got {x_resolution[0]} and {y_resolution[0]}."
    )

    # Get the resolution in degrees.
    resolution = x_resolution[0]

    # Extract the longitudes and latitudes values.
    longitudes = density.x.to_numpy()
    latitudes = density.y.to_numpy()

    # Calculate the latitude values of the grid cell boundaries.
    boundary_latitudes = numpy.concatenate(
        [
            [latitudes[0] - resolution / 2],
            0.5 * (latitudes[1:] + latitudes[:-1]),
            [latitudes[-1] + resolution / 2],
        ]
    )

    # Create an xarray DataArray for the boundary latitudes.
    boundary_latitudes = xarray.Dataset(
        data_vars={
            "upper_lat": (
                ["y", "x"],
                numpy.tile(boundary_latitudes[1:], (len(longitudes), 1)).T,
            ),
            "lower_lat": (
                ["y", "x"],
                numpy.tile(boundary_latitudes[:-1], (len(longitudes), 1)).T,
            ),
        },
        coords={"y": latitudes, "x": longitudes},
    )

    # Define the radius of the Earth in kilometers.
    R = 6371.0

    # Calculate the area of each grid cell in square kilometers.
    area = (
        (numpy.pi / 180)
        * R**2
        * resolution
        * (
            numpy.sin(numpy.deg2rad(boundary_latitudes["upper_lat"]))
            - numpy.sin(numpy.deg2rad(boundary_latitudes["lower_lat"]))
        )
    )

    # Calculate the count by multiplying the density by
    # the area of each grid cell.
    return density * area


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
    fraction_of_grid_cells_in_shape = _get_fraction_of_grid_cells_in_shape(
        xarray_data, entity_shape, make_plot=False
    )

    # Rearrange the xarray data.
    xarray_data_rearranged = (
        xarray_data.where(fraction_of_grid_cells_in_shape > 0.0)  # noqa: PD013
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
    assert target_resolution > 2 * original_resolution, (
        "Target resolution must be at least twice the original resolution."
    )

    # Check if the target resolution provides an integer number of bins.
    assert 360 % target_resolution == 0, (
        "Target resolution must result in an integer number when dividing 360."
    )

    # Define the new coarser resolution.
    x_list = numpy.linspace(-180, 180, int(360 / target_resolution) + 1)
    y_list = numpy.linspace(-90, 90, int(180 / target_resolution) + 1)

    # Define the left and right bounds of the x bins and y bins.
    x_bins = numpy.concatenate(
        [
            numpy.array([-180]),
            (x_list[:-1] + x_list[1:]) / 2,
            numpy.array([180]),
        ]
    )
    y_bins = numpy.concatenate(
        [numpy.array([-90]), (y_list[:-1] + y_list[1:]) / 2, numpy.array([90])]
    )

    # Keep only the bins that are within the specified bounds.
    x_bins = x_bins[
        (x_bins >= bounds[0] - target_resolution / 2)
        & (x_bins <= bounds[2] + target_resolution / 2)
    ]
    y_bins = y_bins[
        (y_bins >= bounds[1] - target_resolution / 2)
        & (y_bins <= bounds[3] + target_resolution / 2)
    ]

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

    # Rename the bins to "x" and "y".
    coarsened_xarray = coarsened_xarray.rename({"x_bins": "x", "y_bins": "y"})

    # If the bounds cover the full longitude range, the first and last
    # x coordinates are the centers of the edge bins (half the size of
    # the other bins). In this case, change the first and last x
    # coordinates to -180 and 180, respectively, and sum the values at
    # the edges.
    if (
        coarsened_xarray.x[0] == -180 + target_resolution / 4
        and coarsened_xarray.x[-1] == 180 - target_resolution / 4
    ):
        # Change the first and last x coordinates to -180 and 180.
        coarsened_xarray = coarsened_xarray.assign_coords(
            x=coarsened_xarray.x.where(
                coarsened_xarray.x != coarsened_xarray.x[0], -180
            )
        )
        coarsened_xarray = coarsened_xarray.assign_coords(
            x=coarsened_xarray.x.where(
                coarsened_xarray.x != coarsened_xarray.x[-1], 180
            )
        )

        # Sum the values at the edges if the x coordinate goes from
        # -180 to 180.
        coarsened_xarray.loc[dict(x=-180)] += coarsened_xarray.loc[dict(x=180)]
        coarsened_xarray.loc[dict(x=180)] = coarsened_xarray.loc[dict(x=-180)]

    return coarsened_xarray


def _aggregate_gridded_data(
    variable: str, code: str, year: int, scenario: str | None
) -> float:
    """
    Aggregate gridded data for a country or subdivision.

    Parameters
    ----------
    variable : str
        The variable to aggregate. Available options are "population"
        and "gdp_ppp".
    code : str
        The code of the country or subdivision of interest.
    year : int
        The year of the data to be retrieved.
    scenario : str
        The scenario of the data to be retrieved.

    Returns
    -------
    float
        The total value of the variable for the country or subdivision.
    """
    # Define the path to the gridded data.
    gridded_data_path = os.path.join(
        utils.directories.read_folders_structure()[
            f"gridded_{variable}_folder"
        ],
        f"{code}_0.25_deg_{year}"
        + (f"_{scenario}" if scenario else "")
        + ".nc",
    )

    if not os.path.exists(gridded_data_path):
        # Import the retrieval module for the gridded data.
        retrieval_module = importlib.import_module(
            f"retrievals.gridded_{variable}"
        )

        # Run the data retrieval for the gridded data.
        retrieval_module.run_data_retrieval(
            code=code,
            file=None,
            year=year,
            start_year=None,
            end_year=None,
            scenario=scenario,
        )

    # Read the gridded data.
    gridded_data = xarray.open_dataarray(gridded_data_path)

    # Get the shape of the country or subdivision.
    shape = utils.shapes.get_entity_shape(
        code, make_plot=False, remove_remote_islands=False
    )

    # Calculate the fraction of the grid cells that belong to the
    # country or subdivision.
    fraction_of_grid_cells_in_shape = _get_fraction_of_grid_cells_in_shape(
        gridded_data, shape, make_plot=False
    )

    # Multiply the gridded data by the fractions and sum over all grid
    # cells to get the total value for the country or subdivision.
    return (gridded_data * fraction_of_grid_cells_in_shape).sum().item()


def _select_years_of_gridded_data(
    available_years_of_gridded_data: list[int],
    selected_years: list[int],
) -> list[int]:
    """
    Select the years of gridded data.

    The function selects the years of gridded data that cover the
    years of interest. It finds the first year of available gridded
    data that is less than or equal to the minimum selected year and
    the last year of available gridded data that is greater than or
    equal to the maximum selected year.

    Parameters
    ----------
    available_years_of_gridded_data : list[int]
        The available years of gridded data.
    selected_years : list[int]
        The years of interest.

    Returns
    -------
    list[int]
        The selected years of gridded data.
    """
    # Get the first year of available gridded data that is less than
    # or equal to the minimum selected year.
    first_selected_year_of_gridded_data = max(
        [
            year
            for year in available_years_of_gridded_data
            if year <= min(selected_years)
        ]
    )

    # Get the last year of available gridded data that is greater than
    # or equal to the maximum selected year.
    last_selected_year_of_gridded_data = min(
        [
            year
            for year in available_years_of_gridded_data
            if year >= max(selected_years)
        ]
    )

    # Select and return the years of gridded data that cover the years
    # of interest.
    return [
        year
        for year in available_years_of_gridded_data
        if first_selected_year_of_gridded_data
        <= year
        <= last_selected_year_of_gridded_data
    ]


def get_total_value_from_gridded_data(
    variable: str,
    code: str,
    selected_years: list[int],
    available_years_of_gridded_data: list[int],
    last_available_historical_years_of_gridded_data: int | None = None,
    scenario: str | None = None,
) -> pandas.Series:
    """
    Get the total value of a variable from gridded data.

    This function retrieves the total value of a specified variable
    (e.g., population or GDP PPP) for a given country or subdivision
    over a range of selected years. It utilizes gridded data files,
    which are aggregated based on the provided shape of the country or
    subdivision. The function can handle both historical data and
    future projections based on scenarios.

    Parameters
    ----------
    variable : str
        The variable to retrieve. It can be either "population" or
        "gdp_ppp".
    code : str
        The code of the subdivision of interest.
    selected_years : list[int]
        The years of interest.
    available_years_of_gridded_data : list[int]
        The available years of gridded data.
    last_available_historical_years_of_gridded_data :
        int | None, optional
        The last available year of historical gridded data without
        scenario.
    scenario : str | None, optional
        The scenario of interest for future projections.

    Returns
    -------
    pandas.Series
        The total value of the variable for the selected years.

    Raises
    ------
    ValueError
        If the variable is not "population" or "gdp_ppp".
        If only one of scenario or
        last_available_historical_years_of_gridded_data is provided.
        If last_available_historical_years_of_gridded_data is greater
        than the minimum available year of gridded data.
    """
    if variable not in ["population", "gdp_ppp"]:
        raise ValueError(
            "The variable must be either 'population' or 'gdp_ppp'."
        )

    if scenario is None and last_available_historical_years_of_gridded_data:
        raise ValueError(
            "If last_available_historical_years_of_gridded_data is "
            "provided, scenario must also be provided."
        )

    if scenario and not last_available_historical_years_of_gridded_data:
        raise ValueError(
            "If scenario is provided, "
            "last_available_historical_years_of_gridded_data must also be "
            "provided."
        )

    if last_available_historical_years_of_gridded_data and (
        last_available_historical_years_of_gridded_data
        > min(available_years_of_gridded_data)
    ):
        raise ValueError(
            "last_available_historical_years_of_gridded_data must be less "
            "than the minimum available (future) year of gridded data."
        )

    # If an extra available year of gridded data is provided, add it
    # to the list of available years of gridded data.
    if last_available_historical_years_of_gridded_data:
        available_years_of_gridded_data = [
            last_available_historical_years_of_gridded_data
        ] + available_years_of_gridded_data

    # Sort the available years of gridded data.
    available_years_of_gridded_data.sort()

    # Get years of available gridded data that cover the selected years.
    selected_years_of_gridded_data = _select_years_of_gridded_data(
        available_years_of_gridded_data,
        selected_years,
    )

    # Initialize the list to store the total values.
    total_value_list = []

    for year in selected_years_of_gridded_data:
        if (
            last_available_historical_years_of_gridded_data
            and year == last_available_historical_years_of_gridded_data
        ):
            # Extract the total value for the last year of
            # historical gridded data without scenario.
            total_value_list.append(
                _aggregate_gridded_data(variable, code, year, scenario=None)
            )
        else:
            # Extract the total value for the year and
            # scenario of interest.
            total_value_list.append(
                _aggregate_gridded_data(
                    variable, code, year, scenario=scenario
                )
            )

    # Construct a Series with the total values and the selected
    # years of gridded data as index.
    total_values = pandas.Series(
        data=total_value_list,
        index=selected_years_of_gridded_data,
    )

    # Set the name of the Series and its index.
    total_values.index.name = "Year"
    if variable == "population":
        total_values.name = "Population"
    elif variable == "gdp_ppp":
        total_values.name = "GDP PPP"

    # Interpolate to the selected years and return it.
    return total_values.reindex(
        list(
            range(
                total_values.index.min(),
                total_values.index.max() + 1,
            )
        )
    ).interpolate()

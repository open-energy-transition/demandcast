# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains functions to generate a simple plot of data
    from a GeoDataFrame or xarray DataArray and save the figure
    to a specified directory.
"""

import os

import geopandas
import matplotlib.pyplot
import xarray

import utils.directories


def simple_plot(
    data_to_plot: geopandas.GeoDataFrame | xarray.DataArray, figure_name: str
) -> None:
    """
    Generate a simple plot of the provided data.

    This function takes a GeoDataFrame or xarray DataArray, plots it
    using matplotlib, and saves the figure to a specified directory.

    Parameters
    ----------
    data_to_plot : geopandas.GeoDataFrame | xarray.DataArray
        The data to plot.
    figure_name : str
        The name of the figure.
    """
    # Create a directory to store the figures.
    figure_directory = utils.directories.read_folders_structure()[
        "figures_folder"
    ]
    os.makedirs(figure_directory, exist_ok=True)

    # Plot the data.
    fig, ax = matplotlib.pyplot.subplots()
    data_to_plot.plot(ax=ax)
    fig.savefig(
        os.path.join(figure_directory, figure_name + ".png"),
        dpi=300,
        bbox_inches="tight",
    )
    matplotlib.pyplot.close(fig)

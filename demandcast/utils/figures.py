"""
License: AGPL-3.0.

Description:

    This module contains functions to generate a simple plot of data
    from a GeoDataFrame or xarray DataArray and save the figure in the
    figures folder of the results.
"""

import os

import geopandas
import matplotlib.pyplot as plt
import xarray

import utils.paths


def simple_plot(
    data_to_plot: geopandas.GeoDataFrame | xarray.DataArray, figure_name: str
) -> None:
    """
    Generate a simple plot of the provided data.

    The figure is saved as a PNG file named after the figure.

    Parameters
    ----------
    data_to_plot : geopandas.GeoDataFrame | xarray.DataArray
        The data to plot.
    figure_name : str
        The name of the figure.
    """
    figure_directory = utils.paths.get_results_folder("figures")
    os.makedirs(figure_directory, exist_ok=True)

    fig, ax = plt.subplots()
    # xarray types the plot accessor in a way that mypy misreads.
    data_to_plot.plot(ax=ax)  # type: ignore[call-arg]
    fig.savefig(
        os.path.join(figure_directory, figure_name + ".png"),
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(fig)

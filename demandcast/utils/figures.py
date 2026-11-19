"""
License: AGPL-3.0.

Description:

    This module saves the figures, and draws a simple plot of a
    GeoDataFrame or an xarray DataArray, such as the shape of a country
    or subdivision, in the figures folder of the results.
"""

import os
from typing import Any

import geopandas
import matplotlib.pyplot as plt
import xarray

import utils.files
import utils.paths


def save_figure(fig: plt.Figure, file_path: str, **kwargs: Any) -> None:
    """
    Save a figure at 300 dpi, cropped to its content.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The figure.
    file_path : str
        The path of the file, whose extension gives its format.
    **kwargs : Any
        Other arguments of matplotlib.figure.Figure.savefig.

    Notes
    -----
    The figure is written through utils.files.writing, whose temporary
    name has no extension of an image, so the format is given.
    """
    with utils.files.writing(file_path) as temporary_path:
        fig.savefig(
            temporary_path,
            format=os.path.splitext(file_path)[1][1:],
            dpi=300,
            bbox_inches="tight",
            **kwargs,
        )


def simple_plot(
    data_to_plot: geopandas.GeoDataFrame | xarray.DataArray, figure_name: str
) -> None:
    """
    Plot data and save the figure.

    The figure is saved as a PNG file at 300 dpi, named after the
    figure, in the figures folder of the results.

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
    save_figure(fig, os.path.join(figure_directory, figure_name + ".png"))
    plt.close(fig)

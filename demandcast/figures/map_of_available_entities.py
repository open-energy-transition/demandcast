"""
License: AGPL-3.0.

Description:

    Draw a map of the countries and subdivisions with electricity
    demand data, colored by their years of data. The countries and the
    standard subdivisions have the shapes of the Natural Earth database,
    and the non-standard subdivisions the shapes of their definitions
    in the YAML files of shapes/subdivisions/, made of standard
    subdivisions of Natural Earth (see utils.shapes).
"""

import datetime as dt
import os
from collections.abc import Mapping

import cartopy.crs
import cartopy.feature
import matplotlib.cm
import matplotlib.colors
import matplotlib.pyplot as plt

import utils.data_sources
import utils.shapes

# The classes of the years of available data, with their upper bounds.
YEAR_CLASSES = {"0-4": 5, "5-9": 10, "10-19": 20, "20+": float("inf")}


def get_classes_of_years(
    periods: Mapping[str, list[tuple[dt.date, dt.date]]],
) -> dict[str, int]:
    """
    Get the class of the years of available data of each code.

    Parameters
    ----------
    periods : Mapping[str, list[tuple[datetime.date, datetime.date]]]
        The first and last days of each period of the data of each
        country or subdivision.

    Returns
    -------
    dict[str, int]
        The class of each code, the position of the first class of
        YEAR_CLASSES whose upper bound is above its years of data, of
        365 days.
    """
    return {
        code: next(
            number
            for number, upper_bound in enumerate(YEAR_CLASSES.values())
            if sum((end - start).days + 1 for start, end in code_periods) / 365
            < upper_bound
        )
        for code, code_periods in periods.items()
    }


def plot(figure_directory: str) -> None:
    """
    Plot a map of the countries and subdivisions.

    The countries and subdivisions are those with a retrieval script of
    electricity demand data.

    Parameters
    ----------
    figure_directory : str
        The directory to store the figure.

    Notes
    -----
    The map is saved with the title of the Awesome Electricity Demand
    list (available_entities_for_aed.png), with that of DemandCast
    (available_entities.png), and with that title on a transparent
    background, with black text (available_entities_light_mode.png) and
    with white text (available_entities_dark_mode.png).
    """
    periods = utils.data_sources.read_all_periods()
    codes = utils.data_sources.read_all_codes()
    classes_of_years = get_classes_of_years(
        {code: periods[code] for code in codes}
    )

    map_projection = cartopy.crs.Robinson(central_longitude=0)
    data_crs = cartopy.crs.PlateCarree()

    map_cmap = plt.get_cmap("Blues")

    # The part of the colormap that the classes use.
    lower_bound = 0.2
    upper_bound = 0.9

    alpha = 0.8

    fig, ax = plt.subplots(
        figsize=(12, 16), subplot_kw={"projection": map_projection}
    )

    # cartopy has no type information, so mypy does not know that ax is
    # a cartopy GeoAxes.
    ax.add_feature(  # type: ignore[attr-defined]
        cartopy.feature.LAND, facecolor="lightgray"
    )
    ax.add_feature(  # type: ignore[attr-defined]
        cartopy.feature.OCEAN, facecolor="white"
    )

    base_colors = [
        map_cmap(lower_bound + number * (upper_bound - lower_bound) / 3)
        for number in range(len(YEAR_CLASSES))
    ]

    for code, class_of_years in classes_of_years.items():
        entity_shape = utils.shapes.get_entity_shape(code, make_plot=False)
        color = base_colors[class_of_years]

        entity_shape.plot(
            ax=ax,
            transform=data_crs,
            facecolor=color,
            edgecolor="black",
            linewidth=0.5,
            aspect=None,
            autolim=False,
            alpha=alpha,
        )

    # Give the colors of the colorbar the transparency of the shapes.
    base_colors = [(*color[:3], alpha) for color in base_colors]

    bar_cmap = matplotlib.colors.ListedColormap(base_colors, name="bar_cmap")
    bounds = [0, 1, 2, 3, 4]
    norm = matplotlib.colors.BoundaryNorm(bounds, bar_cmap.N)
    cbar = fig.colorbar(
        matplotlib.cm.ScalarMappable(norm=norm, cmap=bar_cmap),
        ax=ax,
        orientation="horizontal",
        pad=0.025,
        shrink=0.5,
        ticks=[0.5, 1.5, 2.5, 3.5],
    )
    cbar.ax.set_xticklabels(list(YEAR_CLASSES))
    cbar.ax.tick_params(labelsize=12)

    cbar.set_label(
        "Years of available data",
        fontsize=14,
        weight="bold",
        labelpad=10,
    )

    url = ax.text(
        0.5,
        1.21,
        "https://github.com/open-energy-transition/Awesome-Electricity-Demand",
        fontsize=12,
        ha="center",
        weight="bold",
        transform=ax.transAxes,
        color="tab:blue",
    )
    aed_title = plt.text(
        0.5,
        1.05,
        "Countries and subdivisions with publicly available\n"
        "high-resolution electricity demand data",
        fontsize=18,
        ha="center",
        weight="bold",
        transform=ax.transAxes,
    )

    fig.savefig(
        os.path.join(figure_directory, "available_entities_for_aed.png"),
        dpi=300,
        bbox_inches="tight",
    )

    url.set_visible(False)
    aed_title.set_visible(False)

    ax.set_title(
        (
            "Countries and subdivisions for which retrieval modules\n"
            "of electricity demand data are available"
        ),
        fontsize=18,
        y=1.04,
        weight="bold",
    )

    fig.savefig(
        os.path.join(figure_directory, "available_entities.png"),
        dpi=300,
        bbox_inches="tight",
    )

    fig.savefig(
        os.path.join(figure_directory, "available_entities_light_mode.png"),
        dpi=300,
        bbox_inches="tight",
        transparent=True,
    )

    ax.title.set_color("white")
    for tick in cbar.ax.get_xticklabels():
        tick.set_color("white")
    cbar.ax.xaxis.label.set_color("white")

    fig.savefig(
        os.path.join(figure_directory, "available_entities_dark_mode.png"),
        dpi=300,
        bbox_inches="tight",
        transparent=True,
    )

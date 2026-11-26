"""
License: AGPL-3.0.

Description:

    This module draws a map of the countries and subdivisions with
    electricity demand data, with each place colored by the years of
    all the data that covers it, so that no data hides another: the
    data of a country covers the whole country, and that of a
    subdivision the places inside its shape. The subdivisions of a
    country are split into the pieces that the same subdivisions cover,
    such as the periods of a grid whose area grew, and each piece counts
    the days of the periods of its country and of its subdivisions,
    without counting a day twice. The countries and the standard
    subdivisions have the shapes of the Natural Earth database. The
    non-standard subdivisions are made of standard subdivisions, as
    defined in the YAML files of shapes/subdivisions/ (see
    utils.shapes).
"""

import datetime as dt
import os
from collections.abc import Mapping

import cartopy.crs
import cartopy.feature
import geopandas
import matplotlib.cm
import matplotlib.colors
import matplotlib.pyplot as plt
import shapely

import utils.data_sources
import utils.figures
import utils.shapes

# The classes of the years of available data, with their upper bounds.
YEAR_CLASSES = {"0-4": 5, "5-9": 10, "10-19": 20, "20+": float("inf")}

# The precision of the coordinates of the pieces, in degrees, and the
# smallest area of a piece, in square degrees, below which it is a
# sliver of the borders of the shapes.
GRID_SIZE = 1e-6
MIN_PIECE_AREA = 1e-6


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


def _keep_polygons(geometry: shapely.Geometry) -> shapely.Geometry:
    """
    Keep the polygons of a geometry, without its lines and points.

    Parameters
    ----------
    geometry : shapely.Geometry
        The geometry, such as the result of an overlay of shapes that
        touch along a border.

    Returns
    -------
    shapely.Geometry
        The polygons of the geometry, as one multipolygon.
    """
    return shapely.MultiPolygon(
        [
            polygon
            for part in shapely.get_parts(geometry)
            for polygon in shapely.get_parts(part)
            if isinstance(polygon, shapely.Polygon)
        ]
    )


def get_pieces(
    shapes: Mapping[str, shapely.Geometry],
) -> list[tuple[shapely.Geometry, tuple[str, ...]]]:
    """
    Split shapes into the pieces that the same shapes cover.

    Parameters
    ----------
    shapes : Mapping[str, shapely.Geometry]
        The shape of each code, in degrees of longitude and latitude.

    Returns
    -------
    list[tuple[shapely.Geometry, tuple[str, ...]]]
        Each piece, with the codes of the shapes that cover it, in
        order.
    """
    pieces: list[tuple[shapely.Geometry, frozenset[str]]] = []
    for code, shape in shapes.items():
        split = []
        rest = _keep_polygons(shape)
        for piece, covers in pieces:
            for part, part_covers in (
                (
                    _keep_polygons(
                        shapely.intersection(piece, rest, grid_size=GRID_SIZE)
                    ),
                    covers | {code},
                ),
                (
                    _keep_polygons(
                        shapely.difference(piece, shape, grid_size=GRID_SIZE)
                    ),
                    covers,
                ),
            ):
                if shapely.area(part) > MIN_PIECE_AREA:
                    split.append((part, part_covers))
            rest = _keep_polygons(
                shapely.difference(rest, piece, grid_size=GRID_SIZE)
            )
        if shapely.area(rest) > MIN_PIECE_AREA:
            split.append((rest, frozenset({code})))
        pieces = split
    return [(piece, tuple(sorted(covers))) for piece, covers in pieces]


def get_places(
    periods: Mapping[str, list[tuple[dt.date, dt.date]]],
) -> list[tuple[shapely.Geometry, list[tuple[dt.date, dt.date]]]]:
    """
    Get the places of the map, each with the periods that cover it.

    Parameters
    ----------
    periods : Mapping[str, list[tuple[datetime.date, datetime.date]]]
        The first and last days of each period of the data of each
        country or subdivision.

    Returns
    -------
    list[tuple[shapely.Geometry, list[tuple]]]
        The shape of each place with data, with the union of the periods
        of the data that covers it: the countries with data of their
        own first, then the pieces of the subdivisions of each country
        (see get_pieces), which the map draws over them.
    """
    by_country: dict[str, list[str]] = {}
    for code in sorted(periods):
        by_country.setdefault(code.split("_")[0], []).append(code)
    countries = []
    subdivisions = []
    for country, codes in by_country.items():
        national = list(periods.get(country, []))
        if national:
            countries.append(
                (
                    utils.shapes.get_entity_shape(
                        country, make_plot=False
                    ).union_all(),
                    national,
                )
            )
        shapes = {
            code: utils.shapes.get_entity_shape(
                code, make_plot=False
            ).union_all()
            for code in codes
            if "_" in code
        }
        for piece, covers in get_pieces(shapes):
            subdivisions.append(
                (
                    piece,
                    utils.data_sources.merge_periods(
                        national
                        + [
                            period
                            for code in covers
                            for period in periods[code]
                        ]
                    ),
                )
            )
    return countries + subdivisions


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
    The map is saved four times: with the title of the Awesome
    Electricity Demand list (available_entities_for_aed.png), with the
    title of DemandCast (available_entities.png), and with the title of
    DemandCast on a transparent background, in black text
    (available_entities_light_mode.png) and in white text
    (available_entities_dark_mode.png).
    """
    periods = utils.data_sources.read_all_periods()
    places = get_places(
        {code: periods[code] for code in utils.data_sources.read_all_codes()}
    )
    classes_of_years = get_classes_of_years(
        {str(number): place[1] for number, place in enumerate(places)}
    )

    map_projection = cartopy.crs.Robinson(central_longitude=0)
    data_crs = cartopy.crs.PlateCarree()

    map_cmap = plt.get_cmap("Blues")

    # The part of the colormap that the classes use.
    lower_bound = 0.2
    upper_bound = 0.9

    # The pieces of the subdivisions are drawn over their countries,
    # whose colors they include, so the places are drawn opaque.
    alpha = 1.0

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

    for number, (place, _) in enumerate(places):
        color = base_colors[classes_of_years[str(number)]]

        geopandas.GeoSeries([place], crs="EPSG:4326").plot(
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

    utils.figures.save_figure(
        fig,
        os.path.join(figure_directory, "available_entities_for_aed.png"),
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

    utils.figures.save_figure(
        fig,
        os.path.join(figure_directory, "available_entities.png"),
    )

    utils.figures.save_figure(
        fig,
        os.path.join(figure_directory, "available_entities_light_mode.png"),
        transparent=True,
    )

    ax.title.set_color("white")
    for tick in cbar.ax.get_xticklabels():
        tick.set_color("white")
    cbar.ax.xaxis.label.set_color("white")

    utils.figures.save_figure(
        fig,
        os.path.join(figure_directory, "available_entities_dark_mode.png"),
        transparent=True,
    )
    plt.close(fig)

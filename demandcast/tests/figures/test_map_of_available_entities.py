"""
License: AGPL-3.0.

Description:

    Tests for the places and the classes of the years of data of the
    map of the countries and subdivisions with electricity demand data,
    with shapes made for the tests.
"""

import datetime as dt

import cartopy.crs
import cartopy.feature
import geopandas
import shapely

from figures import map_of_available_entities


def test_get_classes_of_years():
    """
    Test that each code is in the class of its years of data.

    The years of a code are those of all its periods: "I" has two
    periods of 3 years, so 6 years.
    """
    start = dt.date(2000, 1, 1)
    periods = {
        code: [(start, start + dt.timedelta(days=round(365 * years) - 1))]
        for code, years in {
            "A": 0.1,
            "B": 4.9,
            "C": 5,
            "D": 9.9,
            "E": 10,
            "F": 19.9,
            "G": 20,
            "H": 40,
        }.items()
    }
    periods["I"] = [
        (dt.date(2000, 1, 1), dt.date(2002, 12, 31)),
        (dt.date(2010, 1, 1), dt.date(2012, 12, 31)),
    ]

    assert map_of_available_entities.get_classes_of_years(periods) == {
        "A": 0,
        "B": 0,
        "C": 1,
        "D": 1,
        "E": 2,
        "F": 2,
        "G": 3,
        "H": 3,
        "I": 1,
    }


def test_get_pieces():
    """
    Test that overlapping shapes are split into the pieces they cover.

    A and B overlap on the square from 1 to 2, and C lies inside B.
    """
    pieces = map_of_available_entities.get_pieces(
        {
            "A": shapely.box(0, 0, 2, 1),
            "B": shapely.box(1, 0, 4, 1),
            "C": shapely.box(3, 0, 4, 1),
        }
    )

    assert sorted(
        (covers, round(float(shapely.area(piece)), 6))
        for piece, covers in pieces
    ) == [
        (("A",), 1.0),
        (("A", "B"), 1.0),
        (("B",), 1.0),
        (("B", "C"), 1.0),
    ]


def test_get_places(monkeypatch):
    """
    Test that each place has the periods of all the data that covers it.

    The country X has data of its own, and its subdivision X_A covers
    half of it, in another period. Y has only data of its subdivision.
    """
    shapes = {
        "X": shapely.box(0, 0, 2, 1),
        "X_A": shapely.box(0, 0, 1, 1),
        "Y_B": shapely.box(5, 0, 6, 1),
    }
    monkeypatch.setattr(
        map_of_available_entities.utils.shapes,
        "get_entity_shape",
        lambda code, **_: geopandas.GeoDataFrame(
            geometry=[shapes[code]], crs="EPSG:4326"
        ),
    )
    periods = {
        "X": [(dt.date(2000, 1, 1), dt.date(2004, 12, 31))],
        "X_A": [(dt.date(2003, 1, 1), dt.date(2009, 12, 31))],
        "Y_B": [(dt.date(2020, 1, 1), dt.date(2020, 12, 31))],
    }

    places = map_of_available_entities.get_places(periods)

    assert [
        (tuple(shapely.bounds(place)), place_periods)
        for place, place_periods in places
    ] == [
        ((0.0, 0.0, 2.0, 1.0), periods["X"]),
        ((0.0, 0.0, 1.0, 1.0), [(dt.date(2000, 1, 1), dt.date(2009, 12, 31))]),
        ((5.0, 0.0, 6.0, 1.0), periods["Y_B"]),
    ]


def test_plot(monkeypatch, tmp_path):
    """
    Test that the map draws each place and is saved four times.

    The land and the ocean of Natural Earth are replaced with empty
    features, and the figures are not drawn into files, so that no map
    data is downloaded.
    """
    for feature in ("LAND", "OCEAN"):
        monkeypatch.setattr(
            map_of_available_entities.cartopy.feature,
            feature,
            cartopy.feature.ShapelyFeature([], cartopy.crs.PlateCarree()),
        )
    shapes = {"X": shapely.box(0, 0, 2, 1), "X_A": shapely.box(0, 0, 1, 1)}
    monkeypatch.setattr(
        map_of_available_entities.utils.data_sources,
        "read_all_periods",
        lambda: {
            "X": [(dt.date(2000, 1, 1), dt.date(2004, 12, 31))],
            "X_A": [(dt.date(2003, 1, 1), dt.date(2009, 12, 31))],
        },
    )
    monkeypatch.setattr(
        map_of_available_entities.utils.data_sources,
        "read_all_codes",
        lambda: ["X", "X_A"],
    )
    monkeypatch.setattr(
        map_of_available_entities.utils.shapes,
        "get_entity_shape",
        lambda code, **_: geopandas.GeoDataFrame(
            geometry=[shapes[code]], crs="EPSG:4326"
        ),
    )
    saved = []
    monkeypatch.setattr(
        map_of_available_entities.utils.figures,
        "save_figure",
        lambda figure, path, **_: saved.append((figure, path)),
    )

    map_of_available_entities.plot(str(tmp_path))

    assert [path for _, path in saved] == [
        str(tmp_path / name)
        for name in (
            "available_entities_for_aed.png",
            "available_entities.png",
            "available_entities_light_mode.png",
            "available_entities_dark_mode.png",
        )
    ]
    # The land, the ocean, the country, then the piece of its
    # subdivision.
    assert len(saved[0][0].axes[0].collections) == 4

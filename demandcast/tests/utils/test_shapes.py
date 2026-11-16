"""
License: AGPL-3.0.

Description:

    This module contains tests for the shapes module.
"""

from unittest.mock import patch

import geopandas
import pytest
import yaml
from shapely import Polygon

import utils.codes
import utils.shapes

SQUARE = "POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0))"


@pytest.fixture
def dummy_geodf():
    """
    Make a dummy GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        A GeoDataFrame with a simple square polygon.
    """
    polygon = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    geodataframe = geopandas.GeoDataFrame(
        {"geometry": [polygon]}, crs="EPSG:4326"
    )
    return geodataframe


def test_remove_islands_and_clip_to_180(dummy_geodf):
    """Test _remove_islands_and_clip_to_180 with various codes."""
    countries = [
        "CHL",
        "ESP",
        "FJI",
        "FRA",
        "NLD",
        "NOR",
        "NZL",
        "PRT",
        "RUS",
        "RUS_CHU",
        "USA",
    ]
    for code in countries:
        result = utils.shapes._remove_islands_and_clip_to_180(
            dummy_geodf.copy(), code
        )
        assert isinstance(result, geopandas.GeoDataFrame)

    dummy_bounds = geopandas.GeoSeries(
        Polygon([(0, 0), (0.5, 0), (0.5, 0.5), (0, 0.5)])
    )
    dummy_bounds_frame = geopandas.GeoDataFrame.from_features(
        dummy_bounds, crs=4326
    )

    with patch("geopandas.GeoDataFrame.from_features") as mock_from_features:
        mock_from_features.return_value = dummy_bounds_frame

        # Test the function with a country code that has islands.
        result = utils.shapes._remove_islands_and_clip_to_180(
            dummy_geodf.copy(), "CHL"
        )

        assert result.bounds.minx[0] >= dummy_bounds_frame.bounds.minx[0]
        assert result.bounds.miny[0] >= dummy_bounds_frame.bounds.miny[0]
        assert result.bounds.maxx[0] <= dummy_bounds_frame.bounds.maxx[0]
        assert result.bounds.maxy[0] <= dummy_bounds_frame.bounds.maxy[0]


def test_get_standard_shape_by_code():
    """
    Test the get_standard_shape function with valid country codes.

    The cartopy Reader is mocked to give square shapes.
    """

    class DummyShape:
        """A record of the cartopy Reader."""

        def __init__(self, attr):
            """Set the attributes and the square shape of the record."""
            self.attributes = attr
            self.geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    with (
        patch("cartopy.io.shapereader.natural_earth"),
        patch("cartopy.io.shapereader.Reader") as mock_reader,
    ):
        mock_reader.return_value.records.return_value = [
            DummyShape({"ISO_A3": "FRA", "ISO_A3_EH": "FRA"}),
            DummyShape({"ISO_A3": "ITA", "ISO_A3_EH": "ITA"}),
        ]

        # Test the get_standard_shape function for France.
        shape = utils.shapes.get_standard_shape(
            "FRA", remove_remote_islands=True
        )
        assert isinstance(shape, geopandas.GeoDataFrame)

        mock_reader.return_value.records.return_value = [
            DummyShape({"iso_3166_2": "AU-VIC"}),
            DummyShape({"iso_3166_2": "CA-ON"}),
        ]

        # Test the get_standard_shape function for Victoria, Australia.
        shape = utils.shapes.get_standard_shape(
            "AUS_VIC", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)


def test_get_standard_shape_invalid_code():
    """
    Test the get_standard_shape function with invalid country codes.

    The shapes of the mocked cartopy Reader have invalid codes, and
    are found by their names.
    """

    class DummyShape:
        """A record of the cartopy Reader."""

        def __init__(self, attr):
            """Set the attributes and the square shape of the record."""
            self.attributes = attr
            self.geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    with (
        patch("cartopy.io.shapereader.natural_earth"),
        patch("cartopy.io.shapereader.Reader") as mock_reader,
    ):
        mock_reader.return_value.records.return_value = [
            DummyShape(
                {
                    "ISO_A3": "INVALID",
                    "ISO_A3_EH": "INVALID",
                    "NAME": "France",
                    "NAME_LONG": "France",
                }
            ),
            DummyShape(
                {
                    "ISO_A3": "INVALID",
                    "ISO_A3_EH": "INVALID",
                    "NAME": "Italy",
                    "NAME_LONG": "Italy",
                }
            ),
        ]

        # Test the get_standard_shape function for France.
        shape = utils.shapes.get_standard_shape(
            "FRA", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)

        mock_reader.return_value.records.return_value = [
            DummyShape({"iso_3166_2": "INVALID", "name": "Victoria"}),
            DummyShape({"iso_3166_2": "INVALID", "name": "Ontario"}),
        ]

        # Test the get_standard_shape function for Victoria, Australia.
        shape = utils.shapes.get_standard_shape(
            "AUS_VIC", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)


def test_read_non_standard_shape_codes():
    """
    Test the _read_non_standard_shape_codes function.

    The codes are in a dictionary by data source.
    """
    codes = utils.shapes._read_non_standard_shape_codes()

    assert isinstance(codes, dict)
    assert "occto" in codes
    assert "tepco" in codes
    assert "neso" in codes
    assert codes["soni"] == ["GBR_NIR"]
    assert "GBR_GB" in codes["neso"]


def test_get_non_standard_shape():
    """Test the _get_non_standard_shape function."""
    shape = utils.shapes._get_non_standard_shape("GBR_GB", "neso")
    assert isinstance(shape, geopandas.GeoDataFrame)


def test_get_entity_shape(dummy_geodf):
    """
    Test the get_entity_shape function.

    The shape is standard or non-standard, and a subdivision that no
    data source lists has a standard shape.
    """
    dummy_geodf["code"] = "FRA"
    dummy_geodf = dummy_geodf.set_index("code")

    with (
        patch("utils.shapes.get_standard_shape") as mock_standard,
        patch(
            "utils.shapes._read_non_standard_shape_codes"
        ) as mock_read_codes,
        patch("utils.shapes._get_non_standard_shape") as mock_nonstandard,
        patch("utils.figures.simple_plot") as mock_plot,
    ):
        mock_standard.return_value = dummy_geodf
        mock_plot.return_value = None

        # Test the get_entity_shape function for a country with a
        # standard shape.
        result = utils.shapes.get_entity_shape("FRA")
        assert isinstance(result, geopandas.GeoDataFrame)

        # Mock the return value for the _read_non_standard_shape_codes
        # function to simulate a non-standard shape for a subdivision.
        mock_read_codes.return_value = {"dat_source": ["XX_1"]}
        mock_nonstandard.return_value = dummy_geodf

        result = utils.shapes.get_entity_shape("XX_1", make_plot=False)
        assert isinstance(result, geopandas.GeoDataFrame)

        # Mock the return value for the _read_non_standard_shape_codes
        # function with an empty list to simulate that the subdivision
        # has then a standard shape.
        mock_read_codes.return_value = {"dat_source": []}
        mock_standard.return_value = dummy_geodf

        result = utils.shapes.get_entity_shape("XX_1", make_plot=False)
        assert isinstance(result, geopandas.GeoDataFrame)


def test_get_entity_bounds(dummy_geodf):
    """
    Test the get_entity_bounds function.

    The bounds have a margin of 1 degree, and longitudes within -180
    and 180 degrees.
    """
    bounds = utils.shapes.get_entity_bounds(dummy_geodf)

    assert isinstance(bounds, list)
    assert len(bounds) == 4

    assert bounds[0] == dummy_geodf.bounds.minx[0] - 1
    assert bounds[1] == dummy_geodf.bounds.miny[0] - 1
    assert bounds[2] == dummy_geodf.bounds.maxx[0] + 1
    assert bounds[3] == dummy_geodf.bounds.maxy[0] + 1

    # Define a GeoDataFrame with bounds exceeding the range [-180, 180]
    # for the longitude.
    dummy_geodf = geopandas.GeoDataFrame(
        {
            "geometry": [
                Polygon([(-200, -100), (200, -100), (200, 100), (-200, 100)])
            ]
        },
        crs="EPSG:4326",
    )

    bounds = utils.shapes.get_entity_bounds(dummy_geodf)

    assert bounds[0] == -180
    assert bounds[2] == 180


@pytest.mark.network
def test_get_all_codes_with_shapes():
    """Test the get_all_codes_with_shapes function."""
    shape_codes = utils.shapes.get_all_codes_with_shapes()

    assert isinstance(shape_codes, list)
    assert len(shape_codes) > 0
    assert "FRA" in shape_codes
    assert "USA_TEX" in shape_codes
    assert "RUS_AD" in shape_codes
    assert "UKR_40" in shape_codes
    assert "XKX" in shape_codes
    assert "BRA_N" in shape_codes


@pytest.fixture
def subdivisions_file(tmp_path):
    """
    Point the folder of the subdivisions to a temporary folder.

    Yields
    ------
    function
        A function that writes its first argument as the content of a
        file of the folder, by default ``XX.yaml``, and clears the
        cache of the subdivisions.
    """
    folder = tmp_path / "subdivisions"
    folder.mkdir()

    def write(content, name="XX.yaml"):
        (folder / name).write_text(yaml.safe_dump(content), encoding="utf-8")
        utils.shapes.read_subdivisions.cache_clear()

    with patch("utils.paths.SUBDIVISIONS_FOLDER", str(folder)):
        yield write
    utils.shapes.read_subdivisions.cache_clear()


def test_read_subdivisions():
    """
    Read the subdivisions of the repository.

    Each code has a country and a subdivision, and each subdivision
    has a standard subdivision of its own country.
    """
    utils.shapes.read_subdivisions.cache_clear()
    subdivisions = utils.shapes.read_subdivisions().subdivisions

    assert "BRA_N" in subdivisions
    assert subdivisions["AUS_QLD1"].cuts == {"AU-QLD": "queensland"}
    assert subdivisions["MEX_BCS"].cuts == {"MX-BCS": "mulege"}
    assert subdivisions["USA_NW"].name == "Northwest"
    assert "US-NV" in subdivisions["USA_NW"].standard_subdivisions
    for code, subdivision in subdivisions.items():
        country, _ = code.split("_", 1)
        alpha_2 = utils.codes.get_iso_alpha_2_code(country)
        assert any(
            r.startswith(f"{alpha_2}-")
            for r in subdivision.standard_subdivisions
        )


@pytest.mark.parametrize(
    ("cuts", "subdivisions", "message"),
    [
        (
            {"a": {"description": "A", "polygon": SQUARE}},
            {
                "XX_1": {
                    "name": "X",
                    "standard_subdivisions": ["XX-A"],
                    "cuts": {"XX-B": "a"},
                }
            },
            "cuts XX-B, not one of its standard subdivisions",
        ),
        (
            {},
            {
                "XX_1": {
                    "name": "X",
                    "standard_subdivisions": ["XX-A"],
                    "cuts": {"XX-A": "a"},
                }
            },
            "unknown cut a",
        ),
        (
            {"a": {"description": "A", "polygon": SQUARE}},
            {"XX_1": {"name": "X", "standard_subdivisions": ["XX-A"]}},
            "unused cuts: a",
        ),
        (
            {"a": {"description": "A", "polygon": "POLYGON ((0 0"}},
            {},
            "invalid WKT",
        ),
        (
            {"a": {"description": "A", "polygon": "POINT (0 0)"}},
            {},
            "Point is not a polygon",
        ),
        (
            {
                "a": {
                    "description": "A",
                    "polygon": "POLYGON ((0 0, 1 1, 1 0, 0 1, 0 0))",
                }
            },
            {},
            "the polygon is not valid",
        ),
    ],
)
def test_read_invalid_subdivisions(
    subdivisions_file, cuts, subdivisions, message
):
    """Reject a cut of another region, unknown or unused, or invalid."""
    subdivisions_file({"cuts": cuts, "subdivisions": subdivisions})

    with pytest.raises(ValueError, match=message):
        utils.shapes.read_subdivisions()


def test_read_subdivisions_of_several_files(subdivisions_file):
    """
    Read the subdivisions of every file, which may have no cuts.

    Notes
    -----
    Files that are not YAML, such as notes, are left out.
    """
    subdivisions_file(
        {
            "subdivisions": {
                "XX_1": {"name": "X", "standard_subdivisions": "XX-A"}
            }
        }
    )
    subdivisions_file(
        {
            "cuts": {"a": {"description": "A", "polygon": SQUARE}},
            "subdivisions": {
                "YY_1": {
                    "name": "Y",
                    "standard_subdivisions": "YY-A YY-B",
                    "cuts": {"YY-A": "a"},
                }
            },
        },
        name="YY.yaml",
    )
    subdivisions_file({}, name="notes.txt")

    definitions = utils.shapes.read_subdivisions()

    assert sorted(definitions.subdivisions) == ["XX_1", "YY_1"]
    assert definitions.subdivisions["YY_1"].standard_subdivisions == [
        "YY-A",
        "YY-B",
    ]
    assert list(definitions.cuts) == ["a"]


def test_read_subdivisions_of_another_country(subdivisions_file):
    """Reject a subdivision in the file of another country."""
    subdivisions_file(
        {
            "subdivisions": {
                "YY_1": {"name": "Y", "standard_subdivisions": "YY-A"}
            }
        }
    )

    with pytest.raises(ValueError, match="another country: YY_1"):
        utils.shapes.read_subdivisions()


def test_read_cuts_of_two_files(subdivisions_file):
    """Reject a cut with the name of a cut of another file."""
    for country in ("XX", "YY"):
        subdivisions_file(
            {
                "cuts": {"a": {"description": "A", "polygon": SQUARE}},
                "subdivisions": {
                    f"{country}_1": {
                        "name": country,
                        "standard_subdivisions": f"{country}-A",
                        "cuts": {f"{country}-A": "a"},
                    }
                },
            },
            name=f"{country}.yaml",
        )

    with pytest.raises(ValueError, match="cuts of another file: a"):
        utils.shapes.read_subdivisions()


def test_read_non_standard_shape_codes_skips_other_folders(tmp_path):
    """Leave out the folders of the shapes without a shapefile."""
    (tmp_path / "subdivisions").mkdir()
    (tmp_path / "__pycache__").mkdir()

    with patch("utils.paths.SHAPES_FOLDER", str(tmp_path)):
        assert utils.shapes._read_non_standard_shape_codes() == {}


def _standard_subdivisions():
    """
    Make two standard subdivisions side by side.

    Returns
    -------
    geopandas.GeoDataFrame
        The squares of XX-A, from 0 to 1, and XX-B, from 1 to 2.
    """
    return geopandas.GeoDataFrame(
        {
            "iso_3166_2": ["XX-A", "XX-B"],
            "geometry": [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
            ],
        },
        crs=4326,
    )


def test_get_subdivision_shape(subdivisions_file):
    """
    Make a subdivision of two standard subdivisions, one of them cut.

    Notes
    -----
    The cut takes the upper half of XX-B, so the two rows of the
    subdivision have an area of 1.5.
    """
    subdivisions_file(
        {
            "cuts": {
                "half": {
                    "description": "Upper half",
                    "polygon": "POLYGON ((1 0.5, 2 0.5, 2 1, 1 1, 1 0.5))",
                }
            },
            "subdivisions": {
                "XX_1": {
                    "name": "X",
                    "standard_subdivisions": ["XX-A", "XX-B"],
                    "cuts": {"XX-B": "half"},
                },
                "XX_2": {
                    "name": "Y",
                    "standard_subdivisions": ["XX-A", "XX-C"],
                },
            },
        }
    )

    with patch(
        "utils.shapes._read_detailed_standard_subdivisions",
        return_value=_standard_subdivisions(),
    ):
        shape = utils.shapes.get_entity_shape("XX_1", make_plot=False)
        assert list(shape.index) == ["XX_1", "XX_1"]
        assert shape.union_all().area == pytest.approx(1.5)

        with pytest.raises(ValueError, match="no subdivision XX-C"):
            utils.shapes.get_entity_shape("XX_2", make_plot=False)


@pytest.mark.network
def test_read_detailed_standard_subdivisions():
    """Read the standard subdivisions of Natural Earth at 1:10m."""
    regions = utils.shapes._read_detailed_standard_subdivisions()

    assert "BO-B" in set(regions["iso_3166_2"])


@pytest.mark.network
def test_subdivisions_have_shapes():
    """Make the shape of every subdivision of the repository."""
    utils.shapes.read_subdivisions.cache_clear()
    for code in utils.shapes.read_subdivisions().subdivisions:
        shape = utils.shapes.get_entity_shape(code, make_plot=False)
        assert not shape.union_all().is_empty

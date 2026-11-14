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
    assert "eia" in codes
    assert "tepco" in codes
    assert "neso" in codes
    assert codes["soni"] == ["GBR_NIR"]
    assert "MEX_PEN" in codes["cenace"]


def test_get_non_standard_shape():
    """Test the _get_non_standard_shape function."""
    shape = utils.shapes._get_non_standard_shape("MEX_PEN", "cenace")
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
def composites_file(tmp_path):
    """
    Point the file of the composites to a temporary file.

    Yields
    ------
    function
        A function that writes its argument as the content of the
        file, and clears the cache of the composites.
    """
    path = tmp_path / "composites.yaml"

    def write(content):
        path.write_text(yaml.safe_dump(content), encoding="utf-8")
        utils.shapes.read_composites.cache_clear()

    with patch("utils.paths.COMPOSITES_FILE", str(path)):
        yield write
    utils.shapes.read_composites.cache_clear()


def test_read_composites():
    """
    Read the composites of the repository.

    Each code has a country and a subdivision, and each composite has a
    standard subdivision of its own country.
    """
    utils.shapes.read_composites.cache_clear()
    composites = utils.shapes.read_composites().composites

    assert "BRA_N" in composites
    assert composites["AUS_QLD1"].cuts == {"AU-QLD": "queensland"}
    for code, composite in composites.items():
        country, _ = code.split("_", 1)
        alpha_2 = utils.codes.get_iso_alpha_2_code(country)
        assert any(r.startswith(f"{alpha_2}-") for r in composite.regions)


@pytest.mark.parametrize(
    ("cuts", "composites", "message"),
    [
        (
            {"a": {"description": "A", "polygon": SQUARE}},
            {
                "XX_1": {
                    "name": "X",
                    "regions": ["XX-A"],
                    "cuts": {"XX-B": "a"},
                }
            },
            "cuts XX-B, not its region",
        ),
        (
            {},
            {
                "XX_1": {
                    "name": "X",
                    "regions": ["XX-A"],
                    "cuts": {"XX-A": "a"},
                }
            },
            "unknown cut a",
        ),
        (
            {"a": {"description": "A", "polygon": SQUARE}},
            {"XX_1": {"name": "X", "regions": ["XX-A"]}},
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
def test_read_invalid_composites(composites_file, cuts, composites, message):
    """Reject a cut of another region, unknown or unused, or invalid."""
    composites_file({"cuts": cuts, "composites": composites})

    with pytest.raises(ValueError, match=message):
        utils.shapes.read_composites()


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


def test_get_composite_shape(composites_file):
    """
    Make a composite of two standard subdivisions, one of them cut.

    Notes
    -----
    The cut takes the upper half of XX-B, so the two rows of the
    composite have an area of 1.5.
    """
    composites_file(
        {
            "cuts": {
                "half": {
                    "description": "Upper half",
                    "polygon": "POLYGON ((1 0.5, 2 0.5, 2 1, 1 1, 1 0.5))",
                }
            },
            "composites": {
                "XX_1": {
                    "name": "X",
                    "regions": ["XX-A", "XX-B"],
                    "cuts": {"XX-B": "half"},
                },
                "XX_2": {"name": "Y", "regions": ["XX-A", "XX-C"]},
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
def test_composites_have_shapes():
    """Make the shape of every composite of the repository."""
    utils.shapes.read_composites.cache_clear()
    for code in utils.shapes.read_composites().composites:
        shape = utils.shapes.get_entity_shape(code, make_plot=False)
        assert not shape.union_all().is_empty

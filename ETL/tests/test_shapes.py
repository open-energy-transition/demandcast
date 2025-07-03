# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains tests for the shapes module.
"""

from unittest.mock import patch

import geopandas
import pytest
import utils.shapes
from shapely import Polygon


@pytest.fixture
def dummy_geodf():
    """
    Create a dummy GeoDataFrame for testing purposes.

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


def test_remove_islands(dummy_geodf):
    """
    Test the _remove_islands function with various country codes.

    Parameters
    ----------
    dummy_geodf : geopandas.GeoDataFrame
        A dummy GeoDataFrame to test the function.
    """
    countries = ["CL", "ES", "FR", "NL", "NO", "NZ", "PT", "XX"]
    for code in countries:
        result = utils.shapes._remove_islands(dummy_geodf.copy(), code)
        assert isinstance(result, geopandas.GeoDataFrame)


def test_get_standard_shape_by_code():
    """
    Test the _get_standard_shape function with valid country codes.

    This function mocks the cartopy Reader to return dummy shapes for
    specified country codes and checks if the returned shape is a
    GeoDataFrame.
    """

    # Define a dummy shape class to simulate the cartopy Reader's
    # behavior for testing purposes.
    class DummyShape:
        def __init__(self, attr):
            self.attributes = attr
            self.geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    with patch("cartopy.io.shapereader.Reader") as mock_reader:
        # Mock the cartopy Reader to return dummy shapes for France and
        # Italy with ISO_A2 codes.
        mock_reader.return_value.records.return_value = [
            DummyShape({"ISO_A2": "FR", "ISO_A2_EH": "FR"}),
            DummyShape({"ISO_A2": "IT", "ISO_A2_EH": "IT"}),
        ]

        # Test the _get_standard_shape function for France.
        shape = utils.shapes._get_standard_shape(
            "FR", remove_remote_islands=True
        )
        assert isinstance(shape, geopandas.GeoDataFrame)

        # Mock the cartopy Reader to return dummy shapes for Australia
        # and Canada with iso_3166_2 codes.
        mock_reader.return_value.records.return_value = [
            DummyShape({"iso_3166_2": "AU-VIC"}),
            DummyShape({"iso_3166_2": "CA-ON"}),
        ]

        # Test the _get_standard_shape function for Victoria, Australia.
        shape = utils.shapes._get_standard_shape(
            "AU_VIC", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)


def test_get_standard_shape_invalid_code():
    """
    Test the _get_standard_shape function with invalid country codes.

    This function mocks the cartopy Reader to return dummy shapes for
    specified country codes that do not match any valid ISO_A2 or
    iso_3166_2 codes, and checks if the returned shape is a
    GeoDataFrame.
    """

    # Define a dummy shape class to simulate the cartopy Reader's
    # behavior for testing purposes.
    class DummyShape:
        def __init__(self, attr):
            self.attributes = attr
            self.geometry = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])

    with patch("cartopy.io.shapereader.Reader") as mock_reader:
        # Mock the cartopy Reader to return dummy shapes for France and
        # Italy with invalid ISO_A2 codes.
        mock_reader.return_value.records.return_value = [
            DummyShape(
                {
                    "ISO_A2": "INVALID",
                    "ISO_A2_EH": "INVALID",
                    "NAME": "France",
                    "NAME_LONG": "France",
                }
            ),
            DummyShape(
                {
                    "ISO_A2": "INVALID",
                    "ISO_A2_EH": "INVALID",
                    "NAME": "Italy",
                    "NAME_LONG": "Italy",
                }
            ),
        ]

        # Test the _get_standard_shape function for France with an
        # invalid code. It should then read the shape using the country
        # name instead.
        shape = utils.shapes._get_standard_shape(
            "FR", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)

        # Mock the cartopy Reader to return dummy shapes for Victoria
        # and Ontario with invalid iso_3166_2 codes.
        mock_reader.return_value.records.return_value = [
            DummyShape({"iso_3166_2": "INVALID", "name": "Victoria"}),
            DummyShape({"iso_3166_2": "INVALID", "name": "Ontario"}),
        ]

        # Test the _get_standard_shape function for Victoria, Australia
        # with an invalid code. It should then read the shape using the
        # region name instead.
        shape = utils.shapes._get_standard_shape(
            "AU_VIC", remove_remote_islands=False
        )
        assert isinstance(shape, geopandas.GeoDataFrame)


def test_get_name_from_code():
    """
    Test the _get_name_from_code function with various country codes.

    This function checks if the function returns the correct name for
    the provided country code.
    """
    # Test the function with a valid ISO_A2 code.
    name = utils.shapes._get_name_from_code("FR")
    assert name == "France"

    # Test the function with a valid iso_3166_2 code.
    name = utils.shapes._get_name_from_code("AU_VIC")
    assert name == "Victoria"

    with patch("pycountry.countries.get") as mock_get:
        # Mock the pycountry.countries.get method to return None.
        mock_get.return_value = None

        # Test the function with a code that does not match any country.
        with pytest.raises(ValueError):
            utils.shapes._get_name_from_code("INVALIDCODE")

    with patch("pycountry.subdivisions.get") as mock_get:
        # Mock the pycountry.subdivisions.get method to return None.
        mock_get.return_value = None

        # Test the function with a code that does not match any country.
        with pytest.raises(ValueError):
            utils.shapes._get_name_from_code("INVALID_CODE")

        # Mock the pycountry.subdivisions.get method to return a list.
        mock_get.return_value = ["Invalid", "Code"]

        # Test the function with a list of codes that should not be
        # returned.
        with pytest.raises(ValueError):
            utils.shapes._get_name_from_code("INVALID_CODE")


def test_read_non_standard_shape_codes():
    """
    Test the _read_non_standard_shape_codes function.

    This function checks if the function returns a dictionary with
    non-standard shape codes for various entities.
    """
    # Call the function to read non-standard shape codes.
    codes = utils.shapes._read_non_standard_shape_codes()

    # Check if the returned codes are in the expected format.
    assert isinstance(codes, dict)
    assert "eia" in codes.keys()
    assert "tepco" in codes.keys()
    assert "neso" in codes.keys()
    assert "BR_N" in codes["ons"]
    assert "MX_PEN" in codes["cenace"]


def test_get_non_standard_shape():
    """
    Test the _get_non_standard_shape function.

    This function checks if the function returns a GeoDataFrame for
    non-standard shapes based on the provided code and data source.
    """
    # Test the function with a known non-standard shape code and data
    # source.
    shape = utils.shapes._get_non_standard_shape("MX_PEN", "cenace")
    assert isinstance(shape, geopandas.GeoDataFrame)


def test_get_entity_shape(dummy_geodf):
    """
    Test the get_entity_shape function.

    This function checks if the function returns a GeoDataFrame for
    both standard and non-standard shapes based on the provided entity
    code. It also tests the fallback mechanism for non-standard shapes.

    Parameters
    ----------
    dummy_geodf : geopandas.GeoDataFrame
        A dummy GeoDataFrame to use as a mock shape.
    """
    # Prepare a dummy GeoDataFrame with a code column for testing.
    dummy_geodf["code"] = "FR"
    dummy_geodf = dummy_geodf.set_index("code")

    with (
        patch("utils.shapes._get_standard_shape") as mock_standard,
        patch(
            "utils.shapes._read_non_standard_shape_codes"
        ) as mock_read_codes,
        patch("utils.shapes._get_non_standard_shape") as mock_nonstandard,
        patch("utils.figures.simple_plot") as mock_plot,
    ):
        # Mock the return values for the _get_standard_shape and
        # simple_plot functions.
        mock_standard.return_value = dummy_geodf
        mock_plot.return_value = None

        # Test the get_entity_shape function for a country with a
        # standard shape.
        result = utils.shapes.get_entity_shape("FR")
        assert isinstance(result, geopandas.GeoDataFrame)

        # Mock the return value for the _read_non_standard_shape_codes
        # function to simulate a non-standard shape for a subdivision.
        mock_read_codes.return_value = {"dat_source": ["XX_1"]}
        mock_nonstandard.return_value = dummy_geodf

        # Test the get_entity_shape function for a non-standard shape.
        result = utils.shapes.get_entity_shape("XX_1", make_plot=False)
        assert isinstance(result, geopandas.GeoDataFrame)

        # Mock the return value for the _read_non_standard_shape_codes
        # function with an empty list to simulate that the subdivision
        # has then a standard shape.
        mock_read_codes.return_value = {"dat_source": []}
        mock_standard.return_value = dummy_geodf

        # Test the get_entity_shape function for a subdivision shape
        # that has a standard shape.
        result = utils.shapes.get_entity_shape("XX_1", make_plot=False)
        assert isinstance(result, geopandas.GeoDataFrame)


def test_get_entity_bounds(dummy_geodf):
    """
    Test the get_entity_bounds function.

    This function checks if the function returns a list of bounds for
    the provided GeoDataFrame.

    Parameters
    ----------
    dummy_geodf : geopandas.GeoDataFrame
        A dummy GeoDataFrame to use for testing.
    """
    bounds = utils.shapes.get_entity_bounds(dummy_geodf)
    assert isinstance(bounds, list)
    assert len(bounds) == 4

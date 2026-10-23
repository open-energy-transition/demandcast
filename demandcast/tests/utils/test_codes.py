"""
License: AGPL-3.0.

Description:

    Tests for the ISO codes, names and continents of the countries and
    subdivisions, in utils/codes.py.
"""

from unittest.mock import patch

import pytest
import utils.codes


def test_get_name_from_code():
    """
    Test the _get_name_from_code function with various country codes.

    This function checks if the function returns the correct name for
    the provided country code.
    """
    # Test the function with a valid ISO_A3 code.
    name = utils.codes.get_name_from_code("FRA")
    assert name == "France"

    # Test the function with a valid iso_3166_2 code.
    name = utils.codes.get_name_from_code("AUS_VIC")
    assert name == "Victoria"

    # Test the function with a valid iso_3166_2 code.
    name = utils.codes.get_name_from_code("USA-CA")
    assert name == "California"

    # Test the function with a code for a not fully recognized country.
    name = utils.codes.get_name_from_code("XKX")
    assert name == "Kosovo"

    with (
        patch("utils.codes.get_iso_alpha_2_code") as mock_convert,
        patch("pycountry.subdivisions.get") as mock_get,
    ):
        # Mock get_iso_alpha_2_code and pycountry.subdivisions.get to
        # return invalid values.
        mock_convert.return_value = "INVALID_CODE"
        mock_get.return_value = ["Invalid", "Code"]

        # Test the function with a code that does not match any country.
        with pytest.raises(ValueError, match="should not return a list"):
            utils.codes.get_name_from_code("INVALID_CODE")

        # Mock the pycountry.subdivisions.get method to return None.
        mock_get.return_value = None

        # Test the function with a code that does not match any
        # subdivision.
        with pytest.raises(ValueError, match="not found in pycountry"):
            utils.codes.get_name_from_code("INVALID_SUBDIVISION")


def test_get_iso_alpha_2_code():
    """
    Test the conversion from ISO Alpha-3 to ISO Alpha-2 codes.

    This test checks the conversion for a country in pycountry and for
    a not fully recognized country, and that unknown codes raise an
    error.
    """
    assert utils.codes.get_iso_alpha_2_code("FRA") == "FR"
    assert utils.codes.get_iso_alpha_2_code("XKX") == "XK"
    with pytest.raises(KeyError):
        utils.codes.get_iso_alpha_2_code("INVALID")


def test_continents():
    """
    Test if the function retrieves continents correctly.

    This test checks if the function retrieves the continent for a
    specific country code and returns the expected continent.
    """
    # Check if the function retrieves the continent for a specific
    # country code.
    assert utils.codes.get_continent_code("FRA") == "EU"
    assert utils.codes.get_continent_code("USA_TEX") == "NA"
    assert utils.codes.get_continent_code("XKX") == "EU"

    # Check if the function catches errors for invalid codes.
    with pytest.raises(ValueError, match="No continent code is available"):
        utils.codes.get_continent_code("INVALID_CODE")

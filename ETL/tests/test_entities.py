# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the entities module in the ETL
    utility package.
"""

import datetime
from unittest.mock import mock_open, patch

import pytest
import pytz
import utils.entities


def test_read_codes():
    """
    Test if the entities module can read codes correctly.

    This test checks if the functions in the entities module can
    correctly read codes from a yaml file or from a specific data
    source, and if they handle errors correctly.
    """
    # Define a sample yaml file content.
    entities = [
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2014-12-15",
            "end_date": "today",
        },
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "US",
            "start_date": "2020-01-01",
            "end_date": "today",
            "time_zone": "America/Chicago",
        },
    ]

    # Read the codes from the sample yaml file and check them.
    with patch(
        "utils.entities._read_entities_info",
        return_value=entities,
    ):
        sample_codes = utils.entities.read_codes(file_path="dummy.yaml")
    assert sample_codes == ["FR", "US_TEX"]

    # Read codes belonging to a specific data source and check them.
    entsoe_codes = utils.entities.read_codes(data_source="entsoe")
    assert isinstance(entsoe_codes, list)
    assert "FR" in entsoe_codes
    assert "US_TEX" not in entsoe_codes

    # Read all codes available in the yaml files and check them.
    all_codes = utils.entities.read_all_codes()
    assert isinstance(all_codes, list)
    assert "FR" in all_codes
    assert "US_TEX" in all_codes


def test_read_codes_errors():
    """
    Test if the read_codes function handles errors correctly.

    This test checks if the function raises errors for invalid file
    paths, invalid data sources, and invalid codes.
    """
    # Check if common errors in input data are handled correctly.
    with pytest.raises(ValueError):
        utils.entities.read_codes(file_path="", data_source="")
    with pytest.raises(ValueError):
        utils.entities.read_codes(
            file_path="INVALID_DATA_SOURCE", data_source="INVALID_DATA_SOURCE"
        )
    with pytest.raises(ValueError):
        utils.entities.read_codes(data_source="INVALID_DATA_SOURCE")


def test_check_and_read_codes():
    """
    Test if the function check_and_get_codes works correctly.

    This test checks if the function can read codes from a yaml file,
    from a specific data source, or from a specific code, and if it
    handles errors correctly.
    """
    # Read codes belonging to a specific data source.
    entsoe_codes = utils.entities.check_and_get_codes(data_source="entsoe")
    assert isinstance(entsoe_codes, list)
    assert "FR" in entsoe_codes
    assert "US_TEX" not in entsoe_codes

    # Check the validity of a specific code for a specific data source.
    assert utils.entities.check_and_get_codes(
        code="FR", data_source="entsoe"
    ) == ["FR"]

    # Read codes from a specified file path and check them.
    with (
        patch("utils.entities.read_codes"),
        patch("utils.entities.read_all_codes"),
    ):
        # Mock the return value of read_codes to return codes from a
        # specific file.
        utils.entities.read_codes.return_value = ["FR", "DE"]

        # Mock the return value of read_all_codes to return all
        # available codes.
        utils.entities.read_all_codes.return_value = ["FR", "DE", "IT"]

        # Check if the codes from the file are read correctly.
        dummy_codes = utils.entities.check_and_get_codes(
            file_path="dummy.yaml"
        )

        # Check if the codes for a specific file are read correctly.
        assert isinstance(dummy_codes, list)
        assert "FR" in dummy_codes
        assert "US_TEX" not in dummy_codes


def test_check_and_read_codes_errors():
    """
    Test if the check_and_get_codes function handles errors correctly.

    This test checks if the function raises errors for invalid codes,
    invalid data sources, and if the codes in the file do not match the
    expected codes.
    """
    # Check if the function raises an error for an invalid code.
    with pytest.raises(ValueError):
        utils.entities.check_and_get_codes(
            code="INVALID_CODE", data_source="entsoe"
        )

    # Check if the function raises an error for invalid codes read from
    # a file.
    with pytest.raises(ValueError):
        with (
            patch(
                "utils.entities.read_codes",
            ),
            patch("utils.entities.read_all_codes"),
        ):
            # Mock the return value of read_codes to return invalid
            # codes.
            utils.entities.read_codes.return_value = ["US_CAL", "US_TEX"]

            # Mock the return value of read_all_codes to return all
            # available codes.
            utils.entities.read_all_codes.return_value = ["FR", "DE", "IT"]

            # Check if the function raises an error for invalid codes.
            __ = utils.entities.check_and_get_codes(file_path="dummy.yaml")


def test_read_iso_alpha_3_codes():
    """
    Test if the function get_iso_alpha_3_code works correctly.

    This test checks if the function can convert ISO alpha-2 codes to
    ISO alpha-3 codes and if it raises an error for invalid codes.
    """
    # Check if ISO alpha-3 codes are read correctly.
    assert utils.entities.get_iso_alpha_3_code("FR") == "FRA"
    assert utils.entities.get_iso_alpha_3_code("US_TEX") == "USA"
    with pytest.raises(ValueError):
        utils.entities.get_iso_alpha_3_code("INVALID_CODE")


def test_check_codes():
    """
    Test if the check_code function works correctly.

    This test checks if the function can check the validity of codes
    for a specific data source and if it raises errors for invalid
    codes or data sources.
    """
    utils.entities.check_code("US_TEX", data_source="eia")
    with pytest.raises(AssertionError):
        utils.entities.check_code("INVALID_CODE", data_source="entsoe")
    with pytest.raises(ValueError):
        utils.entities.check_code("FR", data_source="INVALID_DATA_SOURCE")


def test_time_zones():
    """
    Test if the entities module can retrieve time zones correctly.

    This test checks if the entities module can retrieve the time
    zones for countries and subdivisions. It also checks if the time
    zones are correctly set for the specified codes.
    """
    # Check the time zone of a country.
    assert utils.entities.get_time_zone("FR") == pytz.timezone("Europe/Paris")

    # Check the time zone of a subdivision.
    assert utils.entities.get_time_zone("US_CAL") == pytz.timezone(
        "America/Los_Angeles"
    )

    # Define sample yaml file content with invalid time zone.
    entities = [
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2014-12-15",
            "end_date": "today",
        }
    ]

    # Check if the function retrieves time zones from a yaml file
    # correctly.
    with patch(
        "utils.entities._read_entities_info",
        return_value=entities,
    ):
        time_zones = utils.entities._get_time_zones(file_path="dummy.yaml")

        # Check if the function returns a dictionary with correct time
        # zones.
        assert isinstance(time_zones, dict)
        assert "FR" in time_zones
        assert time_zones["FR"] == pytz.timezone("Europe/Paris")


def test_time_zones_errors():
    """
    Test if the time zone functions handle errors correctly.

    This test checks if the functions raise errors for invalid codes,
    missing time zones, and conflicting time zones in multiple yaml
    files.
    """
    # Test if invalid codes raise errors.
    with pytest.raises(ValueError):
        utils.entities.get_time_zone("INVALID_CODE")
    with pytest.raises(ValueError):
        utils.entities._get_country_time_zone("INVALID_CODE")
    with pytest.raises(ValueError):
        utils.entities._get_country_time_zone("INVALIDCODE")

    # Test not fully recognized countries.
    assert utils.entities._get_country_time_zone("XK") == pytz.timezone(
        "Europe/Belgrade"
    )

    # Define sample yaml file content with invalid time zone.
    entity_with_invalid_time_zone = [
        {
            "country_name": "France",
            "country_code": "FR",
            "start_date": "2014-12-15",
            "end_date": "today",
            "time_zone": "America/Chicago",
        }
    ]

    # Check if the function raises errors for invalid time zones.
    with pytest.raises(ValueError):
        with patch(
            "utils.entities._read_entities_info",
            return_value=entity_with_invalid_time_zone,
        ):
            utils.entities._get_time_zones()

    # Define sample yaml file content with missing time zone.
    entity_with_missing_time_zone = [
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "US",
            "start_date": "2020-01-01",
            "end_date": "today",
        }
    ]

    # Check if the function raises errors for missing time zones.
    with pytest.raises(ValueError):
        with patch(
            "utils.entities._read_entities_info",
            return_value=entity_with_missing_time_zone,
        ):
            utils.entities._get_time_zones()

    with (
        patch("utils.entities._get_data_sources") as mock_get_data_sources,
        patch("utils.entities._get_time_zones") as mock_get_time_zones,
    ):
        # Mock the return value of _get_data_sources and
        # _get_time_zones.
        mock_get_data_sources.return_value = ["source1", "source2"]
        mock_get_time_zones.return_value = None

        # Check if the function raises an error for time zones not
        # found.
        with pytest.raises(ValueError):
            utils.entities.get_time_zone("XX")

        # Define two different time zones.
        time_zone1 = datetime.timezone.utc
        time_zone2 = datetime.timezone(datetime.timedelta(hours=-1))

        # Mock the return value of _get_time_zones to return different
        # time zones for each data source.
        mock_get_time_zones.side_effect = [time_zone1, time_zone2]

        # Check if the function raises an error for conflicting time
        # zones in multiple yaml files.
        with pytest.raises(ValueError):
            utils.entities.get_time_zone("YY")


def test_date_ranges():
    """
    Test if the date ranges are read correctly.

    This test checks if the function reads the date ranges from a yaml
    file and returns a dictionary with the expected keys and values.
    """
    # Define a sample yaml file content.
    sample_yaml = """
    entities:
      - country_name: France
        country_code: FR
        start_date: 2014-12-15
        end_date: today
      - subdivision_name: Texas
        subdivision_code: TEX
        country_name: United States
        country_code: US
        start_date: 2020-01-01
        end_date: today
        time_zone: America/Chicago
    """

    # Read the date ranges from the sample yaml file.
    with patch("builtins.open", mock_open(read_data=sample_yaml)):
        date_ranges = utils.entities.read_date_ranges(file_path="dummy.yaml")

    # Check if function returns a list of date ranges.
    assert isinstance(date_ranges, dict)

    # Check if the date ranges are read correctly.
    assert date_ranges["FR"] == (
        datetime.date(2014, 12, 15),
        (datetime.datetime.today() - datetime.timedelta(days=5)).date(),
    )


def test_date_ranges_errors():
    """
    Test if the read_date_ranges function handles errors correctly.

    This test checks if the function raises errors for invalid date
    ranges, such as end dates before start dates.
    """
    # Define sample yaml file content with an invalid data.
    sample_yaml_with_invalid_date_range = """
    entities:
      - country_name: France
        country_code: FR
        start_date: 2014-12-15
        end_date: 2012-01-01
    """

    # Check if the function raises an error for invalid date ranges.
    with pytest.raises(ValueError):
        with patch(
            "builtins.open",
            mock_open(read_data=sample_yaml_with_invalid_date_range),
        ):
            utils.entities.read_date_ranges(file_path="dummy.yaml")


def test_years():
    """
    Test if the function retrieves available years correctly.

    This test checks if the function retrieves the available years for a
    specific country code and returns a list of years.
    """
    # Check if the function retrieves available years for a specific
    # country code
    years = utils.entities.get_available_years("FR")

    # Check if the years are read correctly.
    assert isinstance(years, list)
    assert len(years) > 0
    assert all(isinstance(year, int) for year in years)

    # Check if the function catches errors for invalid codes.
    with pytest.raises(ValueError):
        utils.entities.get_available_years("INVALID_CODE")


def test_continents():
    """
    Test if the function retrieves continents correctly.

    This test checks if the function retrieves the continent for a
    specific country code and returns the expected continent.
    """
    # Check if the function retrieves the continent for a specific
    # country code.
    assert utils.entities.get_continent_code("FR") == "EU"
    assert utils.entities.get_continent_code("US_TEX") == "NA"

    # Check if the function catches errors for invalid codes.
    with pytest.raises(ValueError):
        utils.entities.get_continent_code("INVALID_CODE")

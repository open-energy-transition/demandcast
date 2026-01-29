# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the entities module.
"""

import datetime
from unittest.mock import patch

import pandas
import pytest
import pytz
import utils.entities


def test_get_name_from_code():
    """
    Test the _get_name_from_code function with various country codes.

    This function checks if the function returns the correct name for
    the provided country code.
    """
    # Test the function with a valid ISO_A3 code.
    name = utils.entities.get_name_from_code("FRA")
    assert name == "France"

    # Test the function with a valid iso_3166_2 code.
    name = utils.entities.get_name_from_code("AUS_VIC")
    assert name == "Victoria"

    # Test the function with a valid iso_3166_2 code.
    name = utils.entities.get_name_from_code("USA-CA")
    assert name == "California"

    # Test the function with a code for a not fully recognized country.
    name = utils.entities.get_name_from_code("XKX")
    assert name == "Kosovo"

    with (
        patch(
            "pycountry_convert.country_alpha3_to_country_alpha2"
        ) as mock_convert,
        patch("pycountry.subdivisions.get") as mock_get,
    ):
        # Mock the pycountry_convert and pycountry.subdivisions.get
        # methods to return invalid values.
        mock_convert.return_value = "INVALID_CODE"
        mock_get.return_value = ["Invalid", "Code"]

        # Test the function with a code that does not match any country.
        with pytest.raises(ValueError):
            utils.entities.get_name_from_code("INVALID_CODE")

        # Mock the pycountry.subdivisions.get method to return None.
        mock_get.return_value = None

        # Test the function with a code that does not match any
        # subdivision.
        with pytest.raises(ValueError):
            utils.entities.get_name_from_code("INVALID_SUBDIVISION")


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
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
            "end_date": "today",
        },
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "USA",
            "start_date": datetime.date(2020, 1, 1).isoformat(),
            "end_date": "today",
            "time_zone": "America/Chicago",
        },
    ]

    # Read the codes from the sample yaml file and check them.
    with patch(
        "utils.entities._read_entities_info",
        return_value=entities,
    ):
        sample_codes = utils.entities.read_codes_in(file_path="dummy.yaml")
    assert sample_codes == ["FRA", "USA_TEX"]

    # Read codes belonging to a specific data source and check them.
    entsoe_codes = utils.entities.read_codes_in(data_source="entsoe")
    assert isinstance(entsoe_codes, list)
    assert "FRA" in entsoe_codes
    assert "USA_TEX" not in entsoe_codes

    # Read all codes available in the yaml files and check them.
    all_codes = utils.entities.read_all_codes_with_electricity_demand_data()
    assert isinstance(all_codes, list)
    assert "FRA" in all_codes
    assert "USA_TEX" in all_codes


def test_read_codes_errors():
    """
    Test if the read_codes function handles errors correctly.

    This test checks if the function raises errors for invalid file
    paths, invalid data sources, and invalid codes.
    """
    # Check if common errors in input data are handled correctly.
    with pytest.raises(ValueError):
        utils.entities.read_codes_in(file_path="", data_source="")
    with pytest.raises(ValueError):
        utils.entities.read_codes_in(
            file_path="INVALID_DATA_SOURCE", data_source="INVALID_DATA_SOURCE"
        )
    with pytest.raises(ValueError):
        utils.entities.read_codes_in(data_source="INVALID_DATA_SOURCE")


def test_get_all_codes_with_all_data():
    """
    Test if the function _get_all_codes_with_all_data works correctly.

    This test checks if the function can read the available data summary
    from a CSV file and return a list of codes for which all data is
    available.
    """
    with (
        patch("pandas.read_csv") as mock_read_csv,
        patch("os.path.join") as mock_path_join,
        patch("utils.config.read_folders_structure") as mock_read_folders,
    ):
        # Mock folder structure
        mock_read_folders.return_value = {"checks_folder": "/checks"}
        mock_path_join.return_value = "/checks/available_data_summary.csv"

        # Mock the return value of pandas.read_csv to return a sample
        # DataFrame.
        mock_read_csv.return_value = pandas.DataFrame(
            {
                "historical_population": [True, True, True, False],
                "historical_electricity_demand_per_capita": [
                    True,
                    True,
                    False,
                    True,
                ],
                "historical_gdp_ppp_per_capita": [True, False, True, True],
                "future_population": [True, True, True, False],
                "future_electricity_demand_per_capita": [
                    True,
                    True,
                    False,
                    True,
                ],
                "future_gdp_ppp_per_capita": [True, False, True, True],
                "area_greater_than_500_km2": [True, True, True, True],
            },
            index=["XY1", "XY2", "XY3", "XY4"],
        )

        # Get all codes with all data available.
        all_data_codes = utils.entities._get_all_codes_with_all_data()

        # Check if the function returns a list of codes.
        assert isinstance(all_data_codes, list)

        # Check if the codes are read correctly.
        assert "XY1" in all_data_codes
        assert "XY2" in all_data_codes
        assert "XY3" not in all_data_codes
        assert "XY4" in all_data_codes


def test_check_and_get_codes_with():
    """
    Test if the function check_and_get_codes_with works correctly.

    This test checks if the function can read codes from a yaml file,
    from a specific data source, or from a specific code, and if it
    handles errors correctly.
    """
    # Read codes belonging to a specific data source.
    entsoe_codes = utils.entities.check_and_get_codes_with(
        "electricity_demand_data", data_source="entsoe"
    )
    assert isinstance(entsoe_codes, list)
    assert "FRA" in entsoe_codes
    assert "USA_TEX" not in entsoe_codes

    # Check the validity of a specific code for a specific data source.
    assert utils.entities.check_and_get_codes_with(
        "electricity_demand_data", code="FRA", data_source="entsoe"
    ) == ["FRA"]

    # Read codes from a specified file path and check them.
    with (
        patch("utils.entities.read_codes_in") as mock_read_codes,
        patch(
            "utils.entities.read_all_codes_with_electricity_demand_data"
        ) as mock_read_all_codes,
    ):
        # Mock the return value of read_codes_in to return codes from a
        # specific file.
        mock_read_codes.return_value = ["FRA", "DEU"]

        # Mock the return value of
        # read_all_codes_with_electricity_demand_data to return all
        # available codes with demand data.
        mock_read_all_codes.return_value = [
            "FRA",
            "DEU",
            "ITA",
        ]

        # Check if the codes from the file are read correctly.
        dummy_codes = utils.entities.check_and_get_codes_with(
            "electricity_demand_data", file_path="dummy.yaml"
        )

        # Check if the codes for a specific file are read correctly.
        assert isinstance(dummy_codes, list)
        assert "FRA" in dummy_codes
        assert "USA_TEX" not in dummy_codes

    # Read codes for which all data is available.
    with patch(
        "utils.entities._get_all_codes_with_all_data"
    ) as mock_get_all_codes:
        # Mock the return value of _get_all_codes_with_all_data to
        # return a sample list of codes.
        mock_get_all_codes.return_value = ["XYZ1", "XYZ2"]

        # Get all codes with all data available.
        shape_codes = utils.entities.check_and_get_codes_with("all_data")

        # Check if the codes are read correctly.
        assert isinstance(shape_codes, list)
        assert "XYZ1" in shape_codes
        assert "XYZ2" in shape_codes
        assert "XYZ3" not in shape_codes


def test_check_and_get_codes_with_errors():
    """
    Test if the check_and_get_codes_with function handles errors.

    This test checks if the function raises errors for invalid codes,
    invalid data sources, and if the codes in the file do not match the
    expected codes.
    """
    # Check if the function raises an error for an invalid feature.
    with pytest.raises(ValueError):
        utils.entities.check_and_get_codes_with(
            "INVALID_FEATURE", code="FRA", data_source="entsoe"
        )

    # Check if the function raises an error when a data source is
    # provided for the "all_data" feature.
    with pytest.raises(ValueError):
        utils.entities.check_and_get_codes_with(
            "all_data", code="FRA", data_source="entsoe"
        )

    # Check if the function raises an error for an invalid code.
    with pytest.raises(ValueError):
        utils.entities.check_and_get_codes_with(
            "electricity_demand_data",
            code="INVALID_CODE",
            data_source="entsoe",
        )
    with pytest.raises(ValueError):
        utils.entities.check_and_get_codes_with(
            "all_data",
            code="INVALID_CODE",
        )

    # Check if the function raises an error for invalid codes read from
    # a file.
    with pytest.raises(ValueError):
        with (
            patch("utils.entities.read_codes_in") as mock_read_codes,
            patch(
                "utils.entities.read_all_codes_with_electricity_demand_data"
            ) as mock_read_all_codes,
        ):
            # Mock the return value of read_codes_in to return invalid
            # codes.
            mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]

            # Mock the return value of
            # read_all_codes_with_electricity_demand_data
            # to return all available codes with demand data.
            mock_read_all_codes.return_value = [
                "FRA",
                "DEU",
                "ITA",
            ]

            # Check if the function raises an error for invalid codes.
            utils.entities.check_and_get_codes_with(
                "electricity_demand_data", file_path="dummy.yaml"
            )

    # Check if the function raises an error for invalid codes read from
    # a file.
    with pytest.raises(ValueError):
        with (
            patch("utils.entities.read_codes_in") as mock_read_codes,
            patch(
                "utils.entities._get_all_codes_with_all_data"
            ) as mock_read_all_codes,
        ):
            # Mock the return value of read_codes_in to return invalid
            # codes.
            mock_read_codes.return_value = ["USA_CAL", "USA_TEX"]

            # Mock the return value of
            # read_all_codes_with_electricity_demand_data
            # to return all available codes with demand data.
            mock_read_all_codes.return_value = [
                "FRA",
                "DEU",
                "ITA",
            ]

            # Check if the function raises an error for invalid codes.
            utils.entities.check_and_get_codes_with(
                "all_data", file_path="dummy.yaml"
            )

    with pytest.raises(ValueError):
        with patch("utils.entities.read_codes_in") as mock_read_codes:
            # Check if the function raises an error for invalid codes.
            # Mock the return value of read_codes_in for two times, the
            # first time for electricity demand data, the second time
            # for the codes in the file.
            mock_read_codes.side_effect = [
                ["USA_CAL", "USA_TEX"],
                ["FRA", "DEU", "ITA"],
            ]

            # Check if the function raises an error when the codes in
            # the file do not match the expected codes.
            utils.entities.check_and_get_codes_with(
                "electricity_demand_data",
                data_source="entsoe",
                file_path="dummy.yaml",
            )


def test_check_codes():
    """
    Test if the check_code function works correctly.

    This test checks if the function can check the validity of codes
    for a specific data source and if it raises errors for invalid
    codes or data sources.
    """
    utils.entities.check_code_in_data_source("USA_TEX", data_source="eia")
    with pytest.raises(AssertionError):
        utils.entities.check_code_in_data_source(
            "INVALID_CODE", data_source="entsoe"
        )
    with pytest.raises(ValueError):
        utils.entities.check_code_in_data_source(
            "FRA", data_source="INVALID_DATA_SOURCE"
        )


def test_time_zones():
    """
    Test if the entities module can retrieve time zones correctly.

    This test checks if the entities module can retrieve the time
    zones for countries and subdivisions. It also checks if the time
    zones are correctly set for the specified codes.
    """
    # Check the time zone of a country.
    assert utils.entities.get_time_zone("FRA") == pytz.timezone("Europe/Paris")

    # Check the time zone of a subdivision.
    assert utils.entities.get_time_zone("USA_CAL") == pytz.timezone(
        "America/Los_Angeles"
    )

    # Check the time zone of a country with multiple time zones.
    assert utils.entities.get_time_zone("USA") == pytz.timezone(
        "America/New_York"
    )

    # Define a sample yaml file content.
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
            "end_date": "today",
        }
    ]

    # Check if the function retrieves time zones from a specified data
    # source.
    with patch(
        "utils.entities._read_entities_info",
        return_value=entities,
    ):
        time_zones = utils.entities._get_time_zones_in_data_source(
            "dummy_data_source"
        )

        # Check if the function returns a dictionary with correct time
        # zones.
        assert isinstance(time_zones, dict)
        assert "FRA" in time_zones
        assert time_zones["FRA"] == pytz.timezone("Europe/Paris")

    # Check if the function retrieves the time zone for a subdivision
    # not defined in any yaml file.
    assert utils.entities.get_time_zone("RUS_AD") == pytz.timezone(
        "Europe/Moscow"
    )


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
        utils.entities._get_time_zone_of_country("INVALID_CODE")
    with pytest.raises(ValueError):
        utils.entities._get_time_zone_of_country("INVALIDCODE")

    # Test not fully recognized countries.
    assert utils.entities._get_time_zone_of_country("XKX") == pytz.timezone(
        "Europe/Belgrade"
    )

    # Define a sample yaml file content with invalid time zone.
    entity_with_invalid_time_zone = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
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
            utils.entities._get_time_zones_in_data_source("dummy_data_source")

    # Define sample yaml file content with missing time zone.
    entity_with_missing_time_zone = [
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "USA",
            "start_date": datetime.date(2020, 1, 1).isoformat(),
            "end_date": "today",
        }
    ]

    # Check if the function raises errors for missing time zones.
    with pytest.raises(ValueError):
        with patch(
            "utils.entities._read_entities_info",
            return_value=entity_with_missing_time_zone,
        ):
            utils.entities._get_time_zones_in_data_source("dummy_data_source")

    # Check if the function raises errors when the code is not found in
    # any data source, the time zone is not found, or there are
    # conflicting time zones in multiple yaml files.
    with (
        patch(
            "utils.entities.get_electricity_demand_data_sources_containing_code"
        ) as mock_get_data_sources,
        patch(
            "utils.entities._get_time_zones_in_data_source"
        ) as mock_get_time_zones,
    ):
        # Mock the return value for the case when the code is not found
        # in any data source.
        mock_get_data_sources.return_value = []

        # Check if the function raises an error for codes not found in
        # any data source. This error is raised when the code refers to
        # a subdivision.
        with pytest.raises(ValueError):
            utils.entities._get_defined_time_zone_for_code("XX_YY")

        # Mock the return value for the case when the code is found in
        # multiple data sources.
        mock_get_data_sources.return_value = ["source1", "source2"]

        # Define two different time zones.
        time_zone1 = datetime.timezone.utc
        time_zone2 = datetime.timezone(datetime.timedelta(hours=-1))

        # Mock the return value of _get_time_zones to return different
        # time zones for each data source.
        mock_get_time_zones.side_effect = [
            {"YY": time_zone1},
            {"YY": time_zone2},
        ]

        # Check if the function raises an error for conflicting time
        # zones in multiple yaml files.
        with pytest.raises(ValueError):
            utils.entities._get_defined_time_zone_for_code("YY")


def test_date_ranges():
    """
    Test if the date ranges are read correctly.

    This test checks if the function reads the date ranges from a yaml
    file and returns a dictionary with the expected keys and values.
    """
    # Define a sample yaml file content.
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15),
            "end_date": "today",
        },
        {
            "subdivision_name": "Texas",
            "subdivision_code": "TEX",
            "country_name": "United States",
            "country_code": "USA",
            "start_date": datetime.date(2020, 1, 1),
            "end_date": "today",
            "time_zone": "America/Chicago",
        },
    ]

    # Read the codes from the sample yaml file and check them.
    with patch(
        "utils.entities._read_entities_info",
        return_value=entities,
    ):
        # Read the date ranges from the sample yaml file.
        date_ranges = utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "dummy_data_source"
        )

    # Check if function returns a list of date ranges.
    assert isinstance(date_ranges, dict)

    # Check if the date ranges are read correctly.
    assert date_ranges["FRA"] == (
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
    entities = [
        {
            "country_name": "France",
            "country_code": "FRA",
            "start_date": datetime.date(2014, 12, 15).isoformat(),
            "end_date": datetime.date(2012, 1, 1).isoformat(),
        }
    ]

    # Check if the function raises an error for invalid date ranges.
    with pytest.raises(ValueError):
        with patch(
            "utils.entities._read_entities_info",
            return_value=entities,
        ):
            utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
                "dummy_data_source"
            )


def test_years():
    """
    Test if the function retrieves available years correctly.

    This test checks if the function retrieves the available years for a
    specific country code and returns a list of years.
    """
    # Check if the function retrieves available years for a specific
    # country code
    years = utils.entities.get_available_years("FRA")

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
    assert utils.entities.get_continent_code("FRA") == "EU"
    assert utils.entities.get_continent_code("USA_TEX") == "NA"
    assert utils.entities.get_continent_code("XKX") == "EU"

    # Check if the function catches errors for invalid codes.
    with pytest.raises(ValueError):
        utils.entities.get_continent_code("INVALID_CODE")

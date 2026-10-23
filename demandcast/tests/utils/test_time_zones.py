"""
License: AGPL-3.0.

Description:

    Tests for the time zones of the countries and subdivisions, in
    utils/time_zones.py.
"""

import datetime
from unittest.mock import patch

import pytest
import pytz
from countryinfo import CountryNotFoundError

import utils.time_zones


def test_time_zones():
    """
    Test if the entities module can retrieve time zones correctly.

    This test checks if the entities module can retrieve the time
    zones for countries and subdivisions. It also checks if the time
    zones are correctly set for the specified codes.
    """
    # Check the time zone of a country.
    assert utils.time_zones.get_time_zone("FRA") == pytz.timezone(
        "Europe/Paris"
    )

    # Check the time zone of a subdivision.
    assert utils.time_zones.get_time_zone("USA_CAL") == pytz.timezone(
        "America/Los_Angeles"
    )

    # Check the time zone of a country with multiple time zones.
    assert utils.time_zones.get_time_zone("USA") == pytz.timezone(
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
        "utils.data_sources.read_entities_info",
        return_value=entities,
    ):
        time_zones = utils.time_zones._get_time_zones_in_data_source(
            "dummy_data_source"
        )

        # Check if the function returns a dictionary with correct time
        # zones.
        assert isinstance(time_zones, dict)
        assert "FRA" in time_zones
        assert time_zones["FRA"] == pytz.timezone("Europe/Paris")


@pytest.mark.network
def test_time_zone_of_subdivision_from_shapes():
    """
    Test the time zone of a subdivision not defined in any yaml file.

    The time zone is derived from the shape of the subdivision, which
    is downloaded from Natural Earth.
    """
    assert utils.time_zones.get_time_zone("RUS_AD") == pytz.timezone(
        "Europe/Moscow"
    )


@pytest.mark.parametrize(
    ("code", "time_zone"),
    [
        ("ARG", "America/Argentina/Buenos_Aires"),
        ("ATA", "Antarctica/McMurdo"),
        ("AUS", "Australia/Sydney"),
        ("BRA", "America/Sao_Paulo"),
        ("CAN", "America/Toronto"),
        ("CHL", "America/Santiago"),
        ("CHN", "Asia/Shanghai"),
        ("COD", "Africa/Kinshasa"),
        ("CYP", "Asia/Nicosia"),
        ("DEU", "Europe/Berlin"),
        ("ECU", "America/Guayaquil"),
        ("ESP", "Europe/Madrid"),
        ("FSM", "Pacific/Pohnpei"),
        ("GRL", "America/Nuuk"),
        ("IDN", "Asia/Jakarta"),
        ("KAZ", "Asia/Almaty"),
        ("KIR", "Pacific/Tarawa"),
        ("MEX", "America/Mexico_City"),
        ("MHL", "Pacific/Majuro"),
        ("MNG", "Asia/Ulaanbaatar"),
        ("MYS", "Asia/Kuala_Lumpur"),
        ("NZL", "Pacific/Auckland"),
        ("PNG", "Pacific/Port_Moresby"),
        ("PRT", "Europe/Lisbon"),
        ("PSE", "Asia/Gaza"),
        ("PYF", "Pacific/Tahiti"),
        ("RUS", "Europe/Moscow"),
        ("UKR", "Europe/Kyiv"),
        ("USA", "America/New_York"),
        ("UZB", "Asia/Tashkent"),
    ],
)
def test_time_zones_of_countries_with_several_time_zones(code, time_zone):
    """
    Test the time zone of countries with several time zones.

    The time zone must be the one of the capital city, or the first
    time zone of the country if the capital is unknown or lies in a
    time zone of another country.

    Parameters
    ----------
    code : str
        The ISO Alpha-3 code of the country.
    time_zone : str
        The expected time zone.
    """
    assert utils.time_zones._get_time_zone_of_country(code) == pytz.timezone(
        time_zone
    )


def test_time_zone_of_country_unknown_to_countryinfo():
    """
    Test the time zone of a country that countryinfo does not know.

    The first time zone of the country must be used.
    """
    with patch(
        "utils.time_zones.CountryInfo",
        side_effect=CountryNotFoundError("AUS"),
    ):
        assert utils.time_zones._get_time_zone_of_country(
            "AUS"
        ) == pytz.timezone(pytz.country_timezones["AU"][0])


def test_time_zones_errors():
    """
    Test if the time zone functions handle errors correctly.

    This test checks if the functions raise errors for invalid codes,
    missing time zones, and conflicting time zones in multiple yaml
    files.
    """
    # Test if invalid codes raise errors.
    with pytest.raises(ValueError, match="is not recognized or not available"):
        utils.time_zones.get_time_zone("INVALID_CODE")
    with pytest.raises(ValueError, match="is not available in pytz"):
        utils.time_zones._get_time_zone_of_country("INVALID_CODE")
    with pytest.raises(ValueError, match="is not available in pytz"):
        utils.time_zones._get_time_zone_of_country("INVALIDCODE")

    # Test not fully recognized countries.
    assert utils.time_zones._get_time_zone_of_country("XKX") == pytz.timezone(
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
    with (
        pytest.raises(
            ValueError, match="does not match the expected time zone"
        ),
        patch(
            "utils.data_sources.read_entities_info",
            return_value=entity_with_invalid_time_zone,
        ),
    ):
        utils.time_zones._get_time_zones_in_data_source("dummy_data_source")

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
    with (
        pytest.raises(ValueError, match="The time zone is not defined"),
        patch(
            "utils.data_sources.read_entities_info",
            return_value=entity_with_missing_time_zone,
        ),
    ):
        utils.time_zones._get_time_zones_in_data_source("dummy_data_source")

    # Check if the function raises errors when the code is not found in
    # any data source, the time zone is not found, or there are
    # conflicting time zones in multiple yaml files.
    with (
        patch(
            "utils.data_sources.get_electricity_demand_data_sources_containing_code"
        ) as mock_get_data_sources,
        patch(
            "utils.time_zones._get_time_zones_in_data_source"
        ) as mock_get_time_zones,
    ):
        # Mock the return value for the case when the code is not found
        # in any data source.
        mock_get_data_sources.return_value = []

        # Check if the function raises an error for codes not found in
        # any data source. This error is raised when the code refers to
        # a subdivision.
        with pytest.raises(
            ValueError, match="is not available in any data source"
        ):
            utils.time_zones._get_defined_time_zone_for_code("XX_YY")

        # Mock the return value for the case when the code is found in
        # multiple data sources.
        mock_get_data_sources.return_value = ["source1", "source2"]

        # Define two different time zones.
        time_zone1 = datetime.UTC
        time_zone2 = datetime.timezone(datetime.timedelta(hours=-1))

        # Mock the return value of _get_time_zones to return different
        # time zones for each data source.
        mock_get_time_zones.side_effect = [
            {"YY": time_zone1},
            {"YY": time_zone2},
        ]

        # Check if the function raises an error for conflicting time
        # zones in multiple yaml files.
        with pytest.raises(ValueError, match="Conflicting time zones"):
            utils.time_zones._get_defined_time_zone_for_code("YY")

"""
License: AGPL-3.0.

Description:

    This module gives the time zone of a country or subdivision: the
    one in the YAML files of the data sources, if any, and otherwise
    the time zone of its capital or of the centre of its shape.
"""

import datetime

import pytz
from countryinfo import CountryInfo, CountryNotFoundError
from timezonefinder import TimezoneFinder

import utils.availability
import utils.codes
import utils.data_sources
import utils.shapes

# Time zones of countries with several time zones whose capital
# coordinates in countryinfo point to the wrong one.
CAPITAL_TIME_ZONES = {
    "BRA": "America/Sao_Paulo",
}


def _get_time_zone_of_country(iso_alpha_3_code: str) -> datetime.tzinfo:
    """
    Get the time zone of a country.

    This function retrieves the time zone of a country based on its ISO
    Alpha-3 code. If the country has multiple time zones, it determines
    the appropriate time zone based on the capital city coordinates. If
    the country is not fully recognized, it uses a predefined mapping
    for the time zone.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.

    Returns
    -------
    time_zone : datetime.tzinfo
        The time zone of the country.

    Raises
    ------
    ValueError
        If the provided ISO Alpha-3 code is not available in either
        pycountry or pytz.
    """
    try:
        # Get the ISO Alpha-2 code of the country.
        iso_alpha_2_code = utils.codes.get_iso_alpha_2_code(iso_alpha_3_code)

        # Get the list of time zones for the country.
        time_zones = pytz.country_timezones[iso_alpha_2_code]
    except KeyError:
        # If the country is not on pytz, try to get the time zone
        # from the mapping dictionary of non-fully recognized
        # countries.
        if iso_alpha_3_code in utils.codes.EXTRA_ENTITIES:
            time_zones = [
                utils.codes.EXTRA_ENTITIES[iso_alpha_3_code]["time_zone"]
            ]
        else:
            raise ValueError(
                f"Country code {iso_alpha_3_code} is not available in "
                "pytz and no predefined time zone is set for it."
            ) from None

    # If there are multiple time zones, use the time zone of the
    # capital city.
    if len(time_zones) > 1:
        if iso_alpha_3_code in CAPITAL_TIME_ZONES:
            time_zone_name = CAPITAL_TIME_ZONES[iso_alpha_3_code]
        else:
            try:
                location = CountryInfo(iso_alpha_3_code).capital_latlng()
            except CountryNotFoundError:
                location = None

            capital_time_zone = (
                TimezoneFinder().timezone_at(lat=location[0], lng=location[1])
                if location
                else None
            )

            # Use the first time zone of the country if the capital is
            # unknown or lies in a time zone of another country.
            if (
                capital_time_zone is not None
                and capital_time_zone in time_zones
            ):
                time_zone_name = capital_time_zone
            else:
                time_zone_name = time_zones[0]

        time_zone = pytz.timezone(time_zone_name)
    else:
        # Get the time zone of the country.
        time_zone = pytz.timezone(time_zones[0])

    return time_zone


def _get_time_zones_in_data_source(
    data_source: str,
) -> dict[str, datetime.tzinfo]:
    """
    Get the time zones of countries and subdivisions in a data source.

    This function reads the time zones of the countries and subdivisions
    from the yaml file of a specified data source.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    dict[str, datetime.tzinfo]
        A dictionary containing the time zones of all countries and
        subdivisions defined for the specified data source.

    Raises
    ------
    ValueError
        If the time zone is not defined for a country or subdivision, or
        if the time zone in the file does not match the expected time
        zone for a country or subdivision.
    """
    # Extract the information of the countries and subdivisions.
    entities = utils.data_sources.read_entities_info(data_source=data_source)

    # Define a dictionary to store the time zones of the countries and
    # subdivisions.
    time_zones: dict[str, datetime.tzinfo] = {}

    # Iterate over the entities and extract the time zones.
    for entity in entities:
        # Extract the code of the country or subdivision.
        entity_code = utils.data_sources.get_code_of(entity)

        # If the code specifies a subdivision, extract the time zone
        # from the file.
        if "time_zone" in entity and "_" in entity_code:
            time_zone: datetime.tzinfo = pytz.timezone(entity["time_zone"])

        # If the code specifies a country, get the time zone based on
        # the country code.
        elif "time_zone" not in entity and "_" not in entity_code:
            time_zone = _get_time_zone_of_country(entity_code)

        # If the code specifies a country and the time zone is also
        # defined in the file, check if the time zone is the same as the
        # one in the file.
        elif "time_zone" in entity and "_" not in entity_code:
            time_zone = _get_time_zone_of_country(entity_code)

            # Check if the time zone is the same as the one in the file.
            if time_zone != pytz.timezone(entity["time_zone"]):
                raise ValueError(
                    f"The time zone {entity['time_zone']} in "
                    f"{data_source} for {entity_code} does "
                    f"not match the expected time zone {time_zone}."
                )

        # If the code specifies a subdivision and the time zone is not
        # defined in the file, raise an error.
        else:
            raise ValueError(
                f"The time zone is not defined for {entity_code}."
            )

        # Add the code to the dictionary and the respective time zone.
        time_zones[entity_code] = time_zone

    return time_zones


def _get_defined_time_zone_for_code(code: str) -> datetime.tzinfo:
    """
    Get the defined time zone of a country or subdivision.

    This function retrieves the time zone of a country or subdivision
    based on the definition of the time zone in the yaml files of the
    data sources.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    datetime.tzinfo
        The time zone of the country or subdivision defined in the yaml
        file.

    Raises
    ------
    ValueError
        If the provided code is not recognized or not available, or if
        if conflicting time zones are found for the subdivision.
    """
    # Get the data sources containing the provided code.
    data_sources = (
        utils.data_sources.get_electricity_demand_data_sources_containing_code(
            code
        )
    )

    if len(data_sources) == 0:
        raise ValueError(f"Code {code} is not available in any data source.")

    # Initialize a list of potential time zones from different data
    # sources.
    time_zones: list[datetime.tzinfo] = []

    # Iterate over the data sources and read the time zones.
    for data_source in data_sources:
        # Read the time zone from the file of the data source.
        time_zones_in_data_source = _get_time_zones_in_data_source(data_source)

        # Extract the time zone for the provided code and add it to the
        # list of potential time zones.
        time_zones.append(time_zones_in_data_source[code])

    # Remove duplicates from the list of time zones.
    time_zones = list(set(time_zones))

    if len(time_zones) > 1:
        raise ValueError(
            f"Conflicting time zones found for {code}: "
            f"{', '.join(str(tz) for tz in time_zones)}."
        )

    return time_zones[0]


def _get_time_zone_of_subdivision(code: str) -> datetime.tzinfo:
    """
    Get the time zone of a subdivision.

    This function retrieves the time zone of a subdivision based on
    the definition of the time zone in the yaml files of the data
    sources. If the time zone is not defined in the yaml files, it
    determines the time zone based on the coordinates of the centroid
    of the subdivision shape.

    Parameters
    ----------
    code : str
        The combination of the ISO Alpha-3 codes and the subdivision
        codes.

    Returns
    -------
    datetime.tzinfo
        The time zone of the subdivision.

    Raises
    ------
    ValueError
        If the provided code is not recognized or not available.
    """
    # Get the codes of all countries and subdivisions with demand data.
    all_codes_with_electricity_demand_data = (
        utils.data_sources.read_all_codes_with_electricity_demand_data()
    )

    # Extract the subdivisions that have the time zone defined in the
    # yaml files.
    subdivision_codes_with_defined_time_zone = [
        code for code in all_codes_with_electricity_demand_data if "_" in code
    ]

    # Get the codes of all countries and subdivisions with all data
    # available.
    all_available_codes = utils.availability.read_codes_with_all_data()

    # Extract the subdivisions that do not have the time zone defined
    # in the yaml files.
    subdivision_codes_without_defined_time_zone = [
        code
        for code in all_available_codes
        if "_" in code and code not in subdivision_codes_with_defined_time_zone
    ]

    if code in subdivision_codes_with_defined_time_zone:
        # Get the time zone defined in the yaml files.
        return _get_defined_time_zone_for_code(code)

    if code in subdivision_codes_without_defined_time_zone:
        # Get the shape of the subdivision, which must be a standard
        # shape.
        subdivision_shape = utils.shapes.get_standard_shape(code)

        # Get the centroid of the subdivision shape by projecting it to
        # an equal area projection and then back to longitude and
        # latitude (EPSG 4326) to get accurate coordinates.
        centroid = (
            subdivision_shape.geometry.to_crs("+proj=cea")
            .centroid.to_crs(epsg=4326)
            .iloc[0]
            .coords[0]
        )

        # Find time zone based on subdivision coordinates.
        time_zone_name = TimezoneFinder().timezone_at(
            lat=centroid[1], lng=centroid[0]
        )
        if time_zone_name is None:
            raise ValueError(f"No time zone found for {code}.")

        return pytz.timezone(time_zone_name)

    raise ValueError(f"Code {code} is not recognized or not available.")


def get_time_zone(code: str) -> datetime.tzinfo:
    """
    Get the time zone of a country or subdivision.

    This function retrieves the time zone of a country or subdivision
    based on its code. It uses the ISO Alpha-3 code for countries and a
    combination of the ISO Alpha-3 codes and the subdivision codes for
    subdivisions. If the code specifies a country, it retrieves the time
    zone from the pytz library. If the code specifies a subdivision, it
    retrieves the time zone from the yaml files of the data sources or
    determines it based on the coordinates of the centroid of the
    subdivision shape.

    Parameters
    ----------
    code : str
        The ISO Alpha-3 code of the country or the combination of the
        ISO Alpha-3 codes and the subdivision codes.

    Returns
    -------
    datetime.tzinfo
        The time zone of the country or subdivision.
    """
    if "_" in code:
        # If the code specifies a subdivision, get the time zone of the
        # subdivision.
        return _get_time_zone_of_subdivision(code)
    # If the code specifies a country, get the time zone of the
    # country.
    return _get_time_zone_of_country(code)

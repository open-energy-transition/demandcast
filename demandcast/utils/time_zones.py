"""
License: AGPL-3.0.

Description:

    This module gives the time zone of a country or subdivision: the
    one in the YAML files of the data sources, if any, and otherwise
    the time zone of its capital or of the centre of its shape.
"""

import datetime as dt

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


def _get_time_zone_of_country(iso_alpha_3_code: str) -> dt.tzinfo:
    """
    Get the time zone of a country.

    If the country has several time zones, the time zone of its capital
    is taken. A country that is not fully recognised takes a predefined
    time zone.

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

    Notes
    -----
    A country whose capital is unknown, or lies in a time zone of
    another country, takes its first time zone in pytz.
    """
    try:
        iso_alpha_2_code = utils.codes.get_iso_alpha_2_code(iso_alpha_3_code)
        time_zones = pytz.country_timezones[iso_alpha_2_code]
    except KeyError:
        if iso_alpha_3_code in utils.codes.EXTRA_ENTITIES:
            time_zones = [
                utils.codes.EXTRA_ENTITIES[iso_alpha_3_code]["time_zone"]
            ]
        else:
            raise ValueError(
                f"Country code {iso_alpha_3_code} is not available in "
                "pytz and no predefined time zone is set for it."
            ) from None

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

            if (
                capital_time_zone is not None
                and capital_time_zone in time_zones
            ):
                time_zone_name = capital_time_zone
            else:
                time_zone_name = time_zones[0]

        time_zone = pytz.timezone(time_zone_name)
    else:
        time_zone = pytz.timezone(time_zones[0])

    return time_zone


def _get_time_zones_in_data_source(
    data_source: str,
) -> dict[str, dt.tzinfo]:
    """
    Get the time zones of countries and subdivisions in a data source.

    The time zones are read from the yaml file of the data source.

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
    entities = utils.data_sources.read_entities_info(data_source=data_source)

    time_zones: dict[str, dt.tzinfo] = {}
    for entity in entities:
        entity_code = utils.data_sources.get_code_of(entity)

        # If the code specifies a subdivision, extract the time zone
        # from the file.
        if "time_zone" in entity and "_" in entity_code:
            time_zone: dt.tzinfo = pytz.timezone(entity["time_zone"])

        # If the code specifies a country, get the time zone based on
        # the country code.
        elif "time_zone" not in entity and "_" not in entity_code:
            time_zone = _get_time_zone_of_country(entity_code)

        # If the code specifies a country and the time zone is also
        # defined in the file, check if the time zone is the same as the
        # one in the file.
        elif "time_zone" in entity and "_" not in entity_code:
            time_zone = _get_time_zone_of_country(entity_code)
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

        time_zones[entity_code] = time_zone

    return time_zones


def _get_defined_time_zone_for_code(code: str) -> dt.tzinfo:
    """
    Get the defined time zone of a country or subdivision.

    The time zone is the one defined in the yaml files of the data
    sources.

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
        conflicting time zones are found for the subdivision.
    """
    data_sources = (
        utils.data_sources.get_electricity_demand_data_sources_containing_code(
            code
        )
    )

    if len(data_sources) == 0:
        raise ValueError(f"Code {code} is not available in any data source.")

    time_zones: list[dt.tzinfo] = []
    for data_source in data_sources:
        time_zones_in_data_source = _get_time_zones_in_data_source(data_source)
        time_zones.append(time_zones_in_data_source[code])

    time_zones = list(set(time_zones))

    if len(time_zones) > 1:
        raise ValueError(
            f"Conflicting time zones found for {code}: "
            f"{', '.join(str(tz) for tz in time_zones)}."
        )

    return time_zones[0]


def _get_time_zone_of_subdivision(code: str) -> dt.tzinfo:
    """
    Get the time zone of a subdivision.

    The time zone is the one defined in the yaml files of the data
    sources, or else the one at the centroid of the subdivision shape.

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

    Notes
    -----
    A subdivision without a time zone in the yaml files must have a
    standard shape. The centroid of the shape is computed in an
    equal-area projection, to get accurate coordinates.
    """
    all_codes_with_electricity_demand_data = (
        utils.data_sources.read_all_codes_with_electricity_demand_data()
    )

    # Extract the subdivisions that have the time zone defined in the
    # yaml files.
    subdivision_codes_with_defined_time_zone = [
        code for code in all_codes_with_electricity_demand_data if "_" in code
    ]

    all_available_codes = utils.availability.read_codes_with_all_data()

    # Extract the subdivisions that do not have the time zone defined
    # in the yaml files.
    subdivision_codes_without_defined_time_zone = [
        code
        for code in all_available_codes
        if "_" in code and code not in subdivision_codes_with_defined_time_zone
    ]

    if code in subdivision_codes_with_defined_time_zone:
        return _get_defined_time_zone_for_code(code)

    if code in subdivision_codes_without_defined_time_zone:
        subdivision_shape = utils.shapes.get_standard_shape(code)
        centroid = (
            subdivision_shape.geometry.to_crs("+proj=cea")
            .centroid.to_crs(epsg=4326)
            .iloc[0]
            .coords[0]
        )
        time_zone_name = TimezoneFinder().timezone_at(
            lat=centroid[1], lng=centroid[0]
        )
        if time_zone_name is None:
            raise ValueError(f"No time zone found for {code}.")

        return pytz.timezone(time_zone_name)

    raise ValueError(f"Code {code} is not recognized or not available.")


def get_time_zone(code: str) -> dt.tzinfo:
    """
    Get the time zone of a country or subdivision.

    A country has its time zone in the pytz library. A subdivision has
    its time zone in the yaml files of the data sources, or else that
    of the coordinates of the centroid of its shape.

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
        return _get_time_zone_of_subdivision(code)
    return _get_time_zone_of_country(code)

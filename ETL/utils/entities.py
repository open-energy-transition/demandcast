# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module povides utility functions to read country and
    subdivision codes, time zones, and date ranges from yaml files.
"""

import datetime
import logging
import os

import pandas
import pycountry
import pycountry_convert
import pytz
import yaml
from countryinfo import CountryInfo
from timezonefinder import TimezoneFinder

import utils.directories
import utils.shapes

# Define the time zones of not fully recognized countries that are not
# included in pytz.
extra_entity_time_zone = {
    "XKX": ["Europe/Belgrade"],  # Kosovo
}

# Define the continent codes of not fully recognized countries that
# are not included in pycountry_convert.
extra_entity_continent = {
    "XKX": "EU",  # Kosovo
}


def get_name_from_code(code: str) -> str:
    """
    Get the name of a country or subdivision from its code.

    This function retrieves the name of a country or subdivision based
    on its code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    name : str
        The name of the country or subdivision.

    Raises
    ------
    ValueError
        If the country or subdivision with the given code is not found
        in pycountry.
    """
    # Extract the ISO Alpha-3 code from the code.
    if "_" not in code and "-" not in code:
        iso_alpha_3_code = code
    elif "_" in code:
        iso_alpha_3_code = code.split("_")[0]
    else:
        iso_alpha_3_code = code.split("-")[0]

    # Get the ISO Alpha-2 code of the country itself or the country to
    # which the subdivision belongs.
    iso_alpha_2_code = pycountry_convert.country_alpha3_to_country_alpha2(
        iso_alpha_3_code
    )

    # Get the name of the country or subdivision of interest based on
    # its code.
    if "_" not in code and "-" not in code:
        # Get the country name from the ISO Alpha-3 code.
        name = pycountry_convert.country_alpha2_to_country_name(
            iso_alpha_2_code
        )
    else:
        # Reconstruct the subdivision code.
        if "_" in code:
            subdivision_code = iso_alpha_2_code + "-" + code.split("_")[1]
        else:
            subdivision_code = iso_alpha_2_code + "-" + code.split("-")[1]

        # Get the subdivision information from the code.
        subdivision = pycountry.subdivisions.get(code=subdivision_code)

        # Handle if subdivision is a list or a single object.
        if isinstance(subdivision, list):
            raise ValueError(
                "pycountry.subdivisions should not return a list."
            )
        else:
            name = subdivision.name

    return name


def read_data_sources() -> list[str]:
    """
    Read the the names of the data sources.

    This function reads the names of the data sources from the yaml
    files in the folder containing the modules for electricity demand
    retreivals. The names are extracted from the file names.

    Returns
    -------
    data_sources : list[str]
        The list of available data sources.
    """
    # Get the paths to the yaml files of the data sources.
    file_paths = utils.directories.list_yaml_files(
        "electricity_demand_data_sources_folder"
    )

    # Read the data sources from the file names.
    data_sources = [
        os.path.basename(file_path).split(".")[0] for file_path in file_paths
    ]

    # Sort the data sources alphabetically.
    data_sources.sort()

    return data_sources


def _read_entities_info(
    file_path: str = "", data_source: str = ""
) -> list[dict]:
    """
    Get the information of the countries and subdivisions.

    This function reads the information of the countries and
    subdivisions from a specified yaml file or from the yaml file of a
    specified data source.

    Parameters
    ----------
    file_path : str, optional
        The path to the file containing the information of the countries
        and subdivisions. If provided, the function will read the yaml
        file from this path.
    data_source : str, optional
        The name of the data source. If provided, the function will look
        for a yaml file with the same name in the retrieval scripts
        folder.

    Returns
    -------
    list[dict[str, str | datetime.date]]
        The list of dictionaries containing the information for each
        country and subdivision.

    Raises
    ------
    ValueError
        If the data source is provided but not valid, or if both
        file_path and data_source are provided, or if neither is
        provided.
    """
    if file_path == "" and data_source != "":
        # Check if the data source is valid.
        if data_source not in read_data_sources():
            raise ValueError(
                f"Invalid data source: {data_source}. Available data "
                f"sources are: {', '.join(read_data_sources())}"
            )

        # Get the path to the yaml file of the data source.
        file_path = os.path.join(
            utils.directories.read_folders_structure()[
                "electricity_demand_data_sources_folder"
            ],
            f"{data_source.lower()}.yaml",
        )
    elif file_path == "" and data_source == "":
        # If no file path or data source is provided, raise an error.
        raise ValueError("Either file_path or data_source must be provided.")
    elif file_path != "" and data_source != "":
        # If both data source and data source file path are provided,
        # raise an error.
        raise ValueError(
            "Only one of file_path or data_source must be provided."
        )

    # Read the content from the file.
    with open(file_path, "r") as file:
        content = yaml.safe_load(file)

    # Return the information of the countries and subdivisions.
    return content["entities"]


def _get_electricity_demand_data_sources_containing_code(
    code: str,
) -> list[str]:
    """
    Get the data sources containing the provided code.

    This function retrieves the data sources for which the provided code
    is available. It checks all yaml files in the retrieval scripts
    folder and returns a list of data sources that contain the code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    data_sources : list[str]
        The list of data sources that contain the provided code.
    """
    # Get the available data sources.
    data_sources = read_data_sources()

    # Initialize a list to store the data sources containing the code.
    data_sources_containing_code = []

    # Iterate over the file paths and check if the code is in the file.
    for data_source in data_sources:
        # Read the content from the file.
        entities = _read_entities_info(data_source=data_source)

        # Iterate over the entities in the file.
        for entity in entities:
            # Extract the code of the country or subdivision.
            entity_code = (
                entity["country_code"] + "_" + entity["subdivision_code"]
                if "subdivision_code" in entity
                else entity["country_code"]
            )

            # Check if the provided code matches the entity code.
            if entity_code == code:
                # Add the data source to the list.
                data_sources_containing_code.append(data_source)

    return data_sources_containing_code


def read_codes_in(file_path: str = "", data_source: str = "") -> list[str]:
    """
    Read the codes of the countries and subdivisions.

    This function reads the codes of the countries and subdivision from
    a specified yaml file or from the yaml file of a specified data
    source. It extracts the codes for each country or subdivision and
    returns a list of codes.

    Parameters
    ----------
    file_path : str, optional
        The path to the file containing the information of the countries
        and subdivisions. If provided, the function will read the yaml
        file from this path.
    data_source : str, optional
        The name of the data source. If provided, the function will look
        for a yaml file with the same name in the retrieval scripts
        folder.

    Returns
    -------
    list[str]
        A list of ISO Alpha-3 codes of the countries or the
        combination of the ISO Alpha-3 codes and the subdivision codes.
    """
    # Extract the information of the countries and subdivisions.
    entities = _read_entities_info(
        file_path=file_path, data_source=data_source
    )

    # Extract and return codes.
    return [
        entity["country_code"] + "_" + entity["subdivision_code"]
        if "subdivision_code" in entity
        else entity["country_code"]
        for entity in entities
    ]


def read_all_codes_with_electricity_demand_data() -> list[str]:
    """
    Read the codes of all countries and subdivisions with demand data.

    This function reads the codes of all countries and subdivisions for
    which high-resolution electricity demand data is available. It
    checks all yaml files in the retrieval scripts folder and combines
    the codes from all files, removing duplicates.

    Returns
    -------
    list[str]
        A list of codes of all countries and subdivisions for which
        high-resolution electricity demand data is available.
    """
    # Get the available data sources of electricity demand data.
    data_sources = read_data_sources()

    # Define a list to store the codes.
    codes = []
    # Iterate over the yaml files and read the codes from each file.
    for data_source in data_sources:
        # Read the codes from the file.
        file_codes = read_codes_in(data_source=data_source)

        # Append the codes to the list.
        codes.extend(file_codes)

    # Remove duplicates and return the list of codes.
    return list(set(codes))


def check_code_in_data_source(code: str, data_source: str) -> None:
    """
    Check if the code is available in the specified data source.

    This function checks if the provided code is valid by comparing it
    with the list of available codes from the specified data source.

    Parameters
    ----------
    code : str
        The code of the entity (country or subdivision) to check.
    data_source : str
        The name of the data source from which to read the available
        codes.
    """
    # Check if the code is valid.
    assert code in read_codes_in(data_source=data_source), (
        f"Invalid code: {code}. Available codes are: "
        f"{', '.join(read_codes_in(data_source=data_source))}"
    )


def _get_all_codes_with_all_data() -> list[str]:
    """
    Get the codes of all countries and subdivisions with all data.

    This function retrieves the codes of all countries and
    subdivisions for which all required data for the demand forecasting
    model is available. This includes the availability of shapes,
    historical and future population data, historical and future
    electricity demand per capita, and historical and future GDP PPP per
    capita.

    Returns
    -------
    list[str]
        A list of codes of all countries and subdivisions for which all
        required data is available.
    """
    # Read the CSV file containing the available data information.
    data = pandas.read_csv(
        os.path.join(
            utils.directories.read_folders_structure()["checks_folder"],
            "data_availability_summary.csv",
        ),
        index_col=0,
        na_filter=False,
    )

    # Initialize a list to store the codes.
    all_codes = []

    # Filter the data to get only the countries and subdivisions with
    # all required data available.
    for code in data.index:
        if (
            data.loc[code, "historical_population"]
            and data.loc[code, "historical_electricity_demand_per_capita"]
            and data.loc[code, "historical_gdp_ppp_per_capita"]
            and data.loc[code, "future_population"]
            and data.loc[code, "future_electricity_demand_per_capita"]
            and data.loc[code, "future_gdp_ppp_per_capita"]
        ):
            all_codes.append(code)
        elif (
            data.loc[code, "historical_electricity_demand_per_capita"]
            and data.loc[code, "future_electricity_demand_per_capita"]
            and data.loc[code, "area_greater_than_500_km2"]
        ):
            # In this case, the population and GDP PPP per capita data
            # can be estimated by aggregating gridded data.
            all_codes.append(code)

    return all_codes


def check_and_get_codes_with(
    feature: str,
    code: str | None = None,
    data_source: str | None = None,
    file_path: str | None = None,
) -> list[str]:
    """
    Check code validity (if provided) or get all available codes.

    This function checks if the code provided as an argument or the
    codes in the specified file are valid by comparing them with the
    list of available codes for which a certain feature is available.
    If no code or file path is provided, it returns all available codes
    for which the feature is available.

    Parameters
    ----------
    feature : str
        The feature of interest. Available features are
        "electricity_demand_data" and "all_data".
    code : str, optional
        The code of the country or subdivision.
    data_source : str, optional
        The name of the data source.
    file_path : str, optional
        The path to the file containing the information of the countries
        and subdivisions.

    Returns
    -------
    codes : list[str]
        The list of codes of the countries and subdivisions of interest.

    Raises
    ------
    ValueError
        If the feature is not valid, or if the code is not available,
        or if none of the codes in the file are available.
    """
    # Get the list of available countries and subdivisions according to
    # the arguments.
    if feature == "electricity_demand_data":
        if data_source is not None:
            all_codes = read_codes_in(data_source=data_source)
        else:
            all_codes = read_all_codes_with_electricity_demand_data()
    elif feature == "all_data":
        if data_source is not None:
            raise ValueError(
                "The 'all_data' feature is not associated with a data source."
            )
        all_codes = _get_all_codes_with_all_data()
    else:
        raise ValueError(
            f"Invalid feature: {feature}. Available features are: "
            "'electricity_demand_data' and 'all_data'."
        )

    if code is not None:
        # Check if the code is available.
        if code not in all_codes:
            raise ValueError(
                f"Code {code} is not available. Please choose one of the "
                f"following: {', '.join(all_codes)}"
            )
        else:
            codes = [code]

    elif file_path is not None:
        # Get the list of countries and subdivisions available on the
        # specified file.
        codes = read_codes_in(file_path=file_path)

        # Initialize a list of the remaining codes.
        remaining_codes = codes.copy()

        # Check if the codes are available.
        for code in codes:
            if code not in all_codes:
                logging.error(f"Code {code} is not available.")
                remaining_codes.remove(code)

        # Check if there are any codes left.
        if len(remaining_codes) == 0:
            raise ValueError(
                "None of the codes in the file are available. Please choose "
                f"from the following: {', '.join(all_codes)}"
            )
        else:
            # If there are codes left, return them.
            codes = remaining_codes
    else:
        # If no code or file path is provided, use all available codes.
        codes = all_codes

    return codes


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
        iso_alpha_2_code = pycountry_convert.country_alpha3_to_country_alpha2(
            iso_alpha_3_code
        )

        # Get the list of time zones for the country.
        time_zones = pytz.country_timezones[iso_alpha_2_code]
    except KeyError:
        # If the country is not on pytz, try to get the time zone
        # from the mapping dictionary of non-fully recognized
        # countries.
        if iso_alpha_3_code in extra_entity_time_zone:
            time_zones = extra_entity_time_zone[iso_alpha_3_code]
        else:
            raise ValueError(
                f"Country code {iso_alpha_3_code} is not available in "
                "pytz and no predefined time zone is set for it."
            )

    # If there are multiple time zones, find the time zone based on
    # the capital city.
    if len(time_zones) > 1:
        # Get the country information from CountryInfo.
        for __, info in CountryInfo().all().items():
            if info["ISO"]["alpha3"] == iso_alpha_3_code:
                break

        # Get the capital city coordinates.
        location = info["capital_latlng"]

        # Find time zone based on capital city coordinates.
        time_zone_name = TimezoneFinder().timezone_at(
            lat=location[0], lng=location[1]
        )
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
    entities = _read_entities_info(data_source=data_source)

    # Define a dictionary to store the time zones of the countries and
    # subdivisions.
    time_zones: dict[str, datetime.tzinfo] = {}

    # Iterate over the entities and extract the time zones.
    for entity in entities:
        # Extract the code of the country or subdivision.
        entity_code = (
            entity["country_code"] + "_" + entity["subdivision_code"]
            if "subdivision_code" in entity
            else entity["country_code"]
        )

        # If the code specifies a subdivision, extract the time zone
        # from the file.
        if "time_zone" in entity and "_" in entity_code:
            time_zone = pytz.timezone(entity["time_zone"])

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
    data_sources = _get_electricity_demand_data_sources_containing_code(code)

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
        read_all_codes_with_electricity_demand_data()
    )

    # Extract the subdivisions that have the time zone defined in the
    # yaml files.
    subdivision_codes_with_defined_time_zone = [
        code for code in all_codes_with_electricity_demand_data if "_" in code
    ]

    # Get the codes of all countries and subdivisions with all data
    # available.
    all_available_codes = _get_all_codes_with_all_data()

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

    elif code in subdivision_codes_without_defined_time_zone:
        # Get the shape of the subdivision, which must be a standard
        # shape.
        subdivision_shape = utils.shapes.get_standard_shape(code)

        # Get the centroid of the subdivision shape by projecting it to
        # an equal area projection and then back to the original
        # projection to get accurate coordinates.
        centroid = (
            subdivision_shape.geometry.to_crs("+proj=cea")
            .centroid.to_crs(subdivision_shape.crs)
            .iloc[0]
            .coords[0]
        )

        # Find time zone based on subdivision coordinates.
        time_zone_name = TimezoneFinder().timezone_at(
            lat=centroid[1], lng=centroid[0]
        )

        return pytz.timezone(time_zone_name)

    else:
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
    else:
        # If the code specifies a country, get the time zone of the
        # country.
        return _get_time_zone_of_country(code)


def read_date_ranges_of_electricity_demand_in_data_source(
    data_source: str,
) -> dict[str, tuple[datetime.date, datetime.date]]:
    """
    Read the start and end dates of the available data.

    This function reads the start and end dates of the available data
    for the countries and subdivisions from the yaml file of a specified
    data source. It extracts the start and end dates for each country or
    subdivision and returns a dictionary where the keys are the codes of
    the countries or subdivisions and the values are tuples containing
    the start and end dates.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    start_and_end_dates : dict[str, tuple[datetime.date, datetime.date]]
        The dictionary containing the start and end dates of the
        available data for the countries and subdivisions.

    Raises
    ------
    ValueError
        If the start date is after the end date for a country or
        subdivision.
    """
    # Extract the information of the countries and subdivisions.
    entities = _read_entities_info(data_source=data_source)

    # Define a dictionary to store the start and end dates of the
    # available data for the countries and subdivisions.
    start_and_end_dates: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Iterate over the entities and extract the start and end dates.
    for entity in entities:
        # Extract the code of the country or subdivision.
        code = (
            entity["country_code"] + "_" + entity["subdivision_code"]
            if "subdivision_code" in entity
            else entity["country_code"]
        )

        # Extract the start and end dates of the available data.
        start_date = entity["start_date"]
        if entity["end_date"] == "today":
            # If the end date is "today", set it to a few days before
            # today to avoid issues with the latest data.
            end_date = (
                datetime.datetime.today() - datetime.timedelta(days=5)
            ).date()
        else:
            end_date = entity["end_date"]

        # Add the code to the dictionary and the respective start and
        # end dates.
        start_and_end_dates[code] = (start_date, end_date)

        # Check if the start date is before the end date.
        if start_date > end_date:
            raise ValueError(
                f"The start date {start_date} is after the end date "
                f"{end_date} for {code}."
                ""
            )

    return start_and_end_dates


def read_all_date_ranges() -> dict[str, tuple[datetime.date, datetime.date]]:
    """
    Read the all start and end dates of the available data.

    This function reads the start and end dates of the available data
    for all countries and subdivisions from all yaml files in the
    retrieval scripts folder. It combines the start and end dates from
    all files and checks for duplicates. If a duplicate is found, it
    keeps the dates giving the longest period for that country or
    subdivision.

    Returns
    -------
    start_and_end_dates : dict[str, tuple[datetime.date, datetime.date]]
        The dictionary containing the start and end dates of the
        available data for the countries and subdivisions.
    """
    # Get the available data sources.
    data_sources = read_data_sources()

    # Define a dictionary to store the start and end dates of the
    # available data for the countries and subdivisions.
    start_and_end_dates: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Iterate over the yaml files and read the start and end dates from
    # each file.
    for data_source in data_sources:
        # Read the start and end dates from the file.
        file_start_and_end_dates = (
            read_date_ranges_of_electricity_demand_in_data_source(data_source)
        )

        # Check for duplicates.
        for code, (start_date, end_date) in file_start_and_end_dates.items():
            # If the code is already in the dictionary, get the dates
            # giving the longest period.
            if code in start_and_end_dates:
                existing_start_date, existing_end_date = start_and_end_dates[
                    code
                ]
                existing_time_difference = (
                    existing_end_date - existing_start_date
                ).days
                new_time_difference = (end_date - start_date).days
                if new_time_difference > existing_time_difference:
                    # If the new time difference is greater, update the
                    # start and end dates.
                    start_and_end_dates[code] = (start_date, end_date)
            else:
                # If the code is not in the dictionary, add it to the
                # dictionary.
                start_and_end_dates[code] = (start_date, end_date)

    return start_and_end_dates


def get_available_years(code: str) -> list[int]:
    """
    Get the years of the available data for a country or subdivision.

    This function retrieves the years of the available data for a
    country or subdivision based on its code. It reads the start and end
    dates of the available data for the country or subdivision, converts
    them to the time zone of the country or subdivision, and returns a
    list of years for which data is available.

    Parameters
    ----------
    code : str
        The ISO Alpha-3 code of the country or the combination of the
        ISO Alpha-3 and the subdivision code.

    Returns
    -------
    list[int]
        The years of the available data for the country or subdivision.
    """
    # Get the time zone of the country or subdivision.
    entity_time_zone = get_time_zone(code)

    # Read the start and end dates of the available data for the country
    # or subdivision of interest.
    start_date, end_date = read_all_date_ranges()[code]

    # Convert the start and end dates to the time zone of the country or
    # subdivision.
    start_date = (
        pandas.to_datetime(start_date)
        .tz_localize(entity_time_zone)
        .tz_convert("UTC")
    )
    end_date = (
        pandas.to_datetime(end_date)
        .tz_localize(entity_time_zone)
        .tz_convert("UTC")
    )

    # Return the years of the data availability.
    return [year for year in range(start_date.year, end_date.year + 1)]


def get_continent_code(code: str) -> str:
    """
    Get the continent of a country or subdivision.

    This function retrieves the continent code of a country or
    subdivision based on its code. It uses the pycountry_convert library
    to get the continent code from the ISO Alpha-3 code of the country
    itself or the country to which the subdivision belongs.

    Parameters
    ----------
    code : str
        The ISO Alpha-3 code of the country or the combination of the
        ISO Alpha-3 and the subdivision code.

    Returns
    -------
    str
        The continent code of the country or subdivision.

    Raises
    ------
    ValueError
        If the provided code is not available in either pycountry or
        pycountry_convert.
    """
    # Check if the code specifies a subdivision.
    if "_" in code:
        # Extract the ISO Alpha-3 code of the country.
        iso_alpha_3_code = code.split("_")[0]
    else:
        # If the code does not specify a subdivision, use the ISO
        # Alpha-3 code directly.
        iso_alpha_3_code = code

    # Get the continent code from the ISO Alpha-3 code.
    try:
        # Get the ISO Alpha-2 code of the country.
        iso_alpha_2_code = pycountry_convert.country_alpha3_to_country_alpha2(
            iso_alpha_3_code
        )

        # Get the continent code of the country.
        continent_code = pycountry_convert.country_alpha2_to_continent_code(
            iso_alpha_2_code
        )
    except KeyError:
        if iso_alpha_3_code in extra_entity_continent:
            continent_code = extra_entity_continent[iso_alpha_3_code]
        else:
            raise ValueError(
                f"Country code {iso_alpha_3_code} is not available in "
                "pycountry_convert and no predefined continent code is set "
                "for it."
            )

    return continent_code

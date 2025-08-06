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

# Add countries that are not fully recognized.
pycountry.countries.add_entry(
    alpha_2="XK", alpha_3="XKX", name="Kosovo", numeric="926"
)


def read_data_sources() -> list[str]:
    """
    Read the the names of the data sources.

    This function reads the names of the data sources from the yaml
    files in the retrieval scripts folder. The names are extracted
    from the file names.

    Returns
    -------
    data_sources : list[str]
        The list of data sources available in the retrieval scripts
        folder.
    """
    # Get the paths to the yaml files of the data sources.
    file_paths = utils.directories.list_yaml_files("retrieval_scripts_folder")

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
                "retrieval_scripts_folder"
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


def _get_data_sources(code: str) -> list[str]:
    """
    Get the data source for a given code.

    This function retrieves the data source for which the provided code
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
    # Get the paths to the yaml files of the data sources.
    file_paths = utils.directories.list_yaml_files("retrieval_scripts_folder")

    # Initialize a list to store the data sources.
    data_sources = []

    # Iterate over the file paths and check if the code is in the file.
    for file_path in file_paths:
        # Read the content from the file.
        entities = _read_entities_info(file_path=file_path)

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
                data_sources.append(os.path.basename(file_path).split(".")[0])

    return data_sources


def read_codes(file_path: str = "", data_source: str = "") -> list[str]:
    """
    Read the codes of the countries and subdivisions.

    This function reads the ISO Alpha-2 codes of the countries or the
    combination of the ISO Alpha-2 codes and the subdivision codes from
    a specified yaml file or from the yaml file of a specified data
    source.

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
        A list of ISO Alpha-2 codes of the countries or the
        combination of the ISO Alpha-2 codes and the subdivision codes.
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


def read_all_codes() -> list[str]:
    """
    Read the codes of all countries and subdivisions.

    This function reads the ISO Alpha-2 codes of all countries or the
    combination of the ISO Alpha-2 codes and the subdivision codes from
    all yaml files in the retrieval scripts folder. It combines the
    codes from all files and removes duplicates.

    Returns
    -------
    list[str]
        A list of ISO Alpha-2 codes of the countries or the
        combination of the ISO Alpha-2 codes and the subdivision codes.
    """
    # Get the path of all yaml files in the retrieval scripts folder.
    yaml_file_paths = utils.directories.list_yaml_files(
        "retrieval_scripts_folder"
    )

    # Define a list to store the codes.
    codes = []
    # Iterate over the yaml files and read the codes from each file.
    for yaml_file_path in yaml_file_paths:
        # Read the codes from the file.
        file_codes = read_codes(file_path=yaml_file_path)

        # Append the codes to the list.
        codes.extend(file_codes)

    # Remove duplicates and return the list of codes.
    return list(set(codes))


def check_code(code: str, data_source: str) -> None:
    """
    Check if the code is available.

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
    assert code in read_codes(data_source=data_source), (
        f"Invalid code: {code}. Available codes are: "
        f"{', '.join(read_codes(data_source=data_source))}"
    )


def check_and_get_codes(
    code: str | None = None,
    data_source: str | None = None,
    file_path: str | None = None,
) -> list[str]:
    """
    Check code validity (if provided) or get all available codes.

    This function checks if the provided code is valid by comparing it
    with the list of available codes from the specified data source. If
    no code is provided, it returns all available codes from the data
    source or from the specified yaml file.

    Parameters
    ----------
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
        If the provided code is not available, or if none of the codes
        in the file are available.
    """
    # Get the list of available countries and subdivisions according to
    # the arguments.
    if data_source is not None:
        all_codes = read_codes(data_source=data_source)
    else:
        all_codes = read_all_codes()

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
        codes = read_codes(file_path=file_path)

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


def get_iso_alpha_3_code(code: str) -> str:
    """
    Get the ISO Alpha-3 code of a country.

    This function extracts the ISO Alpha-2 code of the country from the
    provided code, which can be either the ISO Alpha-2 code of the
    country or a combination of the ISO Alpha-2 codes and the
    subdivision codes. It then retrieves the ISO Alpha-3 code of the
    country using the pycountry library.

    Parameters
    ----------
    code : str
        The ISO Alpha-2 code of the country or the combination of the
        ISO Alpha-2 codes and the subdivision codes.

    Returns
    -------
    str
        The ISO Alpha-3 code of the country.

    Raises
    ------
    ValueError
        If the provided code is not recognized or not available.
    """
    # Check if the code specifies a subdivision.
    if "_" in code:
        # Extract the ISO Alpha-2 code of the country.
        iso_alpha_2_code = code.split("_")[0]
    else:
        # If the code does not specify a subdivision, use the ISO
        # Alpha-2 code directly.
        iso_alpha_2_code = code

    # Get the country information.
    country_info = pycountry.countries.get(alpha_2=iso_alpha_2_code)

    # Get the ISO Alpha-3 code of the country.
    if country_info is not None:
        return country_info.alpha_3
    else:
        raise ValueError(
            f"Country code {iso_alpha_2_code} is not recognized or not "
            "available."
        )


def _get_country_time_zone(iso_alpha_2_code: str) -> datetime.tzinfo:
    """
    Get the time zone of a country.

    This function retrieves the time zone of a country based on its ISO
    Alpha-2 code. If the country has multiple time zones, it determines
    the appropriate time zone based on the capital city coordinates. If
    the country is not fully recognized, it uses a predefined mapping
    for the time zone.

    Parameters
    ----------
    iso_alpha_2_code : str
        The ISO Alpha-2 code of the country.

    Returns
    -------
    time_zone : datetime.tzinfo
        The time zone of the country.

    Raises
    ------
    ValueError
        If the provided ISO Alpha-2 code is not recognized or if it
        specifies a subdivision instead of a country.
    """
    # Define the time zones of countries that are not fully recognized.
    not_fully_recognized_countries = {
        "XK": ["Europe/Belgrade"]  # Kosovo
    }

    if "_" not in iso_alpha_2_code:
        # Get the list of time zones for the country.
        try:
            time_zones = pytz.country_timezones[iso_alpha_2_code]
        except KeyError:
            # If the country is not on pytz, try to get the time zone
            # from the mapping dictionary of non-fully recognized
            # countries.
            if iso_alpha_2_code in not_fully_recognized_countries:
                time_zones = not_fully_recognized_countries[iso_alpha_2_code]
            else:
                raise ValueError(
                    f"Country code {iso_alpha_2_code} is not recognized."
                )

        # If there are multiple time zones, find the time zone based on
        # the capital city.
        if len(time_zones) > 1:
            # Get the country name.
            country = pycountry.countries.get(alpha_2=iso_alpha_2_code)

            # Get the capital city coordinates.
            location = CountryInfo(country.name).capital_latlng()

            # Find time zone based on capital city coordinates.
            time_zone_name = TimezoneFinder().timezone_at(
                lat=location[0], lng=location[1]
            )
            time_zone = pytz.timezone(time_zone_name)
        else:
            # Get the time zone of the country.
            time_zone = pytz.timezone(time_zones[0])
    else:
        raise ValueError(
            f"Expected ISO Alpha-2 code, but got {iso_alpha_2_code}."
        )

    return time_zone


def _get_time_zones(
    code: str = "", file_path: str = "", data_source: str = ""
) -> datetime.tzinfo | dict[str, datetime.tzinfo]:
    """
    Get the time zones of the countries and subdivisions.

    This function reads the time zones of the countries and subdivisions
    from a specified yaml file or from the yaml file of a specified data
    source. It then extracts the time zone of the specified country or
    subdivision if the code is provided. If the code is not provided,
    it returns the time zones of all countries and subdivisions defined
    in the file.

    Parameters
    ----------
    code : str, optional
        The ISO Alpha-2 code of the country or the combination of the
        ISO Alpha-2 codes and the subdivision codes. If provided, the
        function will return its time zone.
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
    datetime.tzinfo | dict[str, datetime.tzinfo]
        The time zone of the specified country or subdivision or a
        dictionary containing the time zones of all countries and
        subdivisions defined in the file.

    Raises
    ------
    ValueError
        If the time zone is not defined for a country or subdivision, or
        if the time zone in the file does not match the expected time
        zone for a country or subdivision.
    """
    # Extract the information of the countries and subdivisions.
    entities = _read_entities_info(
        file_path=file_path, data_source=data_source
    )

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
            time_zone = _get_country_time_zone(entity_code)

        # If the code specifies a country and the time zone is also
        # defined in the file, check if the time zone is the same as the
        # one in the file.
        elif "time_zone" in entity and "_" not in entity_code:
            time_zone = _get_country_time_zone(entity_code)

            # Check if the time zone is the same as the one in the file.
            if time_zone != pytz.timezone(entity["time_zone"]):
                raise ValueError(
                    f"The time zone {entity['time_zone']} in "
                    f"{os.path.basename(file_path)} for {entity_code} does "
                    f"not match the expected time zone {time_zone}."
                )

        # If the code specifies a subdivision and the time zone is not
        # defined in the file, raise an error.
        else:
            raise ValueError(
                f"The time zone is not defined for {entity_code}."
            )

        # If the code is provided, return the time zone of the country
        # or subdivision.
        if code != "" and entity_code == code:
            return time_zone

        # Add the code to the dictionary and the respective time zone.
        time_zones[entity_code] = time_zone

    return time_zones


def get_time_zone(code: str) -> datetime.tzinfo:
    """
    Get the time zone of a country or subdivision.

    This function retrieves the time zone of a country or subdivision
    based on its ISO Alpha-2 code or a combination of the ISO Alpha-2
    codes and the subdivision codes. It checks if the code is in the
    dictionary of time zones and returns the corresponding time zone.

    Parameters
    ----------
    code : str
        The ISO Alpha-2 code of the country or the combination of the
        ISO Alpha-2 codes and the subdivision codes.

    Returns
    -------
    datetime.tzinfo
        The time zone of the country or subdivision.

    Raises
    ------
    ValueError
        If the code is not available in any data source or if the time
        zone in the data source does not match the expected time zone.
    """
    # Get the data sources for which the code is available.
    data_sources = _get_data_sources(code)

    # If the code is not available in any data source, raise an error.
    if not data_sources:
        raise ValueError(f"Code {code} is not available in any data source.")

    # Initialize a list of potential time zones from different data
    # sources.
    time_zones: list[datetime.tzinfo] = []

    # Iterate over the data sources and read the time zones.
    for data_source in data_sources:
        # Read the time zone from the file of the data source.
        data_source_time_zone = _get_time_zones(
            code=code, data_source=data_source
        )

        # Check if the time zone is a single datetime.tzinfo object.
        if isinstance(data_source_time_zone, datetime.tzinfo):
            time_zones.append(data_source_time_zone)

    # Remove duplicates from the list of time zones.
    time_zones = list(set(time_zones))

    if not time_zones:
        raise ValueError(
            f"The time zone is not defined for {code} in any data source."
        )
    elif len(time_zones) > 1:
        raise ValueError(
            f"Conflicting time zones found for {code}: "
            f"{', '.join(str(tz) for tz in time_zones)}."
        )

    return time_zones[0]


def read_date_ranges(
    file_path: str = "", data_source: str = ""
) -> dict[str, tuple[datetime.date, datetime.date]]:
    """
    Read the start and end dates of the available data.

    This function reads the start and end dates of the available data
    for the countries and subdivisions from a specified yaml file or
    from the yaml file of a specified data source. It extracts the
    start and end dates for each country or subdivision and returns a
    dictionary where the keys are the codes of the countries or
    subdivisions and the values are tuples containing the start and end
    dates.

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
    start_and_end_dates : dict[str, tuple[datetime.date, datetime.date]]
        The dictionary containing the start and end dates of the
        available data for the countries and subdivisions.

    Raises
    ------
    ValueError
        If the start date is after the end date for a country or
        subdivision, or if both file_path and data_source are provided,
        or if neither is provided.
    """
    # Extract the information of the countries and subdivisions.
    entities = _read_entities_info(
        file_path=file_path, data_source=data_source
    )

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
    # Get the path to all yaml files in the retrieval scripts folder.
    yaml_file_paths = utils.directories.list_yaml_files(
        "retrieval_scripts_folder"
    )

    # Define a dictionary to store the start and end dates of the
    # available data for the countries and subdivisions.
    start_and_end_dates: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Iterate over the yaml files and read the start and end dates from
    # each file.
    for yaml_file_path in yaml_file_paths:
        # Read the start and end dates from the file.
        file_start_and_end_dates = read_date_ranges(file_path=yaml_file_path)

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
    country or subdivision based on its ISO Alpha-2 code or a
    combination of the ISO Alpha-2 codes and the subdivision codes. It
    reads the start and end dates of the available data for the country
    or subdivision, converts them to the time zone of the country or
    subdivision, and returns a list of years for which data is
    available.

    Parameters
    ----------
    code : str
        The ISO Alpha-2 code of the country or the combination of the
        ISO Alpha-2 and the subdivision code.

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
    subdivision based on its ISO Alpha-2 code or a combination of the
    ISO Alpha-2 codes and the subdivision codes. It uses the
    pycountry_convert library to get the continent code from the ISO
    Alpha-2 code of the country.

    Parameters
    ----------
    code : str
        The ISO Alpha-2 code of the country or the combination of the
        ISO Alpha-2 and the subdivision code.

    Returns
    -------
    str
        The continent code of the country or subdivision.

    Raises
    ------
    ValueError
        If the provided code is not recognized or not available.
    """
    # Check if the code specifies a subdivision.
    if "_" in code:
        # Extract the ISO Alpha-2 code of the country.
        iso_alpha_2_code = code.split("_")[0]
    else:
        # If the code does not specify a subdivision, use the ISO
        # Alpha-2 code directly.
        iso_alpha_2_code = code

    # Get the continent code from the ISO Alpha-2 code.
    try:
        continent_code = pycountry_convert.country_alpha2_to_continent_code(
            iso_alpha_2_code
        )
    except KeyError:
        raise ValueError(
            f"Invalid or unknown ISO Alpha-2 code: {iso_alpha_2_code}"
        )

    return continent_code

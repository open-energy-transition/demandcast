"""
License: AGPL-3.0.

Description:

    This module reads the registry of the electricity demand data
    sources: the YAML file of each source, with its licence, the
    definition of its demand and its countries and subdivisions, with
    their time zones and the dates of their data.
"""

import datetime
import os
import zoneinfo
from collections.abc import Mapping
from typing import Any, Literal, Self

import pandas as pd
import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

import utils.paths


def get_code_of(entity: Mapping[str, Any]) -> str:
    """
    Get the code of a country or subdivision from its fields.

    Parameters
    ----------
    entity : Mapping[str, Any]
        The fields of the country or subdivision, as in a yaml file.

    Returns
    -------
    str
        The code of the country, or of the subdivision, which joins the
        codes of its country and of itself with an underscore.
    """
    if entity.get("subdivision_code") is None:
        return entity["country_code"]
    return f"{entity['country_code']}_{entity['subdivision_code']}"


class DataSourceEntity(BaseModel):
    """
    A country or subdivision in the yaml file of a data source.

    A subdivision has a name, a code and a time zone, and a country none
    of them. The data is available from the start date to the end date,
    which can be "today". The data covers the area of the shape of the
    code, unless same_area is false, as for a source that leaves out
    part of it.
    """

    model_config = ConfigDict(extra="forbid")

    country_name: str
    country_code: str
    subdivision_name: str | None = None
    subdivision_code: str | None = None
    time_zone: str | None = None
    start_date: datetime.date
    end_date: datetime.date | Literal["today"]
    same_area: bool = True

    @property
    def code(self) -> str:
        """The code of the country, or of the subdivision."""
        return get_code_of(self.model_dump())

    @model_validator(mode="after")
    def check_entity(self) -> Self:
        """
        Check the fields of the subdivision and the dates.

        Returns
        -------
        Self
            The entity.

        Raises
        ------
        ValueError
            If only some of the fields of a subdivision are given, if
            the time zone does not exist, or if the start date is after
            the end date.
        """
        subdivision_fields = [
            self.subdivision_name,
            self.subdivision_code,
            self.time_zone,
        ]
        if None in subdivision_fields and subdivision_fields != [None] * 3:
            raise ValueError(
                f"{self.code}: a subdivision needs a name, a code and a "
                "time zone, and a country none of them."
            )
        if self.time_zone is not None:
            try:
                zoneinfo.ZoneInfo(self.time_zone)
            except (zoneinfo.ZoneInfoNotFoundError, ValueError) as error:
                raise ValueError(
                    f"{self.code}: unknown time zone {self.time_zone}."
                ) from error
        if self.end_date != "today" and self.start_date > self.end_date:
            raise ValueError(
                f"{self.code}: the start date is after the end date."
            )
        return self


class DataSourceLicence(BaseModel):
    """
    The licence of the data of a data source.

    The terms summarise the licence, which is at the URL. The data is
    uploaded to Zenodo only if it can be redistributed.
    """

    model_config = ConfigDict(extra="forbid")

    redistribute: bool
    terms: str
    url: str


# What a part of the demand can be in the data of a data source:
# counted by the source, added by DemandCast, left out, or not known.
DefinitionValue = Literal["included", "added", "excluded", "unknown"]


class DataSourceDefinition(BaseModel):
    """
    What the demand of a data source counts, from a date.

    The demand that DemandCast models is the gross demand, which counts
    the demand that the generation embedded in the distribution networks
    supplies, such as rooftop solar. Each part says whether the source
    counts it (included), DemandCast adds an estimate of it (added), the
    demand leaves it out (excluded), or it is not known (unknown).
    """

    model_config = ConfigDict(extra="forbid")

    start_date: datetime.date
    quantity: str
    embedded_generation: DefinitionValue
    network_losses: DefinitionValue
    storage_charging: DefinitionValue
    power_plant_use: DefinitionValue
    note: str


class _DataSourceFile(BaseModel):
    """
    The content of the yaml file of a data source.

    A data source is compiled when it republishes the data of the system
    operators, such as the EIA, rather than its own.
    """

    model_config = ConfigDict(extra="forbid")

    licence: DataSourceLicence
    compiled: bool = False
    definition: list[DataSourceDefinition]
    entities: list[DataSourceEntity]

    @model_validator(mode="after")
    def check_definition(self) -> Self:
        """
        Check that the periods of the definition are in order.

        Returns
        -------
        Self
            The content of the file.

        Raises
        ------
        ValueError
            If the definition has no period, or its periods do not start
            in order.
        """
        dates = [period.start_date for period in self.definition]
        if not dates or dates != sorted(set(dates)):
            raise ValueError(
                "The definition needs periods with start dates in order, "
                f"not {dates}."
            )
        return self

    @model_validator(mode="after")
    def check_codes(self) -> Self:
        """
        Check that each country or subdivision comes once.

        Returns
        -------
        Self
            The content of the file.

        Raises
        ------
        ValueError
            If a code comes more than once.
        """
        codes = [entity.code for entity in self.entities]
        duplicates = sorted({code for code in codes if codes.count(code) > 1})
        if duplicates:
            raise ValueError(f"The codes {duplicates} come more than once.")
        return self


def read_data_sources() -> list[str]:
    """
    Read the names of the data sources.

    This function reads the names of the data sources from the yaml
    files in the folder containing the modules for electricity demand
    retrievals. The names are extracted from the file names.

    Returns
    -------
    data_sources : list[str]
        The list of available data sources.
    """
    # Get the path to folder containing the yaml files of the data
    # sources.
    data_sources_directory = utils.paths.DATA_SOURCES_FOLDER

    # Get the path of all yaml files in the specified folder.
    file_paths = [
        os.path.join(data_sources_directory, file)
        for file in os.listdir(data_sources_directory)
        if file.endswith(".yaml")
    ]

    # Read the data sources from the file names.
    data_sources = [
        os.path.basename(file_path).split(".")[0] for file_path in file_paths
    ]

    # Sort the data sources alphabetically.
    data_sources.sort()

    return data_sources


def _read_data_source_file(data_source: str) -> _DataSourceFile:
    """
    Read the yaml file of a data source, and check its content.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    _DataSourceFile
        The content of the file, checked and with its values converted,
        such as the dates written as text: the licence, the definition
        and the entities.

    Raises
    ------
    ValueError
        If the data source is not valid, or if its yaml file is not
        valid.
    """
    # Check if the data source is valid.
    if data_source not in read_data_sources():
        raise ValueError(
            f"Invalid data source: {data_source}. Available data "
            f"sources are: {', '.join(read_data_sources())}"
        )

    # Read the yaml file of the data source.
    file_path = os.path.join(
        utils.paths.DATA_SOURCES_FOLDER,
        f"{data_source.lower()}.yaml",
    )
    with open(file_path, encoding="utf-8") as file:
        content = yaml.safe_load(file)

    # Check its content.
    try:
        return _DataSourceFile.model_validate(content)
    except ValidationError as error:
        raise ValueError(
            f"The yaml file of the data source {data_source} is not "
            f"valid: {error}"
        ) from error


def read_entities(data_source: str) -> list[DataSourceEntity]:
    """
    Read the countries and subdivisions of a data source.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    list[DataSourceEntity]
        The countries and subdivisions, from the yaml file of the data
        source.
    """
    return _read_data_source_file(data_source).entities


def read_licence(data_source: str) -> DataSourceLicence:
    """
    Read the licence of the data of a data source.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    DataSourceLicence
        The licence, from the yaml file of the data source.
    """
    return _read_data_source_file(data_source).licence


def read_compiled(data_source: str) -> bool:
    """
    Read whether a data source republishes the data of other sources.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    bool
        Whether the data source is compiled, from its yaml file.
    """
    return _read_data_source_file(data_source).compiled


def read_definition(data_source: str) -> list[DataSourceDefinition]:
    """
    Read what the demand of a data source counts, period by period.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    list[DataSourceDefinition]
        The periods of the definition, from the yaml file of the data
        source, in the order of their start dates.
    """
    return _read_data_source_file(data_source).definition


def get_definition(
    data_source: str, date: datetime.date
) -> DataSourceDefinition:
    """
    Get what the demand of a data source counts on a date.

    Parameters
    ----------
    data_source : str
        The name of the data source.
    date : datetime.date
        The date.

    Returns
    -------
    DataSourceDefinition
        The period of the definition that the date is in, or the first
        one for a date before it.
    """
    periods = read_definition(data_source)
    started = [period for period in periods if period.start_date <= date]
    return started[-1] if started else periods[0]


def read_entities_info(
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
        folder, and check its content with `DataSourceEntity`.

    Returns
    -------
    list[dict[str, str | datetime.date]]
        The list of dictionaries containing the information for each
        country and subdivision.

    Raises
    ------
    ValueError
        If the data source is provided but not valid or its yaml file
        is not valid, or if both file_path and data_source are
        provided, or if neither is provided.
    """
    if file_path == "" and data_source != "":
        # Read and check the yaml file of the data source, with the
        # values converted and only the fields that it has.
        return [
            entity.model_dump(exclude_unset=True)
            for entity in _read_data_source_file(data_source).entities
        ]
    if file_path == "" and data_source == "":
        # If no file path or data source is provided, raise an error.
        raise ValueError("Either file_path or data_source must be provided.")
    if file_path != "" and data_source != "":
        # If both data source and data source file path are provided,
        # raise an error.
        raise ValueError(
            "Only one of file_path or data_source must be provided."
        )

    # Read the content from the file.
    with open(file_path, encoding="utf-8") as file:
        content = yaml.safe_load(file)

    # Return the information of the countries and subdivisions.
    return content["entities"]


def get_electricity_demand_data_sources_containing_code(
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
        entities = read_entities_info(data_source=data_source)

        # Iterate over the entities in the file.
        for entity in entities:
            # Extract the code of the country or subdivision.
            entity_code = get_code_of(entity)

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
    entities = read_entities_info(file_path=file_path, data_source=data_source)

    # Extract and return codes.
    return [get_code_of(entity) for entity in entities]


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
    entities = read_entities_info(data_source=data_source)

    # Define a dictionary to store the start and end dates of the
    # available data for the countries and subdivisions.
    start_and_end_dates: dict[str, tuple[datetime.date, datetime.date]] = {}

    # Iterate over the entities and extract the start and end dates.
    for entity in entities:
        # Extract the code of the country or subdivision.
        code = get_code_of(entity)

        # Extract the start and end dates of the available data.
        start_date = entity["start_date"]
        if entity["end_date"] == "today":
            # If the end date is "today", set it to a few days before
            # today to avoid issues with the latest data.
            end_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).date()
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

"""
License: AGPL-3.0.

Description:

    This module reads the registry of the electricity demand data
    sources: the YAML file of each source, with its licence, the
    definition of its demand and its countries and subdivisions, with
    their time zones and the dates of their data.
"""

import datetime as dt
import functools
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
        The fields of the country or subdivision, as in a YAML file.

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
    A country or subdivision in the YAML file of a data source.

    A subdivision has a name, a code and a time zone, and a country none
    of them. The data is available from the start date to the end date,
    which can be "today". The data covers the area of the shape of the
    code, unless same_area is false, as for a source that leaves out
    part of it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    country_name: str
    country_code: str
    subdivision_name: str | None = None
    subdivision_code: str | None = None
    time_zone: str | None = None
    start_date: dt.date
    end_date: dt.date | Literal["today"]
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

    The terms summarize the licence, which is at the URL, and
    redistribute says whether they allow the data to be redistributed.

    Notes
    -----
    DemandCast publishes only its forecasts and models, and keeps the
    retrieved data in a private bucket.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    redistribute: bool
    terms: str
    url: str


# What a part of the demand can be in the data of a data source:
# counted by the source, added by DemandCast, counted only in part,
# left out, or not known.
DefinitionValue = Literal[
    "included", "added", "partial", "excluded", "unknown"
]


class DataSourceDefinition(BaseModel):
    """
    What the demand of a data source counts, from a date.

    The demand that DemandCast models is the gross demand, which counts
    the demand that the generation embedded in the distribution networks
    supplies, such as rooftop solar. Each part says whether the source
    counts it (included), DemandCast adds an estimate of it (added), the
    source counts only part of it (partial), such as the rooftop solar
    fed into the networks without the solar that consumers use
    themselves, the demand leaves it out (excluded), or it is not known
    (unknown).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_date: dt.date
    quantity: str
    embedded_generation: DefinitionValue
    network_losses: DefinitionValue
    storage_charging: DefinitionValue
    power_plant_use: DefinitionValue
    note: str


class _DataSourceFile(BaseModel):
    """
    The content of the YAML file of a data source.

    A data source is compiled when it republishes the data of the system
    operators, such as the EIA, rather than its own. A compiled data
    source can also republish the data of other compiled data sources,
    which it lists in republishes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    licence: DataSourceLicence
    compiled: bool = False
    republishes: list[str] = []
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
        if self.republishes and not self.compiled:
            raise ValueError(
                "A data source that republishes other data sources is "
                "compiled."
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

    The names are those of the YAML files in the folder of the modules
    for electricity demand retrievals.

    Returns
    -------
    data_sources : list[str]
        The list of available data sources.
    """
    data_sources_directory = utils.paths.DATA_SOURCES_FOLDER

    file_paths = [
        os.path.join(data_sources_directory, file)
        for file in os.listdir(data_sources_directory)
        if file.endswith(".yaml")
    ]

    data_sources = [
        os.path.basename(file_path).split(".")[0] for file_path in file_paths
    ]
    data_sources.sort()

    return data_sources


def _read_data_source_file(data_source: str) -> _DataSourceFile:
    """
    Read the YAML file of a data source, and check its content.

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
        If the data source is not valid, or if its YAML file is not
        valid.
    """
    if data_source not in read_data_sources():
        raise ValueError(
            f"Invalid data source: {data_source}. Available data "
            f"sources are: {', '.join(read_data_sources())}"
        )

    file_path = os.path.join(
        utils.paths.DATA_SOURCES_FOLDER,
        f"{data_source.lower()}.yaml",
    )
    status = os.stat(file_path)
    return _parse_data_source_file(
        data_source, file_path, status.st_mtime_ns, status.st_size
    )


@functools.cache
def _parse_data_source_file(
    data_source: str,
    file_path: str,
    modified: int,  # noqa: ARG001
    size: int,  # noqa: ARG001
) -> _DataSourceFile:
    """
    Parse and check the YAML file of a data source.

    Parameters
    ----------
    data_source : str
        The name of the data source.
    file_path : str
        The path of its YAML file.
    modified : int
        The time of the last modification of the file, in nanoseconds,
        which only keys the kept content.
    size : int
        The size of the file, in bytes, which only keys the kept
        content.

    Returns
    -------
    _DataSourceFile
        The content of the file, checked.

    Raises
    ------
    ValueError
        If the YAML file is not valid.

    Notes
    -----
    The content is kept for each path, modification time and size, so
    that each file is parsed once, and again once it changes: most
    functions of the countries and subdivisions, such as their time
    zones, read all the files. Its models are frozen, and the functions
    that give its lists give copies of them, so that the kept content
    cannot be changed.
    """
    with open(file_path, encoding="utf-8") as file:
        content = yaml.safe_load(file)

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
        The countries and subdivisions, from the YAML file of the data
        source.
    """
    return list(_read_data_source_file(data_source).entities)


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
        The licence, from the YAML file of the data source.
    """
    return _read_data_source_file(data_source).licence


def read_compilation_level(data_source: str) -> int:
    """
    Read how far a data source is from the system operators.

    Parameters
    ----------
    data_source : str
        The name of the data source.

    Returns
    -------
    int
        0 for a data source that publishes its own data, 1 for one that
        republishes the data of the system operators (compiled in its
        YAML file), and one more than the highest level of the compiled
        data sources that it republishes (republishes in its YAML file).
    """
    content = _read_data_source_file(data_source)
    if not content.compiled:
        return 0
    return 1 + max(
        (read_compilation_level(source) for source in content.republishes),
        default=0,
    )


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
        The periods of the definition, from the YAML file of the data
        source, in the order of their start dates.
    """
    return list(_read_data_source_file(data_source).definition)


def get_definition(data_source: str, date: dt.date) -> DataSourceDefinition:
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

    Exactly one of the file path and the data source is given.

    Parameters
    ----------
    file_path : str, optional
        The path of a YAML file with the information of the countries
        and subdivisions, whose entities are read as they are.
    data_source : str, optional
        The name of the data source, whose YAML file in the folder of
        the data sources is read and checked with `DataSourceEntity`.

    Returns
    -------
    list[dict]
        The information of each country and subdivision.

    Raises
    ------
    ValueError
        If the data source is provided but not valid or its YAML file
        is not valid, or if both file_path and data_source are
        provided, or if neither is provided.
    """
    if file_path == "" and data_source != "":
        # Read and check the YAML file of the data source, with the
        # values converted and only the fields that it has.
        return [
            entity.model_dump(exclude_unset=True)
            for entity in _read_data_source_file(data_source).entities
        ]
    if file_path == "" and data_source == "":
        raise ValueError("Either file_path or data_source must be provided.")
    if file_path != "" and data_source != "":
        raise ValueError(
            "Only one of file_path or data_source must be provided."
        )

    with open(file_path, encoding="utf-8") as file:
        content = yaml.safe_load(file)

    return content["entities"]


def get_data_sources_of(
    code: str,
) -> list[str]:
    """
    Get the data sources containing the provided code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    data_sources : list[str]
        The list of data sources that contain the provided code.
    """
    data_sources = read_data_sources()

    data_sources_containing_code = []
    for data_source in data_sources:
        entities = read_entities_info(data_source=data_source)
        for entity in entities:
            entity_code = get_code_of(entity)
            if entity_code == code:
                data_sources_containing_code.append(data_source)

    return data_sources_containing_code


def read_codes_in(file_path: str = "", data_source: str = "") -> list[str]:
    """
    Read the codes of the countries and subdivisions.

    Parameters
    ----------
    file_path : str, optional
        The path of a YAML file with the information of the countries
        and subdivisions.
    data_source : str, optional
        The name of the data source, whose YAML file in the folder of
        the data sources is read.

    Returns
    -------
    list[str]
        The ISO Alpha-3 codes of the countries, or the combinations of
        the ISO Alpha-3 code and the subdivision code of the
        subdivisions.
    """
    entities = read_entities_info(file_path=file_path, data_source=data_source)

    return [get_code_of(entity) for entity in entities]


def read_all_codes() -> list[str]:
    """
    Read the codes of all countries and subdivisions with demand data.

    The codes of all the data sources are combined, without
    duplicates.

    Returns
    -------
    list[str]
        A list of codes of all countries and subdivisions for which
        high-resolution electricity demand data is available, sorted.

    Notes
    -----
    The codes are sorted alphabetically, so that they are processed in
    the same order in every run.
    """
    data_sources = read_data_sources()

    codes = []
    for data_source in data_sources:
        file_codes = read_codes_in(data_source=data_source)
        codes.extend(file_codes)

    return sorted(set(codes))


def read_date_ranges(
    data_source: str,
) -> dict[str, tuple[dt.date, dt.date]]:
    """
    Read the start and end dates of the available data.

    The dates are read from the YAML file of the data source.

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

    Notes
    -----
    An end date of "today" is taken as five days before today, to avoid
    issues with the latest data.
    """
    entities = read_entities_info(data_source=data_source)

    start_and_end_dates: dict[str, tuple[dt.date, dt.date]] = {}
    for entity in entities:
        code = get_code_of(entity)

        start_date = entity["start_date"]
        if entity["end_date"] == "today":
            end_date = (pd.Timestamp.now() - pd.Timedelta(days=5)).date()
        else:
            end_date = entity["end_date"]

        start_and_end_dates[code] = (start_date, end_date)

        if start_date > end_date:
            raise ValueError(
                f"The start date {start_date} is after the end date "
                f"{end_date} for {code}."
            )

    return start_and_end_dates


def read_all_periods() -> dict[str, list[tuple[dt.date, dt.date]]]:
    """
    Read the periods of the available data of each code.

    Returns
    -------
    dict[str, list[tuple[datetime.date, datetime.date]]]
        The first and last days of each period of the data of each
        country or subdivision, in order: the union of the periods of
        its data sources, with the periods that overlap or follow each
        other merged.
    """
    date_ranges: dict[str, list[tuple[dt.date, dt.date]]] = {}
    for data_source in read_data_sources():
        for (
            code,
            date_range,
        ) in read_date_ranges(data_source).items():
            date_ranges.setdefault(code, []).append(date_range)

    periods: dict[str, list[tuple[dt.date, dt.date]]] = {}
    for code, ranges in date_ranges.items():
        merged: list[tuple[dt.date, dt.date]] = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1][1] + dt.timedelta(days=1):
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        periods[code] = merged
    return periods

"""
License: AGPL-3.0.

Description:

    This module gives the paths of the folders and files that
    DemandCast reads and writes.

    The inputs that come with the code stay in the code folder: the
    configuration files, the shapes, the descriptions of the data
    sources, the reviews of the flags and the summary of the data
    availability.

    Everything that the scripts write is in the data folder, which is
    the "data" folder in the code folder, unless the environment
    variable DEMANDCAST_DATA_FOLDER names another one. Each dataset
    has its own folder, with its stages:

        data/
        ├── electricity_demand/
        │   ├── raw/                 responses and manifests, by source
        │   │   └── manual_downloads/  files downloaded by hand
        │   ├── processed/, cleaned/, combined/
        ├── gridded_weather/, gridded_population/, gridded_gdp_ppp/
        │   ├── raw/                 global grids, as downloaded
        │   └── processed/           grids of each country and
        │                            subdivision
        ├── temperature/, population/, gdp_ppp_per_capita/,
        │   annual_electricity_demand_per_capita/
        ├── assembled/
        ├── models/<algorithm>/
        ├── results/
        │   ├── validation/, cross_validation/, forecasts/
        │   ├── figures/
        │   └── checks/              reports of the checks
        └── logs/

    The gridded weather of a few countries is downloaded for each of
    them, straight into its processed folder.
"""

import os
from typing import Literal

# The folder of the code, with the inputs that come with it.
CODE_FOLDER = os.path.normpath(
    os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
)
CONFIG_FOLDER = os.path.join(CODE_FOLDER, "config")
SHAPES_FOLDER = os.path.join(CODE_FOLDER, "shapes")
RETRIEVALS_FOLDER = os.path.join(CODE_FOLDER, "retrievals")
DATA_SOURCES_FOLDER = os.path.join(
    RETRIEVALS_FOLDER, "electricity_demand_data_sources"
)
CHECKS_FOLDER = os.path.join(CODE_FOLDER, "checks")
ENV_FILE = os.path.join(CODE_FOLDER, ".env")

# The environment variable that names another data folder.
DATA_FOLDER_VARIABLE = "DEMANDCAST_DATA_FOLDER"

type ElectricityDemandStage = Literal[
    "raw", "manual_downloads", "processed", "cleaned", "combined"
]
type GriddedVariable = Literal["weather", "population", "gdp_ppp"]
type Indicator = Literal[
    "temperature",
    "population",
    "gdp_ppp_per_capita",
    "annual_electricity_demand_per_capita",
]
type ResultKind = Literal[
    "validation", "cross_validation", "forecasts", "figures", "checks"
]


def get_config_file(name: str) -> str:
    """
    Get the path of a configuration file.

    Parameters
    ----------
    name : str
        The name of the file, with its extension.

    Returns
    -------
    str
        The path of the file in the configuration folder.
    """
    return os.path.join(CONFIG_FOLDER, name)


def get_data_folder(*parts: str) -> str:
    """
    Get the data folder, or a folder or file in it.

    Parameters
    ----------
    *parts : str
        The names of the folders and of the file in the data folder.

    Returns
    -------
    str
        The path, under DEMANDCAST_DATA_FOLDER if it is set, and under
        the "data" folder of the code otherwise.
    """
    data_folder = os.environ.get(DATA_FOLDER_VARIABLE) or os.path.join(
        CODE_FOLDER, "data"
    )
    return os.path.join(os.path.abspath(data_folder), *parts)


def get_electricity_demand_folder(stage: ElectricityDemandStage) -> str:
    """
    Get the folder of a stage of the electricity demand.

    Parameters
    ----------
    stage : ElectricityDemandStage
        The stage: "raw", "manual_downloads" (in the raw folder),
        "processed", "cleaned" or "combined".

    Returns
    -------
    str
        The folder.
    """
    if stage == "manual_downloads":
        return get_data_folder("electricity_demand", "raw", stage)
    return get_data_folder("electricity_demand", stage)


def get_electricity_demand_file(
    stage: Literal["processed", "cleaned", "combined"],
    code: str,
    data_source: str | None = None,
) -> str:
    """
    Get the path of the file of the electricity demand of a stage.

    Parameters
    ----------
    stage : str
        The stage of the data, "processed", "cleaned" or "combined".
    code : str
        The code of the country or subdivision.
    data_source : str | None, optional
        The data source, none for the combined data of all of them.

    Returns
    -------
    str
        The path of the parquet file, named after the code and the data
        source, in the folder of the stage.
    """
    name = code if data_source is None else f"{code}_{data_source}"
    return os.path.join(
        get_electricity_demand_folder(stage), f"{name}.parquet"
    )


def get_gridded_folder(
    variable: GriddedVariable, stage: Literal["raw", "processed"]
) -> str:
    """
    Get the folder of a stage of a gridded variable.

    Parameters
    ----------
    variable : GriddedVariable
        The variable: "weather", "population" or "gdp_ppp".
    stage : str
        "raw" for the global grids as downloaded, "processed" for the
        grids of each country and subdivision.

    Returns
    -------
    str
        The folder.
    """
    return get_data_folder(f"gridded_{variable}", stage)


def get_indicator_folder(indicator: Indicator) -> str:
    """
    Get the folder of the time series of an indicator.

    Parameters
    ----------
    indicator : Indicator
        The indicator: "temperature", "population",
        "gdp_ppp_per_capita" or "annual_electricity_demand_per_capita".

    Returns
    -------
    str
        The folder, with one file for each country or subdivision.
    """
    return get_data_folder(indicator)


def get_assembled_folder() -> str:
    """
    Get the folder of the assembled data.

    Returns
    -------
    str
        The folder.
    """
    return get_data_folder("assembled")


def get_models_folder(algorithm: str) -> str:
    """
    Get the folder of the trained models of an algorithm.

    Parameters
    ----------
    algorithm : str
        The name of the algorithm, in lower case, such as "xgboost".

    Returns
    -------
    str
        The folder.
    """
    return get_data_folder("models", algorithm)


def get_results_folder(kind: ResultKind) -> str:
    """
    Get the folder of a kind of results.

    Parameters
    ----------
    kind : ResultKind
        The kind: "validation", "cross_validation", "forecasts",
        "figures" or "checks".

    Returns
    -------
    str
        The folder.
    """
    return get_data_folder("results", kind)


def get_logs_folder() -> str:
    """
    Get the folder of the log files.

    Returns
    -------
    str
        The folder.
    """
    return get_data_folder("logs")

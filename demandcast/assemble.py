"""
License: AGPL-3.0.

Description:

    This script assembles and preprocesses the retrieved data for
    training the machine learning models or forecasting.

    Each row is an hour of an entity, at its end in UTC, with the mean
    electricity demand of the hour, the mean temperature of the hour,
    the calendar of its start in local time and the annual values of
    the local year of its start (see retrievals/temperature.py and
    utils.time_series.convert_from_yearly_to_hourly). The datasets are
    merged on the hours and the entities, keeping only the hours that
    all of them have.

    The target of the training, the fraction of the annual total, is
    estimated from the hours of each year with data, which must then
    represent the year: the training keeps only the years with at least
    90% of their hours and half of the hours of each month, and lists
    the coverage of all the years next to the assembled data.
"""

import dataclasses
import datetime
import functools
import glob
import hashlib
import logging
import os
from collections.abc import Callable
from functools import reduce
from typing import Literal

import dask
import dask.dataframe
import numpy as np
import pandas as pd
from pydantic import model_validator
from tqdm import tqdm

import cleaning.combining
import utils.availability
import utils.catalogue
import utils.config
import utils.manifest
import utils.paths
import utils.public_holidays

# The shares of the hours of a year, and of each of its months, that
# the training needs.
MIN_YEAR_COVERAGE = 0.9
MIN_MONTH_COVERAGE = 0.5


@dataclasses.dataclass(frozen=True)
class Dataset:
    """
    An input of the assembly.

    Attributes
    ----------
    name : str
        The name of the input, which names its settings,
        scenario_for_<name> and climate_model_for_<name>.
    description : str
        The name of the input in the messages of the log.
    get_folder : Callable[[], str]
        The function that gives the folder of its files.
    columns : tuple[str, ...]
        Its columns, which must be positive numbers.
    scenarios : tuple[str, ...] | None, optional
        Its scenarios, from utils/catalogue.py, none if it has none or
        if they depend on the climate model.
    climate : bool, optional
        Whether it comes from the climate models, whose scenarios
        depend on the model.
    by_year : bool, optional
        Whether it has one file per local year, <code>_<year>, with the
        column "Local year", which selects the years to assemble.
    training_only : bool, optional
        Whether it is assembled only for training, as the target.
    """

    name: str
    description: str
    get_folder: Callable[[], str]
    columns: tuple[str, ...]
    scenarios: tuple[str, ...] | None = None
    climate: bool = False
    by_year: bool = False
    training_only: bool = False


# The inputs of the assembly, in the order of their columns.
DATASETS = (
    Dataset(
        "annual_electricity_demand_per_capita",
        "annual electricity demand per capita",
        functools.partial(
            utils.paths.get_indicator_folder,
            "annual_electricity_demand_per_capita",
        ),
        ("Annual electricity demand per capita (kWh)",),
        scenarios=utils.catalogue.IAMC_SCENARIOS,
    ),
    Dataset(
        "gdp_ppp_per_capita",
        "GDP PPP per capita",
        functools.partial(
            utils.paths.get_indicator_folder, "gdp_ppp_per_capita"
        ),
        ("GDP PPP per capita (2021 international $)",),
        scenarios=utils.catalogue.SSP_SCENARIOS,
    ),
    Dataset(
        "population",
        "population",
        functools.partial(utils.paths.get_indicator_folder, "population"),
        ("Population",),
        scenarios=utils.catalogue.SSP_SCENARIOS,
    ),
    Dataset(
        "temperature",
        "temperature",
        functools.partial(utils.paths.get_indicator_folder, "temperature"),
        (
            "Temperature - Top 1 (K)",
            "Temperature - Top 3 (K)",
            "Monthly average temperature - Top 1 (K)",
            "Monthly average temperature rank - Top 1",
            "Annual average temperature - Top 1 (K)",
            "5 percentile temperature - Top 1 (K)",
            "95 percentile temperature - Top 1 (K)",
        ),
        climate=True,
        by_year=True,
    ),
    # The hourly demand that combines all the data sources of each code
    # (see cleaning/combining.py).
    Dataset(
        "electricity_demand",
        "electricity demand",
        functools.partial(
            utils.paths.get_electricity_demand_folder, "combined"
        ),
        ("Load (MW)",),
        training_only=True,
    ),
)


class ConfigModel(utils.config.StrictSettings):
    """Settings of assemble.py."""

    target_use: Literal["training", "forecasting"]
    file: str | None = None
    start_year: int | None = None
    end_year: int | None = None
    scenario_for_annual_electricity_demand_per_capita: str | None = None
    scenario_for_gdp_ppp_per_capita: str | None = None
    scenario_for_population: str | None = None
    scenario_for_temperature: str | None = None
    climate_model_for_temperature: str | None = None

    @model_validator(mode="after")
    def _check_scenarios(self) -> "ConfigModel":
        """
        Check the scenarios and the climate model.

        They are spelt as in the catalogue, whatever their case.

        Returns
        -------
        ConfigModel
            The settings.
        """
        for dataset in DATASETS:
            if dataset.scenarios is None and not dataset.climate:
                continue
            model_field = f"climate_model_for_{dataset.name}"
            scenario_field = f"scenario_for_{dataset.name}"
            model, scenario = _get_scenario_and_model(
                getattr(self, model_field, None),
                getattr(self, scenario_field),
                dataset.scenarios,
                dataset.climate,
            )
            if dataset.climate:
                setattr(self, model_field, model)
            setattr(self, scenario_field, scenario)
        return self


def _get_scenario_and_model(
    selected_model: str | None,
    selected_scenario: str | None,
    scenarios: tuple[str, ...] | None,
    climate: bool,
) -> tuple[str | None, str | None]:
    """
    Check the selected climate model and scenario of a variable.

    Parameters
    ----------
    selected_model : str | None
        The selected climate model.
    selected_scenario : str | None
        The selected scenario.
    scenarios : tuple[str, ...] | None
        The scenarios of the variable, from utils/catalogue.py, None to
        leave the scenario unchecked.
    climate : bool
        Whether the variable comes from the climate models, whose
        scenarios depend on the model.

    Returns
    -------
    tuple[str | None, str | None]
        The climate model and the scenario, spelt as in the catalogue.
    """
    if climate:
        return utils.catalogue.get_climate_model_and_scenario(
            selected_model, selected_scenario
        )
    if scenarios is not None and selected_scenario:
        selected_scenario = utils.catalogue.get_scenario(
            selected_scenario, scenarios
        )
    return selected_model, selected_scenario


def _get_file_paths(
    dataset: Dataset,
    entity_code: str,
    selected_scenario: str | None,
    selected_model: str | None,
) -> list[str]:
    """
    Get the files of an input of a country or subdivision.

    The names have the climate model and the scenario, if any, in upper
    case with underscores for hyphens and dots, as the retrievals write
    them.

    Parameters
    ----------
    dataset : Dataset
        The input.
    entity_code : str
        The code of the country or subdivision.
    selected_scenario : str | None
        The scenario, none for historical data.
    selected_model : str | None
        The climate model, none for historical data.

    Returns
    -------
    list[str]
        The file of the input, or its files of each local year.
    """
    name = entity_code + ("_" + "[0-9]" * 4 if dataset.by_year else "")
    for part in (selected_model, selected_scenario):
        if part:
            name += "_" + part.upper().replace("-", "_").replace(".", "_")
    file_path = os.path.join(dataset.get_folder(), f"{name}.parquet")
    if not dataset.by_year:
        return [file_path]

    file_paths = sorted(glob.glob(file_path))
    if not file_paths:
        logging.warning(
            f"No {dataset.description} files found for entity code "
            f"{entity_code}"
            + (f" with model {selected_model}" if selected_model else "")
            + (
                f" and scenario {selected_scenario}"
                if selected_scenario
                else ""
            )
            + "."
        )
    return file_paths


def _load_data_for_entity(
    entity_code: str,
    file_paths: list[str],
    numeric_columns: list[str],
) -> dask.dataframe.DataFrame | None:
    """
    Load and process data for a specific entity code.

    Parameters
    ----------
    entity_code : str
        Entity code to load data for.
    file_paths : list[str]
        List of file paths to load data from.
    numeric_columns : list[str]
        List of columns to convert to numeric.

    Returns
    -------
    entity_data : dask.dataframe.DataFrame | None
        Dataframe with processed data for the entity code, or None if
        no data was loaded.

    Raises
    ------
    ValueError
        If the electricity demand does not say which hours can be used
        for training.
    """
    # Initialize a list to hold the data for the entity.
    entity_frames: list[pd.DataFrame] = []

    for file_path in file_paths:
        if not os.path.exists(file_path):
            logging.warning(
                f"File {file_path} not found for entity code {entity_code}. "
                "Skipping."
            )
            continue

        # Read the current parquet file, without the hours of the
        # electricity demand that cannot be used for training, such as
        # those of the errors of a data source. The demand must say
        # which hours can be used.
        current_data = pd.read_parquet(file_path)
        if "Load (MW)" in numeric_columns and "Eligible" not in current_data:
            raise ValueError(
                f"The electricity demand of {entity_code} in {file_path} "
                "does not say which hours can be used for training: "
                "combine it again (see cleaning/combining.py)."
            )
        if "Eligible" in current_data:
            excluded = int((~current_data["Eligible"]).sum())
            if excluded:
                logging.info(
                    f"{excluded} hours of the electricity demand of "
                    f"{entity_code} cannot be used for training and are "
                    "left out."
                )
            current_data = current_data[current_data["Eligible"]].drop(
                columns="Eligible"
            )

        # Append to the entity dataframe.
        entity_frames.append(current_data)

    if entity_frames:
        # Concatenate all data for the entity, without the columns of
        # text, such as the data source of each hour of the electricity
        # demand, which cannot be averaged.
        entity_data = pd.concat(entity_frames)
        entity_data = entity_data.drop(
            columns=entity_data.columns.difference(
                entity_data.select_dtypes("number").columns
            )
        )
    else:
        # If no data was loaded, return None.
        return None

    # Ensure specified columns are numeric.
    for column in numeric_columns:
        entity_data[column] = pd.to_numeric(
            entity_data[column], errors="coerce"
        )

    # Drop NaN values that may have resulted from coercion.
    entity_data = entity_data.dropna()

    # Resample to hourly frequency by taking the mean. It is needed to
    # do it on all variables to ensure consistent timestamps. For
    # instance, some entities may have timestamps at the half hour due
    # to the timezone conversion.
    entity_data = entity_data.resample(
        "1h", label="right", closed="right"
    ).mean()

    # Drop any rows with NaN values after resampling.
    entity_data = entity_data.dropna()

    # Use the same time resolution for all datasets. Since pandas 3,
    # the resolution is inferred (e.g., microseconds for parsed strings
    # and nanoseconds for weather data), and merging datasets with
    # different resolutions silently drops rows.
    entity_data.index = pd.DatetimeIndex(entity_data.index).as_unit("ns")

    # Keep only rows with positive values in the specified numeric
    # columns.
    for column in numeric_columns:
        entity_data = entity_data[entity_data[column] > 0]

    # Add a column for the entity code.
    entity_data["Entity code"] = entity_code
    entity_data = entity_data.reset_index()

    return dask.dataframe.from_pandas(entity_data)


def _load_dataset(
    dataset: Dataset,
    target_use: str,
    selected_scenario: str | None = None,
    selected_model: str | None = None,
    file_path: str | None = None,
    read_files: list[str] | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load an input of all the countries and subdivisions.

    Parameters
    ----------
    dataset : Dataset
        The input.
    target_use : str
        The target use, "training" or "forecasting": the training needs
        the codes with electricity demand data, the forecasting those
        with all the other data.
    selected_scenario : str | None, optional
        The scenario, none for historical data.
    selected_model : str | None, optional
        The climate model, none for historical data.
    file_path : str | None, optional
        The file with the codes to load, all of them if none.
    read_files : list[str] | None, optional
        A list to which the paths of the files read are added.

    Returns
    -------
    dask.dataframe.DataFrame
        The data of all the codes, with the columns "Time (UTC)", those
        of the input and "Entity code".
    """
    logging.info(f"Loading {dataset.description} data.")

    entity_codes = utils.availability.check_and_get_codes_with(
        "electricity_demand_data" if target_use == "training" else "all_data",
        file_path=file_path,
    )
    selected_model, selected_scenario = _get_scenario_and_model(
        selected_model, selected_scenario, dataset.scenarios, dataset.climate
    )

    result_data = []
    for entity_code in tqdm(
        entity_codes, desc=f"Loading {dataset.description} data"
    ):
        # The combined demand must follow the current reviews and data
        # sources, so that its eligibility for training is current.
        if dataset.name == "electricity_demand":
            cleaning.combining.ensure_current_combination(entity_code)
        entity_file_paths = _get_file_paths(
            dataset, entity_code, selected_scenario, selected_model
        )
        entity_data = _load_data_for_entity(
            entity_code, entity_file_paths, list(dataset.columns)
        )
        if read_files is not None:
            read_files.extend(
                path for path in entity_file_paths if os.path.exists(path)
            )
        if entity_data is not None:
            result_data.append(entity_data)

    combined_data = dask.dataframe.concat(result_data)
    logging.info(
        f"Loaded {dataset.description} data for "
        f"{len(combined_data['Entity code'].unique())} entities "
        "successfully."
    )
    return combined_data


def _get_inputs_identity(file_paths: list[str]) -> dict[str, int | str]:
    """
    Get the identity of the files of an input of the assembly.

    Parameters
    ----------
    file_paths : list[str]
        The paths of the files read.

    Returns
    -------
    dict[str, int | str]
        The number of files ("files"), and the SHA-256 checksum of their
        paths relative to the data folder and of their checksums, in the
        order of the paths ("sha256"), which changes if any of them
        does.
    """
    checksum = hashlib.sha256()
    references = sorted(
        (utils.manifest.get_data_reference(path), path) for path in file_paths
    )
    for reference, path in references:
        checksum.update(
            f"{reference} {utils.manifest.get_checksum(path)}\n".encode()
        )
    return {"files": len(references), "sha256": checksum.hexdigest()}


def _merge_datasets(
    datasets: list[dask.dataframe.DataFrame], on: list[str]
) -> pd.DataFrame:
    """
    Merge multiple datasets on specified columns, and compute the merge.

    Parameters
    ----------
    datasets : list[dask.dataframe.DataFrame]
        List of dataframes to merge.
    on : list[str]
        The columns to merge on.

    Returns
    -------
    merged_dataset : pandas.DataFrame
        Merged dataset.
    """
    logging.info(f"Merging {len(datasets)} datasets.")

    # Merge all datasets on the specified columns.
    merged_dataset = reduce(
        lambda left, right: dask.dataframe.merge(
            left, right, on=on, how="inner"
        ),
        datasets,
    )

    # Compute the merge and the entities of each dataset at once: each
    # statistic of the lazy merge would compute it again.
    computed_dataset, *entities = dask.compute(
        merged_dataset,
        *(dataset["Entity code"].unique() for dataset in datasets),
    )
    merged_entities = set(computed_dataset["Entity code"])

    logging.info(f"Merged {len(datasets)} datasets successfully.")
    logging.info(
        f"Merged dataset contains {len(computed_dataset)} rows, "
        f"{len(computed_dataset.columns)} columns, and "
        f"{len(merged_entities)} entities."
    )
    logging.info("Excluded entities during merging:")
    for i, dataset_entities in enumerate(entities):
        excluded_entities = set(dataset_entities) - merged_entities
        logging.info(f" - Dataset {i + 1}: {excluded_entities or 'None'}")

    return computed_dataset


def _select_complete_years(
    merged_dataset: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Keep the years of each entity with enough of their hours.

    The fraction of the annual total of an hour assumes that the hours
    of its year with data represent the whole year: a year without its
    winter or its summer would have the wrong annual total.

    Parameters
    ----------
    merged_dataset : pandas.DataFrame
        The merged dataset, with the entity code, the local year and the
        local month of the year of each hour.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame]
        The rows of the years with at least MIN_YEAR_COVERAGE of their
        hours and MIN_MONTH_COVERAGE of the hours of each month, and the
        coverage of each year of each entity: its hours ("Hours"), their
        share of the year ("Year coverage") and the lowest share of the
        hours of a month ("Lowest month coverage"), and whether it is
        kept ("Kept").
    """
    keys = ["Entity code", "Local year"]
    hours_by_month = merged_dataset.pivot_table(
        index=keys,
        columns="Local month of the year",
        aggfunc="size",
        fill_value=0,
    ).reindex(columns=range(1, 13), fill_value=0)
    hours_in_months = pd.DataFrame(
        [
            [
                pd.Timestamp(int(year), month, 1).days_in_month * 24
                for month in range(1, 13)
            ]
            for year in hours_by_month.index.get_level_values("Local year")
        ],
        index=hours_by_month.index,
        columns=hours_by_month.columns,
    )
    coverage = pd.DataFrame(
        {
            "Hours": hours_by_month.sum(axis=1),
            "Year coverage": hours_by_month.sum(axis=1)
            / hours_in_months.sum(axis=1),
            "Lowest month coverage": (hours_by_month / hours_in_months).min(
                axis=1
            ),
        }
    )
    coverage["Kept"] = (coverage["Year coverage"] >= MIN_YEAR_COVERAGE) & (
        coverage["Lowest month coverage"] >= MIN_MONTH_COVERAGE
    )

    excluded = coverage.index[~coverage["Kept"]]
    logging.info(
        f"Excluded {len(excluded)} of {len(coverage)} years of the "
        "entities with too few hours: "
        + (", ".join(f"{code} {year}" for code, year in excluded) or "none")
        + "."
    )
    kept = pd.MultiIndex.from_frame(merged_dataset[keys]).isin(
        coverage.index[coverage["Kept"]]
    )
    return merged_dataset[kept], coverage.reset_index()


def _calculate_load_fraction(merged_dataset: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the fraction of load at each timestamp.

    The load fraction is calculated as the load at each timestamp
    divided by the total annual load for the corresponding entity and
    year, adjusted for the amount of hours tracked in the dataset. The
    function assumes that time is in hourly frequency. Changes should be
    made if a different frequency is used.

    Parameters
    ----------
    merged_dataset : pandas.DataFrame
        Input dataframe with load, entity code, and local year columns.

    Returns
    -------
    merged_dataset : pandas.DataFrame
        Dataframe with load fraction column added.
    """
    logging.info("Calculating load fraction for each timestamp.")

    # Compute the total annual load and the amount of hours tracked in
    # the dataset for each entity and year.
    groups = merged_dataset.groupby(["Entity code", "Local year"])["Load (MW)"]
    annual_load = groups.transform("sum")
    amount_of_hours_tracked = groups.transform("count")

    # Calculate the amount of hours in each year.
    years = merged_dataset["Local year"]
    is_leap_year = (years % 4 == 0) & ((years % 100 != 0) | (years % 400 == 0))
    amount_of_hours_in_year = np.where(is_leap_year, 8784, 8760)

    # Calculate the load fraction.
    merged_dataset["Load (fraction of annual total)"] = (
        merged_dataset["Load (MW)"]
        * amount_of_hours_tracked
        / (amount_of_hours_in_year * annual_load)
    )

    logging.info("Load fraction calculated successfully.")

    return merged_dataset


def run_data_assemply(
    target_use: str,
    file: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    scenario_for_annual_electricity_demand_per_capita: str | None = None,
    scenario_for_gdp_ppp_per_capita: str | None = None,
    scenario_for_population: str | None = None,
    scenario_for_temperature: str | None = None,
    climate_model_for_temperature: str | None = None,
) -> None:
    """
    Preprocess raw data and save the assembled dataset.

    Parameters
    ----------
    target_use : str
        Target use for which the data is being assembled. It can be
        'training' or 'forecasting'.
    file : str | None, optional
        Optional file path including entity codes to load. If None,
        load all available codes.
    start_year : int | None, optional
        Start year for filtering the assembled data. If None, no
        filtering is applied.
    end_year : int | None, optional
        End year for filtering the assembled data. If None, no
        filtering is applied.
    scenario_for_annual_electricity_demand_per_capita : str | None,
        optional
        Scenario to load for annual electricity demand per capita. None
        for historical data.
    scenario_for_gdp_ppp_per_capita : str | None, optional
        Scenario to load for GDP PPP per capita. None for historical
        data.
    scenario_for_population : str | None, optional
        Scenario to load for population. None for historical data.
    scenario_for_temperature : str | None, optional
        Scenario to load for temperature. None for historical data.
    climate_model_for_temperature : str | None, optional
        Climate model to load for temperature. None for historical data.

    Raises
    ------
    ValueError
        If target_use is not 'training' or 'forecasting' or if only one
        of start_year or end_year is provided.
    """
    # Check that the inputs are valid.
    if target_use not in ["training", "forecasting"]:
        raise ValueError(
            "target_use must be either 'training' or 'forecasting'"
        )
    if (start_year and not end_year) or (end_year and not start_year):
        raise ValueError(
            "Both start_year and end_year must be provided to filter "
            "by year range."
        )

    logging.info(f"Starting data assembly for {target_use}.")

    # The selected scenarios and climate models of the inputs.
    selected_scenarios = {
        "annual_electricity_demand_per_capita": (
            scenario_for_annual_electricity_demand_per_capita
        ),
        "gdp_ppp_per_capita": scenario_for_gdp_ppp_per_capita,
        "population": scenario_for_population,
        "temperature": scenario_for_temperature,
    }
    selected_models = {"temperature": climate_model_for_temperature}

    datasets_to_merge = []
    read_files: dict[str, list[str]] = {}
    for dataset in DATASETS:
        if dataset.training_only and target_use != "training":
            continue
        read_files[dataset.name] = []
        data = _load_dataset(
            dataset,
            target_use,
            selected_scenarios.get(dataset.name),
            selected_models.get(dataset.name),
            file,
            read_files[dataset.name],
        )
        if dataset.by_year and start_year and end_year:
            # Keep the specified year range, before the merges: the
            # other inputs have no local year, and the merges keep only
            # the rows of all the inputs.
            data = data[
                (data["Local year"] >= start_year)
                & (data["Local year"] <= end_year)
            ]
        datasets_to_merge.append(data)

    # Merge datasets on common columns.
    assembled_data = _merge_datasets(
        datasets_to_merge,
        ["Time (UTC)", "Entity code"],
    )

    # Tell which hours are on a public holiday of their country or
    # subdivision, which the other calendar features cannot see.
    assembled_data["Local holiday indicator"] = 0
    for entity_code, rows in assembled_data.groupby(
        "Entity code"
    ).groups.items():
        assembled_data.loc[rows, "Local holiday indicator"] = (
            utils.public_holidays.get_holiday_indicator(
                assembled_data.loc[rows, "Time (UTC)"], str(entity_code)
            )
        )

    coverage = None
    if target_use == "training":
        # Keep the years with enough hours, and calculate the load
        # fraction for training data.
        assembled_data, coverage = _select_complete_years(assembled_data)
        assembled_data = _calculate_load_fraction(assembled_data)

    # Get the assembled data folder path.
    assembled_data_folder = utils.paths.get_assembled_folder()
    os.makedirs(assembled_data_folder, exist_ok=True)

    # Construct the output file path.
    output_path = os.path.join(
        assembled_data_folder,
        f"assembled_data_for_{target_use}_"
        f"{datetime.datetime.now().astimezone():%Y%m%d_%H%M%S}",
    )

    # Sort the dataset in the order of the entities and of the times,
    # since the windows of the LSTM need consecutive hours. Save it to
    # CSV and Parquet formats.
    assembled_data = assembled_data.sort_values(
        ["Entity code", "Time (UTC)"], ignore_index=True
    )
    assembled_data.to_csv(output_path + ".csv", index=False)
    assembled_data.to_parquet(output_path + ".parquet", index=False)
    if coverage is not None:
        coverage.to_csv(output_path + "_coverage.csv", index=False)

    # Tell what the dataset is for and how it was assembled.
    utils.manifest.write_manifest(
        output_path + ".parquet",
        "dataset",
        {
            "purpose": target_use,
            "settings": {
                "file": file,
                "start_year": start_year,
                "end_year": end_year,
                "scenario_for_annual_electricity_demand_per_capita": (
                    scenario_for_annual_electricity_demand_per_capita
                ),
                "scenario_for_gdp_ppp_per_capita": (
                    scenario_for_gdp_ppp_per_capita
                ),
                "scenario_for_population": scenario_for_population,
                "scenario_for_temperature": scenario_for_temperature,
                "climate_model_for_temperature": (
                    climate_model_for_temperature
                ),
            },
            "columns": {
                str(column): str(dtype)
                for column, dtype in assembled_data.dtypes.items()
            },
            "rows": len(assembled_data),
            "entities": sorted(assembled_data["Entity code"].unique()),
            "inputs": {
                name: _get_inputs_identity(file_paths)
                for name, file_paths in read_files.items()
            },
        },
    )

    logging.info(
        f"Assembled data saved to {output_path}.csv and {output_path}.parquet"
    )


def main(config: ConfigModel) -> None:
    """
    Assemble the data of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("assembly_of_retrieved_data")
    utils.config.log_configuration(config)

    run_data_assemply(
        config.target_use,
        config.file,
        config.start_year,
        config.end_year,
        config.scenario_for_annual_electricity_demand_per_capita,
        config.scenario_for_gdp_ppp_per_capita,
        config.scenario_for_population,
        config.scenario_for_temperature,
        config.climate_model_for_temperature,
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "assemble",
            ConfigModel,
            "Assemble and preprocess the retrieved data for training the "
            "machine learning models or forecasting.",
        )
    )

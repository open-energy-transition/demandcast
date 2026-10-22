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

import datetime
import glob
import logging
import os
from collections.abc import Callable
from functools import reduce
from typing import Literal

import dask
import dask.dataframe
import numpy as np
import pandas as pd
import retrievals.annual_electricity_demand_per_capita
import retrievals.gdp_ppp_per_capita
import retrievals.gridded_weather
import retrievals.population
import utils.config
import utils.entities
from pydantic import BaseModel
from tqdm import tqdm

# The shares of the hours of a year, and of each of its months, that
# the training needs.
MIN_YEAR_COVERAGE = 0.9
MIN_MONTH_COVERAGE = 0.5


class ConfigModel(BaseModel):
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


def _validate(
    parameter_name: str,
    selected_value: str | None,
    available_values: list[str],
) -> None:
    """
    Validate a selected parameter value against available options.

    Parameters
    ----------
    parameter_name : str
        Name of the parameter being validated.
    selected_value : str
        The selected value to validate.
    available_values : list[str]
        List of available valid values.

    Raises
    ------
    ValueError
        If the selected value is not in the list of available values.
    """
    if selected_value and selected_value not in available_values:
        raise ValueError(
            f"{parameter_name.capitalize()} '{selected_value}' is not available. "
            f"Available {parameter_name}s: {available_values}"
        )


def _validate_scenario_model_combination(
    selected_model: str | None,
    selected_scenario: str | None,
    scenario_getter: Callable[[], list[str]] | None,
    model_scenario_getter: Callable[[], dict[str, list[str]]] | None,
) -> None:
    """
    Validate the selected scenario and model combination.

    Parameters
    ----------
    selected_model : str | None
        The selected model to validate.
    selected_scenario : str | None
        The selected scenario to validate.
    scenario_getter : Callable[[], list[str]] | None
        Function that returns list of available scenarios. If None,
        no scenario validation is performed.
    model_scenario_getter : Callable[[], dict[str, list[str]]]
        Function that returns dict mapping models to their available
        scenarios.
    """
    if model_scenario_getter and selected_model:
        available_scenarios_for_model = model_scenario_getter()
        _validate(
            "model", selected_model, list(available_scenarios_for_model.keys())
        )
        _validate(
            "scenario",
            selected_scenario,
            available_scenarios_for_model[selected_model]
            if selected_model
            else [""],
        )
    elif scenario_getter:
        available_scenarios = scenario_getter()
        _validate("scenario", selected_scenario, available_scenarios)


def _get_files_to_load(
    variable: str,
    entity_codes: list[str],
    selected_scenario: str | None,
    selected_model: str | None,
) -> dict[str, list[str]]:
    """
    Get the list of files to load for a specific entity code.

    Parameters
    ----------
    variable : str
        Variable to load.
    entity_codes : list[str]
        List of entity codes to get files for.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    selected_model : str | None
        Model to load (e.g., climate model). None for historical data.

    Returns
    -------
    files_to_load : dict[str, list[str]]
        Dictionary mapping entity codes to list of file paths to load.
    """
    # Get the folder containing the data.
    data_folder = utils.config.read_folders_structure()[
        f"{variable.replace(' ', '_').lower()}_folder"
    ]

    if variable == "electricity demand":
        # For electricity demand, read the hourly demand that combines
        # all the data sources of each code (see cleaning/combining.py).
        data_folder = utils.config.read_folders_structure()[
            "combined_electricity_demand_folder"
        ]

    # Initialize an empty dictionary to hold the files to load.
    files_to_load = {}

    for entity_code in entity_codes:
        # Define the file pattern based on the variable and parameters.
        file_pattern = f"{entity_code}"

        if variable == "temperature":
            # For temperature, add a glob pattern representing the year
            # number because multiple files per entity code exist.
            file_pattern += "_" + ("[0-9]" * 4)

        # Append model and scenario if provided.
        if selected_model:
            file_pattern += f"_{selected_model.upper().replace('-', '_').replace('.', '_')}"
        if selected_scenario:
            file_pattern += f"_{selected_scenario.upper().replace('-', '_').replace('.', '_')}"

        # Append the file extension.
        file_pattern += ".parquet"

        if variable == "temperature":
            # Add all matching files for temperature.
            files_to_load[entity_code] = glob.glob(
                os.path.join(data_folder, file_pattern)
            )

            if not files_to_load[entity_code]:
                logging.warning(
                    f"No temperature files found for entity code {entity_code}"
                    + (
                        f" with model {selected_model}"
                        if selected_model
                        else ""
                    )
                    + (
                        f" and scenario {selected_scenario}"
                        if selected_scenario
                        else ""
                    )
                    + "."
                )
        else:
            # Add a single file for other variables.
            files_to_load[entity_code] = [
                os.path.join(data_folder, file_pattern)
            ]

    return files_to_load


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

        # Read the current parquet file.
        current_data = pd.read_parquet(file_path)

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


def _load_data(
    variable: str,
    numeric_columns: list[str],
    target_use: str,
    selected_scenario: str | None = None,
    selected_model: str | None = None,
    scenario_getter: Callable[[], list[str]] | None = None,
    model_scenario_getter: Callable[[], dict[str, list[str]]] | None = None,
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load generic scenario-based data with common loading pattern.

    Parameters
    ----------
    variable : str
        Variable to load.
    numeric_columns : list[str]
        List of column names to convert to numeric.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    selected_model : str | None
        Model to load (e.g., climate model). None for historical data.
    scenario_getter : Callable[[], list[str]] | None
        Function that returns list of available scenarios. If None,
        no scenario validation is performed.
    model_scenario_getter : Callable[[], dict[str, list[str]]] | None
        Function that returns dict mapping models to their available
        scenarios. Required when selected_model is used.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    result_data : dask.dataframe.DataFrame
        Concatenated dataframe with data from all entity codes.
    """
    logging.info(f"Loading {variable} data.")

    # Define the data feature that the entities must have.
    if target_use == "training":
        data_feature = "electricity_demand_data"
    else:
        data_feature = "all_data"

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        data_feature, file_path=file_path
    )

    # Validate scenario and model combination.
    _validate_scenario_model_combination(
        selected_model,
        selected_scenario,
        scenario_getter,
        model_scenario_getter,
    )

    # Get the list of files to load for each entity code.
    files_to_load = _get_files_to_load(
        variable,
        entity_codes,
        selected_scenario,
        selected_model,
    )

    # Initialize a list to hold the loaded data.
    result_data = []

    for entity_code in tqdm(
        entity_codes,
        desc=f"Loading {variable} data",
    ):
        # Load data for the current entity code.
        entity_data = _load_data_for_entity(
            entity_code,
            files_to_load[entity_code],
            numeric_columns,
        )

        if entity_data is None:
            continue

        # Append to the result list.
        result_data.append(entity_data)

    # Concatenate all entity dataframes.
    result_data = dask.dataframe.concat(result_data)

    logging.info(
        f"Loaded {variable} data for "
        f"{len(result_data['Entity code'].unique())} entities successfully."
    )

    return result_data


def _load_electricity_demand(
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load and resample hourly electricity demand.

    Parameters
    ----------
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    dask.dataframe.DataFrame
        Concatenated dataframe with columns: Time (UTC), Load (MW),
        Entity code.
    """
    return _load_data(
        variable="electricity demand",
        numeric_columns=["Load (MW)"],
        target_use="training",
        file_path=file_path,
    )


def _load_annual_electricity_demand_per_capita(
    target_use: str,
    selected_scenario: str | None = None,
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load annual electricity demand per capita.

    Parameters
    ----------
    target_use : str,
        Target use for which the data is being assembled.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    dask.dataframe.DataFrame
        Concatenated dataframe with columns: Time (UTC),
        Annual electricity demand per capita (kWh), entity code.
    """
    return _load_data(
        variable="annual electricity demand per capita",
        numeric_columns=["Annual electricity demand per capita (kWh)"],
        target_use=target_use,
        selected_scenario=selected_scenario,
        scenario_getter=retrievals.annual_electricity_demand_per_capita.get_available_scenarios,
        file_path=file_path,
    )


def _load_gdp_ppp_per_capita(
    target_use: str,
    selected_scenario: str | None = None,
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load GDP PPP per capita.

    Parameters
    ----------
    target_use : str,
        Target use for which the data is being assembled.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    dask.dataframe.DataFrame
        Dataframe with columns: Time (UTC), GDP PPP per capita
        (2021 international $), entity code.
    """
    return _load_data(
        variable="GDP PPP per capita",
        numeric_columns=["GDP PPP per capita (2021 international $)"],
        target_use=target_use,
        selected_scenario=selected_scenario,
        scenario_getter=retrievals.gdp_ppp_per_capita.get_available_scenarios,
        file_path=file_path,
    )


def _load_population(
    target_use: str,
    selected_scenario: str | None = None,
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load population.

    Parameters
    ----------
    target_use : str,
        Target use for which the data is being assembled.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    dask.dataframe.DataFrame
        Concatenated dataframe with columns: Time (UTC), Population,
        entity code.
    """
    return _load_data(
        variable="population",
        numeric_columns=["Population"],
        target_use=target_use,
        selected_scenario=selected_scenario,
        scenario_getter=retrievals.population.get_available_scenarios,
        file_path=file_path,
    )


def _load_temperature(
    target_use: str,
    selected_scenario: str | None = None,
    selected_model: str | None = None,
    file_path: str | None = None,
) -> dask.dataframe.DataFrame:
    """
    Load temperature.

    Parameters
    ----------
    target_use : str,
        Target use for which the data is being assembled.
    selected_scenario : str | None
        Scenario to load. None for historical data.
    selected_model : str | None
        Climate model to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    dask.dataframe.DataFrame
        Concatenated dataframe with temperature features and entity
        code.
    """
    return _load_data(
        variable="temperature",
        numeric_columns=[
            "Temperature - Top 1 (K)",
            "Temperature - Top 3 (K)",
            "Monthly average temperature - Top 1 (K)",
            "Monthly average temperature rank - Top 1",
            "Annual average temperature - Top 1 (K)",
            "5 percentile temperature - Top 1 (K)",
            "95 percentile temperature - Top 1 (K)",
        ],
        target_use=target_use,
        selected_scenario=selected_scenario,
        selected_model=selected_model,
        model_scenario_getter=retrievals.gridded_weather.get_available_scenarios_for_model,
        file_path=file_path,
    )


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

    # Load individual datasets.
    annual_electricity_demand_per_capita = _load_annual_electricity_demand_per_capita(
        target_use,
        selected_scenario=scenario_for_annual_electricity_demand_per_capita,
        file_path=file,
    )
    gdp_ppp_per_capita = _load_gdp_ppp_per_capita(
        target_use,
        selected_scenario=scenario_for_gdp_ppp_per_capita,
        file_path=file,
    )
    population = _load_population(
        target_use, selected_scenario=scenario_for_population, file_path=file
    )
    temperature = _load_temperature(
        target_use,
        selected_scenario=scenario_for_temperature,
        selected_model=climate_model_for_temperature,
        file_path=file,
    )

    if start_year and end_year:
        # Keep the specified year range, before the merges: the other
        # datasets have no local year, and the merges keep only the
        # rows of all the datasets.
        temperature = temperature[
            (temperature["Local year"] >= start_year)
            & (temperature["Local year"] <= end_year)
        ]

    # Combine datasets into a list for merging.
    datasets_to_merge = [
        annual_electricity_demand_per_capita,
        gdp_ppp_per_capita,
        population,
        temperature,
    ]

    if target_use == "training":
        # Add electricity demand data if assembling for training.
        datasets_to_merge.append(_load_electricity_demand(file_path=file))

    # Merge datasets on common columns.
    assembled_data = _merge_datasets(
        datasets_to_merge,
        ["Time (UTC)", "Entity code"],
    )

    coverage = None
    if target_use == "training":
        # Keep the years with enough hours, and calculate the load
        # fraction for training data.
        assembled_data, coverage = _select_complete_years(assembled_data)
        assembled_data = _calculate_load_fraction(assembled_data)

    # Get the assembled data folder path.
    assembled_data_folder = utils.config.read_folders_structure()[
        "assembled_data_folder"
    ]
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

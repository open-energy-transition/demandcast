# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script assembles and preprocesses the retrieved data for
    training the machine learning models or forecasting.
"""

import datetime
import glob
import logging
import os
from functools import reduce
from typing import Callable, Optional

import pandas
import retrievals.annual_electricity_demand_per_capita
import retrievals.gdp_ppp_per_capita
import retrievals.population
import retrievals.temperature
import utils.config
import utils.entities
from pydantic import BaseModel, ValidationError
from tqdm import tqdm


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for data assembly.

    Returns
    -------
    config : BaseModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        target_use: str
        scenario: Optional[str] = None
        climate_model: Optional[str] = None
        file: Optional[str] = None
        start_year: Optional[int] = None
        end_year: Optional[int] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "assemble",
        "Assemble and preprocess the retrieved data for "
        "training the machine learning models or forecasting.",
    )

    try:
        # Validate the configuration.
        config = ConfigModel(**raw_config)

        logging.info("Configuration validated successfully:")
        for field, value in config.model_dump().items():
            logging.info(f" - {field}: {value}")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def _is_date(string: str) -> bool:
    """
    Check if a string is a valid date in YYYY-MM-DD format.

    Parameters
    ----------
    string : str
        The string to check.

    Returns
    -------
    bool
        True if the string is a valid date, False otherwise.
    """
    try:
        datetime.datetime.strptime(string, "%Y-%m-%d")
        return True
    except ValueError:
        return False


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


def _get_data_sources_with_longest_date_range(
    entity_codes: list[str],
) -> dict[str, str]:
    """
    Get the electricity demand data sources with the longest date range.

    Parameters
    ----------
    entity_codes : list[str]
        List of entity codes to check.

    Returns
    -------
    data_source_with_longest_range : dict[str, str]
        Dictionary mapping entity codes to the data source with the
        longest date range.
    """
    # Get the data sources for each entity code.
    data_sources = {}
    for entity_code in entity_codes:
        data_sources[entity_code] = (
            utils.entities.get_electricity_demand_data_sources_containing_code(
                entity_code
            )
        )

    # Initialize a dictionary to hold the data source with the longest
    # date range for each entity code.
    data_source_with_longest_range = {}

    for entity_code in tqdm(
        entity_codes,
        desc=(
            "Determining electricity demand data sources with longest date range"
        ),
    ):
        # Initialize a temporary variable to hold the longest date range
        # for the current entity code.
        longest_date_range = 0

        for data_source in data_sources[entity_code]:
            # Get the date ranges available for the current entity code
            # and data source.
            date_range = utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
                data_source
            )[entity_code]

            # Calculate the number of days in the date range.
            days = (date_range[1] - date_range[0]).days

            if days > longest_date_range:
                # Update the longest date range found so far.
                longest_date_range = days

                # Update the data source with the longest range.
                data_source_with_longest_range[entity_code] = data_source

    return data_source_with_longest_range


def _get_files_to_load(
    variable: str,
    entity_codes: list[str],
    selected_scenario: str | None,
    selected_model: str | None,
    use_glob: bool,
    data_source: dict[str, str] | None,
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
    scenario_getter : Callable[[], dict[str, list[str]]] | None
        Function that returns dict mapping models to their available
        scenarios. Required when selected_model is used.
    model_scenario_getter : Callable[[], dict[str, list[str]]] | None
        Function that returns dict mapping models to their available
        scenarios. Required when selected_model is used.
    use_glob : bool
        Whether to use glob pattern matching for file discovery.
    data_source : dict[str, str] | None
        Dictionary mapping entity codes to their data source. Required
        when loading electricity demand data.

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
        # For electricity demand, find the folder with the most recent
        # date as name.
        data_folder = max(
            [
                os.path.join(data_folder, subfolder)
                for subfolder in os.listdir(data_folder)
                if os.path.isdir(os.path.join(data_folder, subfolder))
                and _is_date(subfolder)
            ]
        )

    # Initialize an empty dictionary to hold the files to load.
    files_to_load = {}

    for entity_code in entity_codes:
        if use_glob:
            # When more than one file has to be considered, construct a
            # glob pattern.
            file_pattern = (
                f"{entity_code}_*"
                + (f"_{selected_model}" if selected_model else "")
                + (f"_{selected_scenario}" if selected_scenario else "")
                + ".parquet"
            )

            # Find matching files.
            files_to_load[entity_code] = [
                f for f in glob.glob(os.path.join(data_folder, file_pattern))
            ]

            if not files_to_load[entity_code]:
                logging.warning(
                    f"No files found for entity code {entity_code}"
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
            # Construct the relevant file name.
            files_to_load[entity_code] = [
                os.path.join(
                    data_folder,
                    (
                        f"{entity_code}"
                        + (
                            f"_{data_source[entity_code]}"
                            if data_source
                            else ""
                        )
                        + (f"_{selected_model}" if selected_model else "")
                        + (
                            f"_{selected_scenario}"
                            if selected_scenario
                            else ""
                        )
                        + ".parquet"
                    ),
                )
            ]

    return files_to_load


def _load_data_for_entity(
    entity_code: str,
    file_paths: list[str],
    numeric_columns: list[str],
) -> pandas.DataFrame | None:
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
    entity_data : pandas.DataFrame | None
        Dataframe with processed data for the entity code, or None if
        no data was loaded.
    """
    # Initialize a temporary dataframe to hold data for the current
    # entity code.
    entity_data = pandas.DataFrame()

    for file_path in file_paths:
        if not os.path.exists(file_path):
            logging.warning(
                f"File {file_path} not found for entity code {entity_code}. "
                "Skipping."
            )
            continue

        # Read the current parquet file.
        current_data = pandas.read_parquet(file_path)

        # Append to the entity dataframe.
        entity_data = pandas.concat([entity_data, current_data])

    # If no data was loaded, return None.
    if entity_data.empty:
        return None

    # Ensure specified columns are numeric.
    for column in numeric_columns:
        entity_data[column] = pandas.to_numeric(
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

    # Add entity code column and reset index.
    entity_data["Entity code"] = entity_code
    entity_data = entity_data.reset_index()

    return entity_data


def _load_data(
    variable: str,
    numeric_columns: list[str],
    target_use: str,
    selected_scenario: str | None = None,
    selected_model: str | None = None,
    scenario_getter: Callable[[], list[str]] | None = None,
    model_scenario_getter: Callable[[], dict[str, list[str]]] | None = None,
    file_path: str | None = None,
) -> pandas.DataFrame:
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
    result_data : pandas.DataFrame
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

    # For electricity demand, get the data source with the longest date
    # range for each entity code.
    if variable == "electricity demand":
        data_source = _get_data_sources_with_longest_date_range(entity_codes)
    else:
        data_source = None

    # For temperature, use glob pattern matching because multiple files
    # per entity code exist (multiple years).
    if variable == "temperature":
        use_glob = True
    else:
        use_glob = False

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
        use_glob=use_glob,
        data_source=data_source,
    )

    # Initialize an empty dataframe to hold all data.
    result_data = pandas.DataFrame()

    for entity_code in tqdm(
        entity_codes,
        desc=f"Loading {variable} data",
    ):
        # Read and process the file.
        entity_data = _load_data_for_entity(
            entity_code,
            files_to_load[entity_code],
            numeric_columns,
        )

        if entity_data is None:
            continue

        # Append to the main dataframe.
        result_data = pandas.concat(
            [result_data, entity_data], ignore_index=True
        )

    logging.info(
        f"Loaded {variable} data for "
        f"{len(result_data['Entity code'].unique())} entities."
    )

    return result_data


def _load_electricity_demand(
    file_path: str | None = None,
) -> pandas.DataFrame:
    """
    Load and resample hourly electricity demand.

    Parameters
    ----------
    selected_codes : list[str] | None
        List of entity codes to load. If None, load all available codes.

    Returns
    -------
    pandas.DataFrame
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
) -> pandas.DataFrame:
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
    pandas.DataFrame
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
) -> pandas.DataFrame:
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
    pandas.DataFrame
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
) -> pandas.DataFrame:
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
    population : pandas.DataFrame
        Concatenated dataframe with columns: Time (UTC),
        Population, entity code.
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
) -> pandas.DataFrame:
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
    temperature : pandas.DataFrame
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
        model_scenario_getter=retrievals.temperature.get_available_scenarios_for_model,
        file_path=file_path,
    )


def _merge_datasets(
    datasets: list[pandas.DataFrame], on: list[str]
) -> pandas.DataFrame:
    """
    Merge multiple datasets on specified columns.

    Parameters
    ----------
    datasets : list[pandas.DataFrame]
        List of dataframes to merge.
    on : list[str]
        List of columns to merge on.

    Returns
    -------
    merged_dataset : pandas.DataFrame
        Merged dataset.
    """
    # Merge all datasets using reduce.
    merged_dataset = reduce(
        lambda left, right: pandas.merge(left, right, on=on),
        datasets,
    )

    logging.info(f"Merged {len(datasets)} datasets successfully.")
    logging.info(
        f"Merged dataset contains {len(merged_dataset)} rows, "
        f"{len(merged_dataset.columns)} columns, and "
        f"{len(merged_dataset['Entity code'].unique())} entities."
    )

    return merged_dataset


def _calculate_load_fraction(
    merged_dataset: pandas.DataFrame,
) -> pandas.DataFrame:
    """
    Calculate the fraction of load at each timestamp.

    Parameters
    ----------
    merged_dataset : pandas.DataFrame
        Input dataframe with load, entity code, and local year columns.

    Returns
    -------
    merged_dataset : pandas.DataFrame
        Dataframe with load fraction column added.
    """
    # Add a new column for the load fraction.
    merged_dataset["Load (fraction of annual total)"] = 0.0

    for name, group in merged_dataset.groupby(["Entity code", "Local year"]):
        # Calculate the total load for the year.
        yearly_load = group["Load (MW)"].sum()

        # Calculate the number of hours tracked in the year.
        amount_of_hours_tracked = len(group["Load (MW)"])

        # Get the year from the group name.
        year = name[1]

        # Calculate the total number of hours in the year.
        amount_of_hours_in_year = (
            len(pandas.date_range(start=f"{year}-01-01", end=f"{year}-12-31"))
            * 24
        )

        # Calculate the load fraction.
        load_fraction = group["Load (MW)"] / yearly_load

        # Adjust percentages to account for missing hours.
        merged_dataset.loc[group.index, "Load (fraction of annual total)"] = (
            load_fraction * (amount_of_hours_tracked / amount_of_hours_in_year)
        )

    return merged_dataset


def run_data_assemply(
    target_use: str,
    scenario: str | None = None,
    climate_model: str | None = None,
    file: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> None:
    """
    Preprocess raw data and save the assembled dataset.

    Parameters
    ----------
    target_use : str
        Target use for which the data is being assembled. It can be
        'training' or 'forecasting'.
    scenario : str, optional
        Selected scenario for data retrieval, by default "".
    climate_model : str, optional
        Selected climate model for data retrieval, by default "".
    file_path : str, optional
        Path to the data files, by default "".

    Raises
    ------
    ValueError
        If target_use is not 'training' or 'forecasting'. If only one of
        start_year or end_year is provided.
    """
    # Check that the target use is valid.
    if target_use not in ["training", "forecasting"]:
        raise ValueError(
            "target_use must be either 'training' or 'forecasting'"
        )

    logging.info(f"Starting data assembly for {target_use}.")

    # Load individual datasets.
    annual_electricity_demand_per_capita = (
        _load_annual_electricity_demand_per_capita(
            target_use, selected_scenario=scenario, file_path=file
        )
    )
    gdp_ppp_per_capita = _load_gdp_ppp_per_capita(
        target_use, selected_scenario=scenario, file_path=file
    )
    population = _load_population(
        target_use, selected_scenario=scenario, file_path=file
    )
    temperature = _load_temperature(
        target_use,
        selected_scenario=scenario,
        selected_model=climate_model,
        file_path=file,
    )

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
    merged_data = _merge_datasets(
        datasets_to_merge,
        ["Time (UTC)", "Entity code"],
    )

    if target_use == "training":
        # Calculate load fraction for training data.
        merged_data = _calculate_load_fraction(merged_data)

    if start_year and end_year:
        # Filter data for the specified year range.
        merged_data = merged_data[
            (merged_data["Local year"] >= start_year)
            & (merged_data["Local year"] <= end_year)
        ]
    elif (start_year and not end_year) or (end_year and not start_year):
        raise ValueError(
            "Both start_year and end_year must be provided to filter "
            "by year range."
        )

    # Get the assembled data folder path.
    assembled_data_folder = utils.config.read_folders_structure()[
        "assembled_data_folder"
    ]
    os.makedirs(assembled_data_folder, exist_ok=True)

    # Construct the output file path.
    output_path = os.path.join(
        assembled_data_folder,
        f"assembled_data_for_{target_use}_"
        + (f"scenario_{scenario}_" if scenario else "")
        + (f"model_{climate_model}_" if climate_model else "")
        + f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
    )

    # Save the merged dataset to CSV and Parquet formats.
    merged_data.to_csv(output_path + ".csv", index=False)
    merged_data.to_parquet(output_path + ".parquet", index=False)

    logging.info(
        f"Assembled data saved to {output_path}.csv and {output_path}.parquet"
    )


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("assembly_of_retrieved_data")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Run the data assembly process.
    run_data_assemply(
        config.target_use,
        config.scenario,
        config.climate_model,
        config.file,
        config.start_year,
        config.end_year,
    )

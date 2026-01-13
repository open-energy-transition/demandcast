# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script assembles and preprocesses the retrieved data for
    training and evaluating the machine learning models.
"""

import datetime
import glob
import logging
import os
from functools import reduce
from typing import Optional

import pandas
import retrievals.annual_electricity_demand_per_capita
import retrievals.gdp_ppp_per_capita
import retrievals.population
import retrievals.temperature
import utils.config
import utils.entities
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for data assembly.

    Returns
    -------
    ConfigModel : BaseModel
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

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        os.path.basename(__file__),
        "Assemble and preprocess the retrieved data for "
        "training and evaluating the machine learning models.",
    )

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
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


def _read_and_process_entity_files(
    folder: str,
    filenames: str | list[str],
    entity_code: str,
    numeric_columns: list[str],
    resample_to_hourly: bool = False,
) -> pandas.DataFrame | None:
    """
    Read a parquet file and add entity code column.

    Parameters
    ----------
    folder : str
        Folder containing the file.
    filenames : str | list[str]
        Filename or list of filenames to read.
    entity_code : str
        Entity code to add to the dataframe.
    numeric_columns : list[str]
        List of columns to convert to numeric.
    resample_to_hourly : bool
        Whether to resample the data to hourly frequency.

    Returns
    -------
    pandas.DataFrame | None
        Dataframe with entity code column, or None if file not found.
    """
    # Ensure filenames is a list.
    if isinstance(filenames, str):
        filenames = [filenames]

    # Initialize a temporary dataframe to hold data for the current
    # entity code.
    entity_data = pandas.DataFrame()

    for filename in filenames:
        # Construct the full file path.
        file_path = os.path.join(folder, filename)

        if not os.path.exists(file_path):
            logging.warning(
                f"File {file_path} not found for in {folder} for "
                f"entity code {entity_code}. Skipping."
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

    if resample_to_hourly:
        # Resample to hourly frequency by taking the mean.
        entity_data = entity_data.resample(
            "1h", label="right", closed="right"
        ).mean()

        # Drop any rows with NaN values after resampling.
        entity_data = entity_data.dropna()

    # Add entity code column and reset index.
    entity_data["Entity code"] = entity_code
    entity_data = entity_data.reset_index()

    return entity_data


def load_electricity_demand(
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
    # Get the folder containing the electricity demand data.
    electricity_demand_folder = utils.config.read_folders_structure()[
        "electricity_demand_folder"
    ]

    # Find the folder with the most recent date as name.
    most_recent_date_folder = max(
        [
            os.path.join(electricity_demand_folder, subfolder)
            for subfolder in os.listdir(electricity_demand_folder)
            if os.path.isdir(
                os.path.join(electricity_demand_folder, subfolder)
            )
            and _is_date(subfolder)
        ]
    )

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        "electricity_demand_data", file_path=file_path
    )

    # Get the data sources for each entity code.
    data_sources = {}
    for code in entity_codes:
        data_sources[code] = (
            utils.entities.get_electricity_demand_data_sources_containing_code(
                code
            )
        )

    # Initialize an empty dataframe to hold all demand data.
    electricity_demand = pandas.DataFrame()

    for entity_code in entity_codes:
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

                # Construct the relevant file name.
                relevant_file = f"{entity_code}_{data_source.lower()}.parquet"

        # Read and process the file.
        entity_data = _read_and_process_entity_files(
            most_recent_date_folder,
            relevant_file,
            entity_code,
            numeric_columns=["Load (MW)"],
            resample_to_hourly=True,
        )

        if entity_data is None:
            continue

        # Append to the main dataframe.
        electricity_demand = pandas.concat(
            [electricity_demand, entity_data], ignore_index=True
        )

    return electricity_demand


def load_annual_electricity_demand_per_capita(
    selected_scenario: str | None = None,
    file_path: str | None = None,
) -> pandas.DataFrame:
    """
    Load annual electricity demand per capita.

    Parameters
    ----------
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
    # Get the folder containing the annual electricity demand per capita
    # data.
    annual_electricity_demand_per_capita_folder = (
        utils.config.read_folders_structure()[
            "annual_electricity_demand_per_capita_folder"
        ]
    )

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        "all_data", file_path=file_path
    )

    # Validate scenario.
    available_scenarios = retrievals.annual_electricity_demand_per_capita.get_available_scenarios()
    _validate("scenario", selected_scenario, available_scenarios)

    # Initialize an empty dataframe to hold all annual electricity
    # demand per capita data.
    annual_electricity_demand_per_capita = pandas.DataFrame()

    for entity_code in entity_codes:
        # Construct the relevant file name.
        relevant_file = (
            f"{entity_code}"
            + (f"_{selected_scenario}" if selected_scenario else "")
            + ".parquet"
        )

        # Read and process the file.
        entity_data = _read_and_process_entity_files(
            annual_electricity_demand_per_capita_folder,
            relevant_file,
            entity_code,
            numeric_columns=["Annual electricity demand per capita (kWh)"],
        )

        if entity_data is None:
            continue

        # Append to the main dataframe.
        annual_electricity_demand_per_capita = pandas.concat(
            [annual_electricity_demand_per_capita, entity_data],
            ignore_index=True,
        )

    return annual_electricity_demand_per_capita


def load_gdp_ppp_per_capita(
    selected_scenario: str | None = None, file_path: str | None = None
) -> pandas.DataFrame:
    """
    Load GDP PPP per capita.

    Parameters
    ----------
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
    # Get the folder containing the GDP PPP per capita data.
    gdp_ppp_per_capita_folder = utils.config.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        "all_data", file_path=file_path
    )

    # Validate scenario.
    available_scenarios = (
        retrievals.gdp_ppp_per_capita.get_available_scenarios()
    )
    _validate("scenario", selected_scenario, available_scenarios)

    # Initialize an empty dataframe to hold all GDP PPP per capita data.
    gdp_ppp_per_capita = pandas.DataFrame()

    for entity_code in entity_codes:
        # Construct the relevant file name.
        relevant_file = (
            f"{entity_code}"
            + (f"_{selected_scenario}" if selected_scenario else "")
            + ".parquet"
        )

        # Read and process the file.
        entity_data = _read_and_process_entity_files(
            gdp_ppp_per_capita_folder,
            relevant_file,
            entity_code,
            numeric_columns=["GDP PPP per capita (2021 international $)"],
        )

        if entity_data is None:
            continue

        # Append to the main dataframe.
        gdp_ppp_per_capita = pandas.concat(
            [gdp_ppp_per_capita, entity_data], ignore_index=True
        )

    return gdp_ppp_per_capita


def load_population(
    selected_scenario: str | None = None, file_path: str | None = None
) -> pandas.DataFrame:
    """
    Load population.

    Parameters
    ----------
    selected_scenario : str | None
        Scenario to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with columns: Time (UTC),
        Population, entity code.
    """
    # Get the folder containing the population data.
    population_folder = utils.config.read_folders_structure()[
        "population_folder"
    ]

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        "all_data", file_path=file_path
    )

    # Validate scenario.
    available_scenarios = retrievals.population.get_available_scenarios()
    _validate("scenario", selected_scenario, available_scenarios)

    # Initialize an empty dataframe to hold all population data.
    population = pandas.DataFrame()

    for entity_code in entity_codes:
        # Construct the relevant file name.
        relevant_file = (
            f"{entity_code}"
            + (f"_{selected_scenario}" if selected_scenario else "")
            + ".parquet"
        )

        # Read and process the file.
        entity_data = _read_and_process_entity_files(
            population_folder,
            relevant_file,
            entity_code,
            numeric_columns=["Population"],
        )

        if entity_data is None:
            continue

        # Append to the main dataframe.
        population = pandas.concat(
            [population, entity_data], ignore_index=True
        )

    return population


def load_temperature(
    selected_scenario: str | None = None,
    selected_model: str | None = None,
    file_path: str | None = None,
) -> pandas.DataFrame:
    """
    Load temperature.

    Parameters
    ----------
    selected_scenario : str | None
        Scenario to load. None for historical data.
    selected_model : str | None
        Climate model to load. None for historical data.
    file_path : str | None
        Optional file path including entity codes to load. If None,
        load all available codes.

    Returns
    -------
    pandas.DataFrame
        Concatenated dataframe with temperature features and entity
        code.
    """
    # Get the folder containing the temperature data.
    temperature_folder = utils.config.read_folders_structure()[
        "temperature_folder"
    ]

    # Check and filter entity codes.
    entity_codes = utils.entities.check_and_get_codes_with(
        "all_data", file_path=file_path
    )

    # Get the available scenarios and models.
    available_scenarios_for_model = (
        retrievals.temperature.get_available_scenarios_for_model()
    )

    # Validate model and scenario.
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

    # Initialize an empty dataframe to hold all temperature data.
    temperature = pandas.DataFrame()

    for entity_code in entity_codes:
        # Construct the relevant file names.
        relevant_files = (
            f"{entity_code}_*"
            + (f"_{selected_model}" if selected_model else "")
            + (f"_{selected_scenario}" if selected_scenario else "")
            + ".parquet"
        )

        # Use glob to find matching files.
        matching_files = [
            f
            for f in glob.glob(
                os.path.join(temperature_folder, relevant_files)
            )
        ]

        if not matching_files:
            logging.warning(
                f"No temperature files found for entity code {entity_code} "
                f"with model {selected_model} and scenario "
                f"{selected_scenario}. Skipping."
            )
            continue

        # Read and process the files.
        entity_data = _read_and_process_entity_files(
            temperature_folder,
            [os.path.basename(f) for f in matching_files],
            entity_code,
            numeric_columns=[
                "Temperature - Top 1 (K)",
                "Temperature - Top 3 (K)",
                "Monthly average temperature - Top 1 (K)",
                "Monthly average temperature rank - Top 1",
                "Annual average temperature - Top 1 (K)",
                "5 percentile temperature - Top 1 (K)",
                "95 percentile temperature - Top 1 (K)",
            ],
        )

        # Append to the main dataframe.
        temperature = pandas.concat(
            [temperature, entity_data], ignore_index=True
        )

    return temperature


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
    pandas.DataFrame
        Merged dataset.
    """
    return reduce(
        lambda left, right: pandas.merge(left, right, on=on),
        datasets,
    )


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
) -> None:
    """
    Preprocess raw data and save the processed dataset.

    Parameters
    ----------
    target_use : str
        Target use for which the data is being assembled. It can be
        'training' or 'evaluation'.
    scenario : str, optional
        Selected scenario for data retrieval, by default "".
    climate_model : str, optional
        Selected climate model for data retrieval, by default "".
    file_path : str, optional
        Path to the data files, by default "".

    Raises
    ------
    ValueError
        If target_use is not 'training' or 'evaluation'.
    """
    # Check that the target use is valid.
    if target_use not in ["training", "evaluation"]:
        raise ValueError(
            "target_use must be either 'training' or 'evaluation'"
        )

    # Load the datasets. The electricity demand data is only needed for
    # training.
    if target_use == "training":
        electricity_demand = load_electricity_demand(file_path=file)
    annual_electricity_demand_per_capita = (
        load_annual_electricity_demand_per_capita(
            selected_scenario=scenario, file_path=file
        )
    )
    gdp_ppp_per_capita = load_gdp_ppp_per_capita(
        selected_scenario=scenario, file_path=file
    )
    population = load_population(selected_scenario=scenario, file_path=file)
    temperature = load_temperature(
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
        datasets_to_merge.append(electricity_demand)

    # Merge datasets on common columns.
    merged_data = _merge_datasets(
        datasets=datasets_to_merge,
        on=["Time (UTC)", "Entity code"],
    )

    if target_use == "training":
        # Calculate load fraction for training data.
        merged_data = _calculate_load_fraction(merged_data)

    # Get the processed data folder path.
    processed_data_folder = utils.config.read_folders_structure()[
        "processed_data_folder"
    ]
    os.makedirs(processed_data_folder, exist_ok=True)

    # Construct the output file path.
    output_path = os.path.join(
        processed_data_folder,
        f"assembled_data_for_{target_use}_"
        + (f"scenario_{scenario}_" if scenario else "")
        + (f"model_{climate_model}_" if climate_model else "")
        + f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet",
    )

    # Save the merged dataset to a parquet file.
    merged_data.to_parquet(output_path, engine="pyarrow")


if __name__ == "__main__":
    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Set up the logging configuration.
    utils.config.set_up_logging("assembly_of_retrieved_data")

    # Run the data assembly process.
    run_data_assemply(
        config.target_use,
        config.scenario,
        config.climate_model,
        config.file,
    )

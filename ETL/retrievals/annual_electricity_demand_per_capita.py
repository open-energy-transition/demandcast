# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    annual electricity demand per capita data from Ember and the World
    Bank, and to calculate future annual electricity demand per capita
    based on growth rates from the IAMC scenarios. The electricity
    demand data is extracted for the countries and subdivisions of
    interest and saved into CSV and Parquet files.

    Source: https://ember-energy.org/data/yearly-electricity-data/
    Source: https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC
    Source: https://tntcat.iiasa.ac.at/SspDb
"""

import logging
import os
import zipfile
from io import BytesIO

import pandas
import requests
import utils.directories
import utils.entities
import utils.scenarios
import utils.time_series


def download_electricity_demand_per_capita_from_ember() -> pandas.DataFrame:
    """
    Download historical electricity demand per capita from Ember.

    Returns
    -------
    pandas.DataFrame
        The electricity demand per capita data from Ember.
    """
    logging.info("Downloading electricity demand per capita data from Ember.")

    # Download the electricity demand dataset from Ember.
    electricity_demand_dataset = pandas.read_csv(
        "https://storage.googleapis.com/emb-prod-bkt-publicdata/"
        "public-downloads/yearly_full_release_long_format.csv"
    )

    # Extract and return the electricity demand per capita data.
    return electricity_demand_dataset[
        electricity_demand_dataset["Variable"] == "Demand per capita"
    ]


def download_electricity_demand_per_capita_from_world_bank() -> (
    pandas.DataFrame
):
    """
    Download historical electricity demand per capita from World Bank.

    Returns
    -------
    pandas.DataFrame
        The electricity demand per capita from the World Bank.
    """
    logging.info(
        "Downloading electricity demand per capita data from the World Bank."
    )

    # Define the URL to download the electricity demand per capita data.
    url = (
        "https://api.worldbank.org/v2/en/indicator/"
        "EG.USE.ELEC.KH.PC?downloadformat=csv"
    )

    # Fetch the data from the World Bank.
    response = requests.get(url)

    # Extract the archive from the response.
    with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
        # Get the name of data file in the archive. It is the file that
        # does not start with "Metadata" and ends with ".csv".
        world_bank_file_name = [
            name
            for name in archive.namelist()
            if not name.startswith("Metadata") and name.endswith(".csv")
        ][0]

        # Extract and return the electricity demand per capita from the
        # archive.
        return pandas.read_csv(archive.open(world_bank_file_name), skiprows=4)


def extract_historical_electricity_demand_per_capita(
    ember_electricity_demand_per_capita: pandas.DataFrame,
    world_bank_electricity_demand_per_capita: pandas.DataFrame,
    iso_alpha_3_code: str,
) -> pandas.Series:
    """
    Extract the historical electricity demand per capita.

    Parameters
    ----------
    ember_electricity_demand_per_capita : pandas.DataFrame
        The electricity demand per capita data from Ember.
    world_bank_electricity_demand_per_capita : pandas.DataFrame
        The electricity demand per capita from the World Bank.
    iso_alpha_3_code : str
        The ISO alpha-3 code of the country.

    Returns
    -------
    pandas.Series
        The electricity demand per capita.
    """
    # Extract the electricity demand per capita from Ember for the
    # country of interest.
    ember_electricity_demand_per_capita = ember_electricity_demand_per_capita[
        ember_electricity_demand_per_capita["ISO 3 code"] == iso_alpha_3_code
    ]

    # Convert to a Series with years as index and convert MWh to kWh.
    ember_electricity_demand_per_capita = pandas.Series(
        ember_electricity_demand_per_capita["Value"].to_numpy() * 1000,
        index=ember_electricity_demand_per_capita["Year"],
    )

    # Extract the electricity demand per capita from the World Bank for
    # the country of interest.
    world_bank_electricity_demand_per_capita = (
        world_bank_electricity_demand_per_capita[
            world_bank_electricity_demand_per_capita["Country Code"]
            == iso_alpha_3_code
        ]
        .iloc[
            0,
            world_bank_electricity_demand_per_capita.columns.str.isdigit(),
        ]
        .dropna()
    )

    # Convert the index to integers.
    world_bank_electricity_demand_per_capita.index = (
        world_bank_electricity_demand_per_capita.index.astype(int)
    )

    # Combine the two datasets by averaging them.
    electricity_demand_per_capita = (
        world_bank_electricity_demand_per_capita
        + ember_electricity_demand_per_capita
    ) / 2

    # Where the combined series is NaN because one of the datasets
    # is missing, use the other dataset.
    return electricity_demand_per_capita.fillna(
        world_bank_electricity_demand_per_capita
    ).fillna(ember_electricity_demand_per_capita)


def _get_future_electricity_demand_per_capita(
    iso_alpha_3_code: str,
    scenario: str,
    last_historical_value: float,
    future_years: list[int],
) -> pandas.Series:
    """
    Get the future electricity demand per capita.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO alpha-3 code of the country.
    scenario : str
        The scenario of interest.
    last_historical_value : float
        The last historical value of the electricity demand per capita.
    future_years : list[int]
        The list of future years where the electricity demand per capita
        is to be calculated.

    Returns
    -------
    pandas.Series
        The future electricity demand per capita.

    Raises
    ------
    ValueError
        If there is not exactly one row for the region and scenario in
        the annual growth rates data.
    """
    # Define the file path of the annual growth rates of future
    # electricity demand per capita.
    file_path = os.path.join(
        utils.directories.read_folders_structure()[
            "annual_electricity_demand_per_capita_folder"
        ],
        "manual_downloads",
        "IAM_annual_electricity_per_capita_growth.xlsx",
    )

    # Read the annual growth rates.
    annual_growth_rate = pandas.read_excel(
        file_path,
        sheet_name="data",
        index_col=0,
    )

    # Get the code of the region that includes the country.
    region_code = utils.scenarios.get_iam_region(iso_alpha_3_code)

    # Extract the annual growth rates of the electricity demand per
    # capita for the region and scenario of interest.
    annual_growth_rate = annual_growth_rate[
        (annual_growth_rate["Region"] == region_code)
        & (annual_growth_rate["Scenario"] == scenario)
    ]

    # Check that there is only one row.
    if len(annual_growth_rate) != 1:
        raise ValueError(
            f"Expected one row for region {region_code} and scenario "
            f"{scenario}, but got {len(annual_growth_rate)}."
        )

    # Convert to a Series with years as index by selecting only the
    # columns that are digits and dropping NaN values.
    annual_growth_rate = annual_growth_rate.iloc[
        0,
        annual_growth_rate.columns.astype(str).str.isdigit(),
    ].dropna()

    # Calculate the future electricity demand per capita by applying
    # the annual growth rates to the last historical value.
    return utils.scenarios.calculate_values_from_growth_rate(
        last_historical_value,
        future_years,
        annual_growth_rate,
    )


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract annual electricity demand per capita.

    This function downloads historical electricity demand per capita
    data from Ember and the World Bank, extracts the electricity data
    for the countries and subdivisions of interest, calculates future
    electricity demand per capita based on growth rates from the IAMC
    scenarios, and saves it into CSV and Parquet files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the electricity demand per capita data to be
        retrieved.
    start_year : int | None
        The start year of the range of electricity demand per capita
        data to be retrieved.
    end_year : int | None
        The end year of the range of electricity demand per capita
        data to be retrieved.
    scenario : str | None
        The scenario of the electricity demand per capita data to be
        retrieved.
    """
    # Get the directory to store the annual electricity demand per
    # capita data.
    result_directory = utils.directories.read_folders_structure()[
        "annual_electricity_demand_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the electricity demand per capita from Ember.
    ember_electricity_demand_per_capita = (
        download_electricity_demand_per_capita_from_ember()
    )

    # Download the electricity demand per capita from the World Bank.
    world_bank_electricity_demand_per_capita = (
        download_electricity_demand_per_capita_from_world_bank()
    )

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Define the available scenarios.
    available_scenarios = [
        "SSP1-Baseline",
        "SSP1-19",
        "SSP1-26",
        "SSP1-34",
        "SSP1-45",
        "SSP2-Baseline",
        "SSP2-19",
        "SSP2-26",
        "SSP2-34",
        "SSP2-45",
        "SSP2-60",
        "SSP3-Baseline",
        "SSP3-34",
        "SSP3-45",
        "SSP3-60",
        "SSP4-Baseline",
        "SSP4-26",
        "SSP4-34",
        "SSP4-45",
        "SSP4-60",
        "SSP5-Baseline",
        "SSP5-19",
        "SSP5-26",
        "SSP5-34",
        "SSP5-45",
        "SSP5-60",
    ]

    # Loop over the countries and subdivisions.
    for code in codes:
        # Get the ISO Alpha-3 code of the country.
        iso_alpha_3_code = utils.entities.get_iso_alpha_3_code(code)

        # Extract the electricity data for the country.
        historical_electricity_demand_per_capita = (
            extract_historical_electricity_demand_per_capita(
                ember_electricity_demand_per_capita,
                world_bank_electricity_demand_per_capita,
                iso_alpha_3_code,
            )
        )

        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Get the years of available historical data.
        available_historical_years = (
            historical_electricity_demand_per_capita.index.tolist()
        )

        # Get the years of available future data.
        available_future_years = list(
            range(max(available_historical_years) + 1, 2101)
        )

        # Get the list of year and scenario combinations.
        year_scenario_list = (
            utils.scenarios.get_year_and_scenario_combinations(
                year,
                start_year,
                end_year,
                available_historical_years,
                available_future_years,
                scenario,
                available_scenarios,
            )
        )

        # Define the file path of the electricity demand per capita
        # data of the country or subdivision.
        file_path_without_ext = os.path.join(result_directory, code)

        # Get the selcted historical years.
        selected_historical_years = [
            year for year, scenario in year_scenario_list if scenario is None
        ]

        # Get the selected future years.
        selected_future_years = [
            year
            for year, scenario in year_scenario_list
            if scenario is not None
        ]

        # Get the selected scenarios.
        selected_scenarios = list(
            set(
                [
                    scenario
                    for year, scenario in year_scenario_list
                    if scenario is not None
                ]
            )
        )

        if (
            not os.path.exists(file_path_without_ext + ".parquet")
            or not os.path.exists(file_path_without_ext + ".csv")
        ) and selected_historical_years:
            logging.info(
                f"Extracting historical annual electricity per capita data "
                f"for {code}."
            )

            # Extract the respective electricity demand per capita.
            selected_historical_electricity_demand_per_capita = (
                historical_electricity_demand_per_capita[
                    historical_electricity_demand_per_capita.index.isin(
                        selected_historical_years
                    )
                ]
            )

            # Convert the historical electricity demand per capita data
            # from yearly to hourly values.
            selected_historical_electricity_demand_per_capita = (
                utils.time_series.convert_from_yearly_to_hourly(
                    selected_historical_electricity_demand_per_capita,
                    time_zone,
                )
            )

            # Clean the time series.
            selected_historical_electricity_demand_per_capita = (
                utils.time_series.clean_data(
                    selected_historical_electricity_demand_per_capita,
                    "Annual electricity demand per capita (kWh/person)",
                )
            )

            # Save the electricity demand per capita data to parquet
            # and CSV files.
            selected_historical_electricity_demand_per_capita.to_frame().to_parquet(
                file_path_without_ext + ".parquet"
            )
            selected_historical_electricity_demand_per_capita.to_csv(
                file_path_without_ext + ".csv",
            )

            logging.info(
                f"Historical annual electricity per capita data for {code} "
                "has been extracted and saved successfully."
            )

        else:
            logging.info(
                f"Historical annual electricity per capita data of {code} "
                "already exists. Skipping retrieval."
            )

        if selected_future_years:
            for scenario in selected_scenarios:
                if not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.parquet"
                ) or not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.csv"
                ):
                    logging.info(
                        f"Extracting future annual electricity demand per "
                        f"capita data for {code} and {scenario}."
                    )

                    # Calculate the future electricity demand per
                    # capita.
                    future_electricity_demand_per_capita = (
                        _get_future_electricity_demand_per_capita(
                            iso_alpha_3_code,
                            scenario,
                            historical_electricity_demand_per_capita.loc[
                                max(available_historical_years)
                            ],
                            available_future_years,
                        )
                    )

                    # Extract the electricity demand per capita for
                    # the selected future years.
                    selected_future_electricity_demand_per_capita = (
                        future_electricity_demand_per_capita[
                            future_electricity_demand_per_capita.index.isin(
                                selected_future_years
                            )
                        ]
                    )

                    # Convert the future electricity demand per capita
                    # data from yearly to hourly values.
                    selected_future_electricity_demand_per_capita = (
                        utils.time_series.convert_from_yearly_to_hourly(
                            selected_future_electricity_demand_per_capita,
                            time_zone,
                        )
                    )

                    # Clean the time series.
                    selected_future_electricity_demand_per_capita = utils.time_series.clean_data(
                        selected_future_electricity_demand_per_capita,
                        "Annual electricity demand per capita (kWh/person)",
                    )

                    # Save the electricity demand per capita data to
                    # parquet and CSV files.
                    selected_future_electricity_demand_per_capita.to_frame().to_parquet(
                        f"{file_path_without_ext}_{scenario}.parquet"
                    )
                    selected_future_electricity_demand_per_capita.to_csv(
                        f"{file_path_without_ext}_{scenario}.csv",
                    )

                else:
                    logging.info(
                        f"Future annual electricity demand per capita data "
                        f"for {code} and {scenario} already exists. "
                        "Skipping retrieval."
                    )

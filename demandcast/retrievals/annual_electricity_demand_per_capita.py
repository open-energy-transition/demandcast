"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    annual electricity demand per capita data from Ember and the World
    Bank, and to calculate future annual electricity demand per capita
    based on growth rates from the IAMC scenarios. The electricity
    demand data is extracted for the countries and subdivisions of
    interest and saved into CSV and Parquet files.

    The two historical sources define the demand differently. The
    demand of Ember is the electricity generated and imported, less the
    exports, so it includes the losses of the networks, as the demand
    that the system operators measure does. The electric power
    consumption of the World Bank (EG.USE.ELEC.KH.PC, from the IEA) is
    the production of the power plants less the losses of transmission,
    distribution and transformation and the own use of the plants, so
    it is lower: Ember is 12% higher than the World Bank in the median
    country, and 6% to 18% in half of them. Averaging them gave a value
    between the two definitions that jumped when one of them was
    missing, such as by 11% for India in 2024. Ember gives the value,
    then, and the World Bank fills the countries and years that Ember
    does not have (before 2000, and about 46 countries), times the
    ratio of Ember to the World Bank of the country in the years that
    both have, or the median of these ratios for a country without such
    years.

    The growth rates of the scenarios are those of the final energy of
    electricity per capita (Final Energy|Electricity per capita), which
    leaves out the losses as the World Bank does, so their projections
    from the demand of Ember assume that the share of the losses stays
    the same.
"""

import logging
import os
from typing import cast

import numpy as np
import pandas as pd
import utils.config
import utils.entities
import utils.scenarios
import utils.time_series
from tqdm import tqdm

from retrievals.socio_economic_data_sources import ember, iiasa, world_bank

# The years that Ember and the World Bank both need for the ratio of a
# country.
MIN_YEARS_OF_BOTH = 3


def get_available_scenarios() -> list[str]:
    """
    Get the available future scenarios.

    Returns
    -------
    list[str]
        The available IAMC scenarios.
    """
    return [
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


def get_historical_data() -> pd.DataFrame:
    """
    Get historical electricity demand per capita data.

    The demand per capita of Ember is completed by that of the World
    Bank, times the ratio of Ember to the World Bank of each country,
    since the World Bank leaves out the losses of the networks.

    Returns
    -------
    pandas.DataFrame
        The historical electricity demand per capita data in kWh, by
        country code (rows) and year (columns).
    """
    # Download the electricity demand per capita from Ember.
    ember_electricity_demand_per_capita = (
        ember.download_electricity_demand_per_capita()
    )

    # Download the electricity demand per capita from the World Bank.
    world_bank_electricity_demand_per_capita = world_bank.download(
        "electricity_demand_per_capita"
    )

    # The ratio of Ember to the World Bank of each country, the median
    # of the years that both have, if there are enough of them, or the
    # median of the countries.
    ratios = (
        ember_electricity_demand_per_capita
        / world_bank_electricity_demand_per_capita
    ).replace([np.inf, -np.inf], np.nan)
    country_ratios = ratios.median(axis=1).where(
        ratios.count(axis=1) >= MIN_YEARS_OF_BOTH
    )
    country_ratios = country_ratios.reindex(
        world_bank_electricity_demand_per_capita.index
    ).fillna(country_ratios.median())

    # Fill the countries and years that Ember does not have with the
    # World Bank, scaled to Ember.
    return ember_electricity_demand_per_capita.combine_first(
        world_bank_electricity_demand_per_capita.mul(country_ratios, axis=0)
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
    result_directory = utils.config.read_folders_structure()[
        "annual_electricity_demand_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the historical electricity demand per capita data.
    global_historical_electricity_demand_per_capita = get_historical_data()

    # Read the growth rates of future electricity demand per capita.
    global_future_electricity_demand_per_capita_growth_rates = iiasa.read(
        "annual_electricity_demand_per_capita"
    )

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    # Get the available scenarios.
    available_scenarios = get_available_scenarios()

    # Loop over the countries and subdivisions.
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        # Get the ISO Alpha-3 code of the country itself or the country
        # to which the subdivision belongs.
        iso_alpha_3_code = entity_code.split("_")[0]

        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(entity_code)

        # Extract the electricity data for the country.
        historical_electricity_demand_per_capita = cast(
            pd.Series,
            global_historical_electricity_demand_per_capita.loc[
                iso_alpha_3_code
            ],
        ).dropna()

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
        file_path_without_ext = os.path.join(result_directory, entity_code)

        # Get the selected historical years.
        selected_historical_years = list(
            {year for year, scenario in year_scenario_list if scenario is None}
        )

        # Get the selected future years.
        selected_future_years = list(
            {
                year
                for year, scenario in year_scenario_list
                if scenario is not None
            }
        )

        # Get the selected scenarios.
        selected_scenarios = list(
            {
                scenario
                for __, scenario in year_scenario_list
                if scenario is not None
            }
        )

        if selected_historical_years:
            if not os.path.exists(
                file_path_without_ext + ".parquet"
            ) or not os.path.exists(file_path_without_ext + ".csv"):
                logging.info(
                    "Extracting historical annual electricity per capita data "
                    f"for {entity_code}."
                )

                # Extract the respective electricity demand per capita.
                selected_historical_electricity_demand_per_capita = (
                    historical_electricity_demand_per_capita[
                        historical_electricity_demand_per_capita.index.isin(
                            selected_historical_years
                        )
                    ]
                )

                # Convert the historical electricity demand per capita
                # data from yearly to hourly values.
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
                        "Annual electricity demand per capita (kWh)",
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
                    "Historical annual electricity per capita data for "
                    f"{entity_code} "
                    "has been extracted and saved successfully."
                )

            else:
                logging.info(
                    "Historical annual electricity per capita data of "
                    f"{entity_code} "
                    "already exists. Skipping retrieval."
                )

        if selected_future_years:
            for selected_scenario in selected_scenarios:
                # Define the file path of the scenario data, with the
                # file name that assemble.py reads.
                scenario_file_path_without_ext = (
                    f"{file_path_without_ext}_"
                    f"{selected_scenario.replace('-', '_')}"
                )

                if not os.path.exists(
                    scenario_file_path_without_ext + ".parquet"
                ) or not os.path.exists(
                    scenario_file_path_without_ext + ".csv"
                ):
                    logging.info(
                        f"Extracting future annual electricity demand per "
                        f"capita data for {entity_code} and "
                        f"{selected_scenario}."
                    )

                    # Get the last year and value of the historical
                    # electricity demand per capita.
                    last_historical_year = max(available_historical_years)
                    last_historical_value = (
                        historical_electricity_demand_per_capita.loc[
                            last_historical_year
                        ]
                    )

                    # Calculate the future electricity demand per
                    # capita.
                    future_electricity_demand_per_capita = iiasa.extrapolate(
                        global_future_electricity_demand_per_capita_growth_rates,
                        iso_alpha_3_code,
                        selected_scenario,
                        last_historical_value,
                        last_historical_year,
                        available_future_years,
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
                    selected_future_electricity_demand_per_capita = (
                        utils.time_series.clean_data(
                            selected_future_electricity_demand_per_capita,
                            "Annual electricity demand per capita (kWh)",
                        )
                    )

                    # Save the electricity demand per capita data to
                    # parquet and CSV files.
                    selected_future_electricity_demand_per_capita.to_frame().to_parquet(
                        scenario_file_path_without_ext + ".parquet"
                    )
                    selected_future_electricity_demand_per_capita.to_csv(
                        scenario_file_path_without_ext + ".csv",
                    )

                    logging.info(
                        f"Future annual electricity demand per capita data "
                        f"for {entity_code} and {selected_scenario} has been "
                        "extracted "
                        "and saved successfully."
                    )

                else:
                    logging.info(
                        f"Future annual electricity demand per capita data "
                        f"for {entity_code} and {selected_scenario} already "
                        "exists. "
                        "Skipping retrieval."
                    )

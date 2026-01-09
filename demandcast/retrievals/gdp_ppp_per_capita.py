# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    GDP PPP per capita data from the World Bank and the International
    Monetary Fund (IMF), as well as to calculate future GDP PPP per
    capita based on growth rates from the IAMC scenarios. The data is
    extracted for specified countries and subdivisions and saved into
    CSV and Parquet files.
"""

import logging
import os

import cpi
import pandas
import utils.config
import utils.entities
import utils.geospatial
import utils.scenarios
import utils.time_series
from tqdm import tqdm

import retrievals.socio_economic_data_sources.iiasa as iiasa
import retrievals.socio_economic_data_sources.imf as imf
import retrievals.socio_economic_data_sources.world_bank as world_bank


def get_historical_data() -> pandas.DataFrame:
    """
    Get the historical GDP PPP per capita data.

    This function downloads the historical GDP PPP per capita data
    from the World Bank and the IMF, merges them, and returns the
    combined DataFrame.

    Returns
    -------
    pandas.DataFrame
        The historical GDP PPP per capita data.
    """
    # Download the historical GDP PPP per capita from the World Bank.
    world_bank_gdp_ppp_per_capita = world_bank.download("gdp_ppp_per_capita")

    # Download the historical GDP PPP per capita from the IMF.
    imf_gdp_ppp_per_capita = imf.download_gdp_ppp_per_capita()

    # Merge the two datasets by averaging them.
    gdp_ppp_per_capita = (
        world_bank_gdp_ppp_per_capita + imf_gdp_ppp_per_capita
    ) / 2

    # Limit the data up to the year before the current year.
    gdp_ppp_per_capita = gdp_ppp_per_capita.loc[
        :, : pandas.Timestamp.now().year - 1
    ]

    # Where the combined DataFrame is NaN because one of the datasets is
    # missing, use the other dataset.
    return gdp_ppp_per_capita.fillna(world_bank_gdp_ppp_per_capita).fillna(
        imf_gdp_ppp_per_capita
    )


def _get_gdp_ppp_per_capita_from_gridded_data(
    code: str,
    selected_years: list[int],
    available_years_of_gridded_data: list[int],
    last_available_historical_years_of_gridded_data: int | None = None,
    scenario: str | None = None,
) -> pandas.Series:
    """
    Get the GDP PPP per capita by aggregating gridded data.

    This function calculates the GDP PPP per capita for a given country
    or subdivision by aggregating gridded GDP PPP and population data.
    The GDP PPP per capita is calculated as the total GDP PPP divided
    by the total population for the specified years.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    selected_years : list[int]
        The years for which the GDP PPP per capita is to be calculated.
    available_years_of_gridded_data : list[int]
        The years for which gridded GDP PPP and population data are
        available.
    last_available_historical_years_of_gridded_data :
        int | None, optional
        The last available historical year for gridded data.
    scenario : str | None, optional
        The scenario for which the GDP PPP per capita is to be
        calculated. If None, historical data is used.

    Returns
    -------
    pandas.Series
        The GDP PPP per capita for the specified years.
    """
    # Get the total GDP PPP from gridded data.
    gdp_ppp = utils.geospatial.get_total_value_from_gridded_data(
        "gdp_ppp",
        code,
        selected_years,
        available_years_of_gridded_data,
        last_available_historical_years_of_gridded_data,
        scenario,
    )

    # Convert GDP PPP, which is in constant 2005 international $, to
    # constant 2021 international $, which is the unit used by the World
    # Bank and the IMF.
    gdp_ppp = gdp_ppp.apply(lambda x: cpi.inflate(x, 2005, to=2021))

    # Get the total population from gridded data.
    population = utils.geospatial.get_total_value_from_gridded_data(
        "population",
        code,
        selected_years,
        available_years_of_gridded_data,
        last_available_historical_years_of_gridded_data,
        scenario,
    )

    # Calculate the GDP PPP per capita.
    return gdp_ppp / population


def _extract_historical_gdp_ppp_per_capita(
    code: str,
    iso_alpha_3_code: str,
    global_historical_gdp_ppp_per_capita: pandas.DataFrame,
    requested_historical_years: list[int],
    used_historical_years: list[int],
    available_historical_years_of_gridded_data: list[int],
) -> pandas.Series:
    """
    Extract the historical GDP PPP per capita for a country.

    This function extracts the historical GDP PPP per capita for a
    given country from the global historical GDP PPP per capita data.
    If the country is not found in the global data, it calculates the
    GDP PPP per capita by aggregating gridded data.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country itself or the country to
        which the subdivision belongs.
    global_historical_gdp_ppp_per_capita : pandas.DataFrame
        The global historical GDP PPP per capita data.
    years_and_scenarios : dict[str, list[int] | dict[str, list[int]]]
        The years and scenarios dictionary for the country.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.

    Returns
    -------
    pandas.Series
        The historical GDP PPP per capita for the country.
    """
    # Check if the ISO Alpha-3 code is in the historical
    # GDP PPP per capita data.
    if iso_alpha_3_code in global_historical_gdp_ppp_per_capita.index:
        # Get the historical GDP PPP per capita for the
        # country of interest.
        historical_gdp_ppp_per_capita = (
            global_historical_gdp_ppp_per_capita.loc[iso_alpha_3_code]
        ).dropna()
    else:
        # Interpolate the historical GDP PPP per capita from
        # gridded data.
        historical_gdp_ppp_per_capita = (
            _get_gdp_ppp_per_capita_from_gridded_data(
                code,
                used_historical_years,
                available_historical_years_of_gridded_data,
            )
        )

    # Map the requested historical years to the used (available)
    # historical years. This is used when the requested years are not
    # all available in the historical data.
    return (
        historical_gdp_ppp_per_capita.reindex(used_historical_years)
    ).set_axis(
        requested_historical_years,
    )


def _extract_future_gdp_ppp_per_capita(
    code: str,
    iso_alpha_3_code: str,
    global_future_gdp_ppp_per_capita: pandas.DataFrame,
    future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    available_historical_years_of_gridded_data: list[int],
    scenario: str,
) -> pandas.Series:
    """
    Extract the future GDP PPP per capita for a country.

    This function extracts the future GDP PPP per capita for a given
    country and scenario from the global future GDP PPP per capita data.
    If the country is not found in the global data, it calculates the
    GDP PPP per capita by aggregating gridded data.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country itself or the country to
        which the subdivision belongs.
    global_future_gdp_ppp_per_capita : pandas.DataFrame
        The global future GDP PPP per capita data.
    years_and_scenarios : dict[str, list[int] | dict[str, list[int]]]
        The years and scenarios dictionary for the country.
    available_future_years_of_gridded_data : list[int]
        The available future years for gridded data.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.
    scenario : str
        The scenario for which the GDP PPP per capita is to be
        extracted.

    Returns
    -------
    pandas.Series
        The future GDP PPP per capita for the country.
    """
    # Check if the ISO Alpha-3 code is in the future
    # GDP PPP per capita data.
    if iso_alpha_3_code in global_future_gdp_ppp_per_capita.index:
        # Get the future GDP PPP per capita for the country and scenario
        # of interest.
        future_gdp_ppp_per_capita = iiasa.extract_and_interpolate(
            global_future_gdp_ppp_per_capita,
            iso_alpha_3_code,
            scenario,
        )
    else:
        # Extract the future GDP PPP per capita by aggregating gridded
        # data.
        future_gdp_ppp_per_capita = _get_gdp_ppp_per_capita_from_gridded_data(
            code,
            future_years,
            available_future_years_of_gridded_data,
            available_historical_years_of_gridded_data[-1],
            scenario,
        )

    return future_gdp_ppp_per_capita


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract GDP PPP per capita data.

    This function downloads and extracts historical GDP PPP per capita
    data from the World Bank and calculates future GDP PPP per capita
    based on growth rates from the IAMC scenarios. The data is
    extracted for the countries and subdivisions of interest and saved
    into CSV and Parquet files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the GDP PPP per capita data to be retrieved.
    start_year : int | None
        The start year of the range of GDP PPP per capita data to be
        retrieved.
    end_year : int | None
        The end year of the range of GDP PPP per capita data to be
        retrieved.
    scenario : str | None
        The scenario of the GDP PPP per capita data to be retrieved.
    """
    # Get the directory to store the GDP PPP per capita data.
    result_directory = utils.config.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the historical GDP PPP per capita.
    global_historical_gdp_ppp_per_capita = get_historical_data()

    # Read the future GDP PPP per capita data.
    global_future_gdp_ppp_per_capita = iiasa.read("gdp_ppp_per_capita")

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "all_data", code=code, file_path=file
    )

    # Define the available years for gridded GDP PPP and population
    # data.
    available_historical_years_of_gridded_data = list(range(2000, 2021, 5))
    available_future_years_of_gridded_data = list(range(2025, 2101, 5))

    # Define the available scenarios for the GDP PPP per capita data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Loop over the countries and subdivisions.
    for code in tqdm(codes, desc="Countries and subdivisions"):
        # Get the ISO Alpha-3 code of the country itself or the country
        # to which the subdivision belongs.
        iso_alpha_3_code = code.split("_")[0]

        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Get the years and scenarios dictionary for the country or
        # subdivision of interest.
        (
            requested_historical_years,
            used_historical_years,
            future_years,
            scenarios,
        ) = utils.scenarios.get_years_and_scenarios(
            iso_alpha_3_code,
            year,
            start_year,
            end_year,
            scenario,
            available_scenarios,
            global_historical_gdp_ppp_per_capita,
            available_historical_years_of_gridded_data,
        )

        # Define the file path of the GDP PPP per capita data without
        # the file extension.
        file_path_without_ext = os.path.join(result_directory, code)

        if requested_historical_years:
            if not os.path.exists(
                file_path_without_ext + ".parquet"
            ) or not os.path.exists(file_path_without_ext + ".csv"):
                logging.info(
                    f"Processing historical GDP PPP per capita data for {code}."
                )

                # Extract the historical GDP PPP per capita data for the
                # country or subdivision of interest.
                historical_gdp_ppp_per_capita = (
                    _extract_historical_gdp_ppp_per_capita(
                        code,
                        iso_alpha_3_code,
                        global_historical_gdp_ppp_per_capita,
                        requested_historical_years,
                        used_historical_years,
                        available_historical_years_of_gridded_data,
                    )
                )

                # Extract the historical GDP PPP per capita for the
                # selected years.
                selected_historical_gdp_ppp_per_capita = (
                    historical_gdp_ppp_per_capita.loc[
                        historical_gdp_ppp_per_capita.index.isin(
                            requested_historical_years
                        )
                    ]
                )

                # Convert the historical GDP PPP per capita data from
                # yearly to hourly values.
                selected_historical_gdp_ppp_per_capita = (
                    utils.time_series.convert_from_yearly_to_hourly(
                        selected_historical_gdp_ppp_per_capita,
                        time_zone,
                    )
                )

                # Clean the time series.
                selected_historical_gdp_ppp_per_capita = (
                    utils.time_series.clean_data(
                        selected_historical_gdp_ppp_per_capita,
                        "GDP PPP per capita (2021 international $)",
                    )
                )

                # Save the historical GDP PPP per capita data to CSV and
                # Parquet files.
                selected_historical_gdp_ppp_per_capita.to_frame().to_parquet(
                    file_path_without_ext + ".parquet",
                )
                selected_historical_gdp_ppp_per_capita.to_csv(
                    file_path_without_ext + ".csv",
                )

                logging.info(
                    f"Historical GDP PPP per capita data for {code} has been "
                    "extracted and saved successfully."
                )
            else:
                logging.info(
                    f"Historical GDP PPP per capita data for {code} already "
                    "exists. Skipping extraction."
                )

        if future_years:
            for scenario in scenarios:
                if not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.parquet"
                ) or not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.csv"
                ):
                    logging.info(
                        f"Processing future GDP PPP per capita data for "
                        f"{code} and scenario {scenario}."
                    )

                    # Extract the future GDP PPP per capita data for
                    # the country or subdivision of interest.
                    future_gdp_ppp_per_capita = (
                        _extract_future_gdp_ppp_per_capita(
                            code,
                            iso_alpha_3_code,
                            global_future_gdp_ppp_per_capita,
                            future_years,
                            available_future_years_of_gridded_data,
                            available_historical_years_of_gridded_data,
                            scenario,
                        )
                    )

                    # Extract the future GDP PPP per capita for the
                    # selected years.
                    selected_future_gdp_ppp_per_capita = (
                        future_gdp_ppp_per_capita.loc[
                            future_gdp_ppp_per_capita.index.isin(future_years)
                        ]
                    )

                    # Convert the future GDP PPP per capita data from
                    # yearly to hourly values.
                    selected_future_gdp_ppp_per_capita = (
                        utils.time_series.convert_from_yearly_to_hourly(
                            selected_future_gdp_ppp_per_capita,
                            time_zone,
                        )
                    )

                    # Clean the time series.
                    selected_future_gdp_ppp_per_capita = (
                        utils.time_series.clean_data(
                            selected_future_gdp_ppp_per_capita,
                            "GDP PPP per capita (2021 international $)",
                        )
                    )

                    # Save the future GDP PPP per capita data to CSV and
                    # Parquet files.
                    selected_future_gdp_ppp_per_capita.to_frame().to_parquet(
                        f"{file_path_without_ext}_{scenario}.parquet",
                    )
                    selected_future_gdp_ppp_per_capita.to_csv(
                        f"{file_path_without_ext}_{scenario}.csv",
                    )
                    logging.info(
                        f"Future GDP PPP per capita data for {code} and "
                        f"scenario {scenario} has been extracted "
                        "and saved successfully."
                    )

                else:
                    logging.info(
                        f"Future GDP PPP per capita data for {code} and "
                        f"scenario {scenario} already exists. "
                        "Skipping extraction."
                    )

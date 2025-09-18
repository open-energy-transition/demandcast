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

    Source: https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.CD
    Source: https://www.imf.org/external/datamapper/PPPPC@WEO/OEMDC/ADVEC/WEOWORLD
    Source: https://tntcat.iiasa.ac.at/SspDb
"""  # noqa: W505

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
from tqdm import tqdm


def download_historical_gdp_ppp_per_capita_from_world_bank() -> (
    pandas.DataFrame
):
    """
    Download historical GDP PPP per capita data from the World Bank.

    Returns
    -------
    gdp_ppp_per_capita : pandas.DataFrame
        The historical GDP PPP per capita data from the World Bank.
    """
    logging.info("Downloading GDP PPP per capita data from the World Bank.")

    # Define the URL to download the GDP PPP per capita data.
    url = "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.PP.CD?downloadformat=csv"  # noqa: W505

    # Download the data from the World Bank.
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

        # Read the GDP PPP per capita from the archive.
        gdp_ppp_per_capita = pandas.read_csv(
            archive.open(world_bank_file_name), skiprows=4
        )

        # Set the index to the country code.
        gdp_ppp_per_capita = gdp_ppp_per_capita.set_index("Country Code")

        # Keep only the columns that are digits (i.e., years).
        gdp_ppp_per_capita = gdp_ppp_per_capita.iloc[
            :, gdp_ppp_per_capita.columns.str.isdigit()
        ]

        # Convert to the correct data types.
        gdp_ppp_per_capita.columns = gdp_ppp_per_capita.columns.astype(int)
        gdp_ppp_per_capita.index = gdp_ppp_per_capita.index.astype(str)
        gdp_ppp_per_capita = gdp_ppp_per_capita.astype(float)

        # Rename the columns.
        gdp_ppp_per_capita.columns.name = "Year"

    logging.info(
        "GDP PPP per capita data from the World Bank has been downloaded"
        "successfully."
    )

    return gdp_ppp_per_capita


def download_historical_gdp_ppp_per_capita_from_imf() -> pandas.DataFrame:
    """
    Download historical GDP PPP per capita data from the IMF.

    Returns
    -------
    pandas.DataFrame
        The historical GDP PPP per capita data from the IMF.
    """
    logging.info("Downloading GDP PPP per capita data from the IMF.")

    # Define the URL to download the GDP PPP per capita data.
    url = "https://www.imf.org/external/datamapper/api/v1/PPPPC"

    # Download the data from the IMF.
    imf_gdp_ppp_per_capita = pandas.DataFrame(
        pandas.read_json(url).loc["PPPPC"].loc["values"]
    )

    # Switch the rows with columns.
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.T

    # Convert to the correct data types.
    imf_gdp_ppp_per_capita.columns = imf_gdp_ppp_per_capita.columns.astype(int)
    imf_gdp_ppp_per_capita.index = imf_gdp_ppp_per_capita.index.astype(str)
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.astype(float)

    # Rename the index and columns.
    imf_gdp_ppp_per_capita.index.name = "Country Code"
    imf_gdp_ppp_per_capita.columns.name = "Year"

    logging.info(
        "GDP PPP per capita data from the IMF has been downloaded "
        "successfully."
    )

    return imf_gdp_ppp_per_capita


def extract_historical_gdp_ppp_per_capita(
    world_bank_gdp_ppp_per_capita: pandas.DataFrame,
    imf_gdp_ppp_per_capita: pandas.DataFrame,
    iso_alpha_3_code: str,
) -> pandas.Series:
    """
    Extract the historical GDP PPP per capita.

    Parameters
    ----------
    world_bank_gdp_ppp_per_capita : pandas.DataFrame
        The historical GDP PPP per capita data from the World Bank.
    imf_gdp_ppp_per_capita : pandas.DataFrame
        The historical GDP PPP per capita data from the IMF.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.

    Returns
    -------
    pandas.Series
        The historical GDP PPP per capita for the given country.

    Raises
    ------
    ValueError
        If no GDP PPP per capita data is found for the given country.
    """
    if iso_alpha_3_code in world_bank_gdp_ppp_per_capita.index:
        # Extract the GDP PPP per capita from the World Bank for the
        # given country.
        world_bank_gdp_ppp_per_capita_of_country = (
            world_bank_gdp_ppp_per_capita.loc[iso_alpha_3_code].dropna()
        )
    else:
        logging.warning(
            f"GDP PPP per capita data from the World Bank is not "
            f"available for {iso_alpha_3_code}."
        )
        world_bank_gdp_ppp_per_capita_of_country = pandas.Series(dtype=float)

    if iso_alpha_3_code in imf_gdp_ppp_per_capita.index:
        # Extract the GDP PPP per capita from the IMF for the given
        # country.
        imf_gdp_ppp_per_capita_of_country = imf_gdp_ppp_per_capita.loc[
            iso_alpha_3_code
        ].dropna()
    else:
        logging.warning(
            f"GDP PPP per capita data from the IMF is not available for "
            f"{iso_alpha_3_code}."
        )
        imf_gdp_ppp_per_capita_of_country = pandas.Series(dtype=float)

    if (
        world_bank_gdp_ppp_per_capita_of_country.empty
        and imf_gdp_ppp_per_capita_of_country.empty
    ):
        raise ValueError(
            f"No GDP PPP per capita data found for {iso_alpha_3_code}."
        )

    # Combine the two datasets by averaging them.
    gdp_ppp_per_capita_of_country = (
        world_bank_gdp_ppp_per_capita_of_country
        + imf_gdp_ppp_per_capita_of_country
    ) / 2

    # Where the combined series is NaN because one of the datasets is
    # missing, use the other dataset.
    return gdp_ppp_per_capita_of_country.fillna(
        world_bank_gdp_ppp_per_capita_of_country
    ).fillna(imf_gdp_ppp_per_capita_of_country)


def _get_future_gdp_ppp_per_capita_from_iiasa(
    iso_alpha_3_code: str,
    scenario: str,
    last_historical_value: float,
    future_years: list[int],
) -> pandas.Series:
    """
    Get the future GDP PPP per capita from the IIASA dataset.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.
    last_historical_value : float
        The last historical value of the GDP PPP per capita.
    future_years : list[int]
        The list of future years where the GDP PPP per capita data is
        to be calculated.

    Returns
    -------
    pandas.Series
        The future GDP PPP per capita.

    Raises
    ------
    ValueError
        If there is not exactly one row for the region and scenario in
        the GDP PPP per capita data.
    """
    # Define the file path of the future GDP PPP per capita data.
    file_path = os.path.join(
        utils.directories.read_folders_structure()[
            "gdp_ppp_per_capita_folder"
        ],
        "manual_downloads",
        "IAM_gdp_ppp_per_capita_growth.xlsx",
    )

    # Read the annual growth rates.
    annual_growth_rate = pandas.read_excel(
        file_path,
        sheet_name="data",
        index_col=0,
    )

    if iso_alpha_3_code in annual_growth_rate["Region"].to_list():
        # Extract the annual growth rates of the GDP PPP per capita for
        # the country and scenario of interest.
        annual_growth_rate = annual_growth_rate[
            (annual_growth_rate["Region"] == iso_alpha_3_code)
            & (annual_growth_rate["Scenario"] == scenario)
        ]
    else:
        raise ValueError(
            f"GDP PPP per capita growth rate data is not available for "
            f"{iso_alpha_3_code}."
        )

    # Check that there is only one row.
    if len(annual_growth_rate) != 1:
        raise ValueError(
            f"Expected one row for country {iso_alpha_3_code} and scenario "
            f"{scenario}, but got {len(annual_growth_rate)}."
        )

    # Convert to a Series with years as index by selecting only the
    # columns that are digits and dropping NaN values.
    annual_growth_rate = annual_growth_rate.iloc[
        0,
        annual_growth_rate.columns.astype(str).str.isdigit(),
    ].dropna()

    # Calculate the future GDP PPP per capita by applying the annual
    # growth rates to the last historical value.
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
    result_directory = utils.directories.read_folders_structure()[
        "gdp_ppp_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the historical GDP PPP per capita from the World Bank.
    world_bank_gdp_ppp_per_capita = (
        download_historical_gdp_ppp_per_capita_from_world_bank()
    )

    # Download the historical GDP PPP per capita from the IMF.
    imf_gdp_ppp_per_capita = download_historical_gdp_ppp_per_capita_from_imf()

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "shape", code=code, file_path=file
    )

    # Define the available scenarios for the GDP PPP per capita data.
    available_scenarios = ["SSP1", "SSP2", "SSP3", "SSP4", "SSP5"]

    # Loop over the countries and subdivisions.
    for code in tqdm(codes, desc="Countries and subdivisions"):
        # Get the ISO Alpha-3 code of the country.
        iso_alpha_3_code = utils.entities.get_iso_alpha_3_code(code)

        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Extract the historical GDP PPP per capita.
        historical_gdp_ppp_per_capita = extract_historical_gdp_ppp_per_capita(
            world_bank_gdp_ppp_per_capita,
            imf_gdp_ppp_per_capita,
            iso_alpha_3_code,
        )

        # Get the years of available historical data.
        available_historical_years = (
            historical_gdp_ppp_per_capita.index.tolist()
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

        # Define the file path of the GDP PPP per capita data without
        # the file extension.
        file_path_without_ext = os.path.join(result_directory, code)

        # Get the selcted historical years.
        selected_historical_years = list(
            set(
                [
                    year
                    for year, scenario in year_scenario_list
                    if scenario is None
                ]
            )
        )

        # Get the selected future years.
        selected_future_years = list(
            set(
                [
                    year
                    for year, scenario in year_scenario_list
                    if scenario is not None
                ]
            )
        )

        # Get the selected scenarios.
        selected_scenarios = list(
            set(
                [
                    scenario
                    for __, scenario in year_scenario_list
                    if scenario is not None
                ]
            )
        )

        if (
            not os.path.exists(file_path_without_ext + ".parquet")
            or not os.path.exists(file_path_without_ext + ".csv")
        ) and selected_historical_years:
            logging.info(
                f"Extracting historical GDP PPP per capita data for {code}."
            )

            # Extract the selected historical GDP PPP per capita data.
            selected_historical_gdp_ppp_per_capita = (
                historical_gdp_ppp_per_capita.loc[
                    historical_gdp_ppp_per_capita.index.isin(
                        selected_historical_years
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
                    "GDP PPP per capita (current international $)",
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

        if selected_future_years:
            for scenario in selected_scenarios:
                if not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.parquet"
                ) or not os.path.exists(
                    f"{file_path_without_ext}_{scenario}.csv"
                ):
                    logging.info(
                        f"Extracting future GDP PPP per capita data for "
                        f"{code} and scenario {scenario}."
                    )

                    # Get the future GDP PPP per capita for the country
                    # and scenario of interest.
                    future_gdp_ppp_per_capita = (
                        _get_future_gdp_ppp_per_capita_from_iiasa(
                            iso_alpha_3_code,
                            scenario,
                            historical_gdp_ppp_per_capita.loc[
                                max(available_historical_years)
                            ],
                            selected_future_years,
                        )
                    )

                    # Select the future GDP PPP per capita for the
                    # selected years.
                    selected_future_gdp_ppp_per_capita = (
                        future_gdp_ppp_per_capita.loc[
                            future_gdp_ppp_per_capita.index.isin(
                                selected_future_years
                            )
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
                            "GDP PPP per capita (current international $)",
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

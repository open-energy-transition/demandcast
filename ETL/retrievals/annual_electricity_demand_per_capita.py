# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script downloads annual electricity demand data from Ember. It
    then extracts the electricity data for the countries and
    subdivisions of interest and saves it into CSV and Parquet files.
    The year of the electricity data can be specified as a command line
    argument. If no year is provided, the script will use all the years
    of available electricity demand data.

    Source: https://ember-energy.org/data/yearly-electricity-data/
"""

import logging
import os
import zipfile
from io import BytesIO

import pandas
import requests
import utils.directories
import utils.entities


def download_electricity_demand_per_capita_from_ember() -> pandas.DataFrame:
    """
    Download the electricity demand from Ember.

    Returns
    -------
    pandas.DataFrame
        The electricity demand per capita data from Ember.
    """
    # Download the data from the Ember dataset.
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
    Download the electricity demand per capita from the World Bank.

    Returns
    -------
    pandas.DataFrame
        The electricity demand per capita from the World Bank.
    """
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


def extract_electricity_demand_per_capita(
    alpha_3_code: str,
    years_of_interest: list[int],
    ember_electricity_demand_per_capita: pandas.DataFrame,
    world_bank_electricity_demand_per_capita: pandas.DataFrame,
) -> pandas.Series:
    """
    Get the electricity demand per capita.

    Parameters
    ----------
    alpha_3_codes : str
        The ISO alpha-3 code of the country.
    years_of_interest : list[int]
        The years of interest.

    Returns
    -------
    pandas.Series
        The electricity demand per capita.
    """
    # Extract the electricity demand per capita from Ember for the
    # country and for the years of interest.
    ember_electricity_demand_per_capita = ember_electricity_demand_per_capita[
        (ember_electricity_demand_per_capita["ISO 3 code"] == alpha_3_code)
        & (ember_electricity_demand_per_capita["Year"].isin(years_of_interest))
    ]

    # Convert to a Series with years as index, convert MWh to kWh, and
    # return it.
    ember_electricity_demand_per_capita = pandas.Series(
        ember_electricity_demand_per_capita["Value"].to_numpy() * 1000,
        index=ember_electricity_demand_per_capita["Year"],
    )

    # Extract the electricity demand per capita from the World Bank for
    # the country and for the years of interest.
    world_bank_electricity_demand_per_capita = (
        world_bank_electricity_demand_per_capita[
            world_bank_electricity_demand_per_capita["Country Code"]
            == alpha_3_code
        ]
        .iloc[
            0,
            world_bank_electricity_demand_per_capita.columns.isin(
                [str(year) for year in years_of_interest]
            ),
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


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
) -> None:
    """
    Download and extract GDP data.

    This function downloads the annual electricity demand data from
    Ember and extracts the electricity data for the countries and
    subdivisions of interest. The data is saved into CSV and Parquet
    files.

    Parameters
    ----------
    args : argparse.Namespace
        The command line arguments.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "annual_electricity_demand_per_capita_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Download the electricity demand from Ember.
    ember_electricity_demand_per_capita = (
        download_electricity_demand_per_capita_from_ember()
    )

    # Download the electricity demand per capita from the World Bank.
    world_bank_electricity_demand_per_capita = (
        download_electricity_demand_per_capita_from_world_bank()
    )

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the countries and subdivisions.
    for code in codes:
        # Define the file path of the population density data for the
        # country or subdivision.
        file_path = os.path.join(result_directory, f"{code}.parquet")

        if not os.path.exists(file_path):
            logging.info(f"Extracting annual electricity data of {code}.")

            if year is not None:
                # If the year is provided, use it.
                years = [year]
            else:
                # Get the years of available data for the country or
                # subdivision.
                years = utils.entities.get_available_years(code)

            # Get the ISO Alpha-3 code of the country.
            iso_alpha_3_code = utils.entities.get_iso_alpha_3_code(code)

            # Extract the electricity data for the country and years of
            # interest.
            electricity_demand_per_capita = (
                extract_electricity_demand_per_capita(
                    iso_alpha_3_code,
                    years,
                    ember_electricity_demand_per_capita,
                    world_bank_electricity_demand_per_capita,
                )
            )

            # Get the time zone of the country.
            time_zone = utils.entities.get_time_zone(code)

            # Define a new index with hourly frequency in the local time
            # zone.
            index = pandas.date_range(
                start=(
                    f"{str(electricity_demand_per_capita.index.min())}-01-01"
                ),
                end=(
                    f"{str(electricity_demand_per_capita.index.max())}-12-31 "
                    "23:00:00"
                ),
                freq="h",
                tz=time_zone,
            )

            electricity_demand_per_capita = pandas.Series(
                index.year.map(electricity_demand_per_capita), index=index
            )

            # Convert the index to UTC and remove the time zone
            # information.
            electricity_demand_per_capita.index = (
                electricity_demand_per_capita.index.tz_convert(
                    "UTC"
                ).tz_localize(None)
            )

            # Set the index name.
            electricity_demand_per_capita.index.name = "Time (UTC)"

            # Save the electricity demand to parquet and CSV files.
            electricity_demand_per_capita.to_parquet(file_path)
            electricity_demand_per_capita.to_csv(
                file_path.replace(".parquet", ".csv")
            )

            logging.info(
                f"Annual electricity data of {code} has been extracted and "
                "saved successfully."
            )

        else:
            logging.info(
                f"Annual electricity data of {code} already exists. Skipping "
                "download."
            )

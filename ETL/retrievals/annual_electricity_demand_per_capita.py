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

import pandas
import utils.directories
import utils.entities


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

    # Get the list of codes of the countries and subdivisions.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    logging.info("Downloading annual electricity data.")

    # Read the CSV file containing the electricity data
    global_electricity_data = pandas.read_csv(
        "https://storage.googleapis.com/emb-prod-bkt-publicdata/"
        "public-downloads/yearly_full_release_long_format.csv"
    )

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
            country_electricity_data = global_electricity_data[
                (global_electricity_data["ISO 3 code"] == iso_alpha_3_code)
                & (global_electricity_data["Year"].isin(years))
            ]

            # Extract the electricity demand and demand per capita data.
            electricity_demand = pandas.Series(
                country_electricity_data[
                    country_electricity_data["Variable"] == "Demand"
                ]["Value"].values,
                index=country_electricity_data[
                    country_electricity_data["Variable"] == "Demand"
                ]["Year"],
            )
            electricity_demand_per_capita = pandas.Series(
                country_electricity_data[
                    country_electricity_data["Variable"] == "Demand per capita"
                ]["Value"].values,
                index=country_electricity_data[
                    country_electricity_data["Variable"] == "Demand per capita"
                ]["Year"],
            )

            # Get the time zone of the country.
            time_zone = utils.entities.get_time_zone(code)

            # Define a new index with hourly frequency in the local time
            # zone.
            index = pandas.date_range(
                start=f"{str(country_electricity_data['Year'].min())}-01-01",
                end=(
                    f"{str(country_electricity_data['Year'].max())}-12-31 "
                    "23:00:00"
                ),
                freq="h",
                tz=time_zone,
            )

            # Create a DataFrame with the new index.
            country_electricity_data = pandas.DataFrame(index=index)

            # Map the electricity demand and demand per capita data to
            # the new index.
            country_electricity_data["Annual electricity demand (TWh)"] = (
                country_electricity_data.index.year.map(
                    electricity_demand
                ).to_numpy()
            )
            country_electricity_data[
                "Annual electricity demand per capita (MWh)"
            ] = country_electricity_data.index.year.map(
                electricity_demand_per_capita
            ).to_numpy()

            # Convert the index to UTC and remove the time zone
            # information.
            country_electricity_data.index = (
                country_electricity_data.index.tz_convert("UTC").tz_localize(
                    None
                )
            )

            # Set the index name.
            country_electricity_data.index.name = "Time (UTC)"

            # Save the electricity demand to parquet and CSV files.
            country_electricity_data.to_parquet(file_path)
            country_electricity_data.to_csv(
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

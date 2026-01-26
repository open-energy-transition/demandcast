# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module is used to download historical population, electricity
    demand per capita and GDP PPP per capita data from the World Bank.
    The unit for electricity demand per capita is kWh and for GDP PPP
    per capita is 2021 international dollars.

    Source: https://data.worldbank.org/indicator/SP.POP.TOTL
    Source: https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC
    Source: https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD
"""

import logging
import zipfile
from io import BytesIO

import pandas
import requests


def download(variable: str) -> pandas.DataFrame:
    """
    Download historical data from World Bank.

    Parameters
    ----------
    variable : str
        The variable to download. It can be either "population",
        "electricity_demand_per_capita" or "gdp_ppp_per_capita".

    Returns
    -------
    world_bank_data : pandas.DataFrame
        The historical data from the World Bank.

    Raises
    ------
    ValueError
        If the variable is not "population",
        "electricity_demand_per_capita" or "gdp_ppp_per_capita".
    """
    if variable == "population":
        logging.info("Downloading population data from the World Bank.")

        # Define the URL to download the population data.
        url = "https://api.worldbank.org/v2/en/indicator/SP.POP.TOTL?downloadformat=csv"  # noqa: W505
    elif variable == "electricity_demand_per_capita":
        logging.info(
            "Downloading electricity demand per capita data from the World "
            "Bank."
        )

        # Define the URL to download the electricity demand per capita
        # data.
        url = "https://api.worldbank.org/v2/en/indicator/EG.USE.ELEC.KH.PC?downloadformat=csv"  # noqa: W505
    elif variable == "gdp_ppp_per_capita":
        logging.info(
            "Downloading GDP PPP per capita data from the World Bank."
        )

        # Define the URL to download the GDP PPP per capita data.
        url = "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.PP.KD?downloadformat=csv"  # noqa: W505
    else:
        raise ValueError(
            "The variable must be 'population', "
            "'electricity_demand_per_capita' or 'gdp_ppp_per_capita'."
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

        # Read the electricity demand per capita from the archive.
        world_bank_data = pandas.read_csv(
            archive.open(world_bank_file_name), skiprows=4
        )

        # Set the index to the country code.
        world_bank_data = world_bank_data.set_index("Country Code")

        # Keep only the columns that are digits (i.e., years).
        world_bank_data = world_bank_data.iloc[
            :, world_bank_data.columns.str.isdigit()
        ]

        # Convert to the correct data types.
        world_bank_data.columns = world_bank_data.columns.astype(int)
        world_bank_data.index = world_bank_data.index.astype(str)
        world_bank_data = world_bank_data.astype(float)

        # Rename the columns.
        world_bank_data.columns.name = "Year"

    # Remove rows with all NaN values.
    world_bank_data = world_bank_data.dropna(how="all")

    # Remove rows with country codes that are not three letters long.
    world_bank_data = world_bank_data[world_bank_data.index.str.len() == 3]

    if variable == "population":
        logging.info(
            "Population data from the World Bank has been downloaded "
            "successfully."
        )
    elif variable == "electricity_demand_per_capita":
        logging.info(
            "Electricity demand per capita data from the World Bank has been "
            "downloaded successfully."
        )
    elif variable == "gdp_ppp_per_capita":
        logging.info(
            "GDP PPP per capita data from the World Bank has been downloaded "
            "successfully."
        )

    return world_bank_data

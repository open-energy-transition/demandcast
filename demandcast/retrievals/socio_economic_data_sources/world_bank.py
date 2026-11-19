"""
License: AGPL-3.0.

Description:

    This module downloads the historical population, electricity
    demand per capita (in kWh) and GDP PPP per capita (in 2021
    international dollars) of the countries from the World Bank.

    Source: https://data.worldbank.org/indicator/SP.POP.TOTL
    Source: https://data.worldbank.org/indicator/EG.USE.ELEC.KH.PC
    Source: https://data.worldbank.org/indicator/NY.GDP.PCAP.PP.KD
"""

import logging
import zipfile
from io import BytesIO

import pandas as pd
import requests


def download(variable: str) -> pd.DataFrame:
    """
    Download historical data from the World Bank.

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
        "electricity_demand_per_capita" or "gdp_ppp_per_capita", or if
        the archive of the World Bank has no data file or no file of
        the countries.

    Notes
    -----
    The archive of the World Bank has the data in the CSV file whose
    name does not start with "Metadata", after four lines of header,
    with a column for each year. Its file "Metadata_Country" gives the
    region of each code: the aggregates, such as WLD for the world,
    have none and are left out. An error of the World Bank raises a
    requests.HTTPError.
    """
    if variable == "population":
        logging.info("Downloading population data from the World Bank.")

        url = "https://api.worldbank.org/v2/en/indicator/SP.POP.TOTL?downloadformat=csv"
    elif variable == "electricity_demand_per_capita":
        logging.info(
            "Downloading electricity demand per capita data from the World "
            "Bank."
        )

        url = "https://api.worldbank.org/v2/en/indicator/EG.USE.ELEC.KH.PC?downloadformat=csv"
    elif variable == "gdp_ppp_per_capita":
        logging.info(
            "Downloading GDP PPP per capita data from the World Bank."
        )

        url = "https://api.worldbank.org/v2/en/indicator/NY.GDP.PCAP.PP.KD?downloadformat=csv"
    else:
        raise ValueError(
            "The variable must be 'population', "
            "'electricity_demand_per_capita' or 'gdp_ppp_per_capita'."
        )

    response = requests.get(url, timeout=60)
    response.raise_for_status()

    with zipfile.ZipFile(BytesIO(response.content), "r") as archive:
        world_bank_file_name = next(
            (
                name
                for name in archive.namelist()
                if not name.startswith("Metadata") and name.endswith(".csv")
            ),
            None,
        )
        if world_bank_file_name is None:
            raise ValueError("No data file found in the World Bank archive.")
        countries_file_name = next(
            (
                name
                for name in archive.namelist()
                if name.startswith("Metadata_Country")
            ),
            None,
        )
        if countries_file_name is None:
            raise ValueError(
                "No file of the countries found in the World Bank archive."
            )

        countries = pd.read_csv(archive.open(countries_file_name))
        country_codes = countries.loc[
            countries["Region"].notna(), "Country Code"
        ]

        world_bank_data = pd.read_csv(
            archive.open(world_bank_file_name), skiprows=4
        )

        world_bank_data = world_bank_data.set_index("Country Code")

        world_bank_data = world_bank_data.iloc[
            :, world_bank_data.columns.str.isdigit()
        ]

        world_bank_data.columns = world_bank_data.columns.astype(int)
        world_bank_data.index = world_bank_data.index.astype(str)
        world_bank_data = world_bank_data.astype(float)

        world_bank_data.columns.name = "Year"

    world_bank_data = world_bank_data.dropna(how="all")

    world_bank_data = world_bank_data[
        world_bank_data.index.isin(country_codes)
    ]

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

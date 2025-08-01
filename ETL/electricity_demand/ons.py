# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Operador Nacional do Sistema Elétrico
    (ONS) in Brazil. The data is retrieved for the years from 2000 to
    the current year. The data is retrieved from the available CSV files
    on the ONS website.

    Source: https://dados.ons.org.br/dataset/curva-carga
"""

import logging

import pandas
import utils.entities
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("CC-BY license. Use for any purpose with attribution.")
    logging.debug("Source: https://dados.ons.org.br/dataset/curva-carga")
    return True


def _check_input_parameters(
    year: int | None = None, code: str = "BR_N"
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int, optional
        The year of the data to retrieve.
    code : str, optional
        The code of the subdivision of interest.
    """
    # Check if the code is valid.
    utils.entities.check_code(code, "ons")

    if year is not None:
        # Check if the year is supported.
        assert year in get_available_requests(code), (
            f"The year {year} is not in the supported range."
        )


def get_available_requests(code: str) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the ONS website.

    Parameters
    ----------
    code : str
        The code of the subdivision.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Check if input parameters are valid.
    _check_input_parameters(code=code)

    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="ons")[
        code
    ]

    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if input parameters are valid.
    _check_input_parameters(year=year)

    # Return the URL of the electricity demand data.
    return (
        "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset/"
        f"curva-carga-ho/CURVA_CARGA_{year}.csv"
    )


def download_and_extract_data_for_request(
    year: int, code: str
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the ONS website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year=year, code=code)

    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Extract the subdivision code from the code.
    subdivision_code = code.split("_")[1]

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv", csv_kwargs={"sep": ";"})

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Filter the dataset for the subdivision of interest.
        dataset = dataset[dataset["id_subsistema"] == subdivision_code]

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["val_cargaenergiahomwmed"].values,
            index=pandas.to_datetime(dataset["din_instante"]),
        ).tz_localize("America/Sao_Paulo", ambiguous="NaT", nonexistent="NaT")

        # Add one hour to the time index because the time values appear
        # to be provided at the beginning of the time interval.
        electricity_demand_time_series.index += pandas.Timedelta(hours=1)

        return electricity_demand_time_series

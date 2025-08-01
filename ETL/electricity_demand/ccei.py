# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Canadian Centre for Energy Information
    (CCEI). The data is retrieved from different starting dates
    depending on the subdivision until the current date. The data has
    various time resolutions.

    Source: https://energy-information.canada.ca/en/resources/high-frequency-electricity-data
"""  # noqa: W505

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
    logging.debug("Non-commercial reproduction with attribution to CCEI.")
    logging.debug("Source: https://www.canada.ca/en/transparency/terms.html")
    return True


def get_available_requests(code: str) -> None:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CCEI website.

    Parameters
    ----------
    code : str
        The code of the subdivision.
    """
    # Check if the code is valid.
    utils.entities.check_code(code, "ccei")

    logging.debug("The data is retrieved all at once.")


def get_url(code: str) -> str:
    """
    Get the URL of the electricity demand data on the CCEI website.

    Parameters
    ----------
    subdivision_code : str
        The code of the Province or Territory of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the code is valid.
    utils.entities.check_code(code, "ccei")

    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Define the mapping between the subdivision codes and API variable
    # names.
    variable_names = {
        "AB": ["AB", "INTERNAL_LOAD"],
        "BC": ["BC", "LOAD"],
        "NB": ["NB", "LOAD"],
        "NL": ["NL", "DEMAND"],
        "NS": ["NS", "LOAD"],
        "ON": ["ON", "ONTARIO_DEMAND"],
        "PE": ["PE", "ON_ISL_LOAD"],
        "QC": ["QC", "DEMAND"],
        "SK": ["SK", "SYSTEM_DEMAND"],
        "YT": ["YK", "TOTAL"],
    }

    assert subdivision_code in variable_names.keys(), (
        f"Subdivision code {subdivision_code} is not supported."
    )

    # Return the URL of the electricity demand data.
    return (
        "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
        f"CCEI,DF_HFED_{variable_names[subdivision_code][0]},1.0/"
        f"N...{variable_names[subdivision_code][1]}?"
        "&dimensionAtObservation=AllDimensions&format=csv"
    )


def download_and_extract_data(code: str) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CCEI website.

    Parameters
    ----------
    subdivision_code : str
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
    # Check if the code is valid.
    utils.entities.check_code(code, "ccei")

    # Get the URL of the electricity demand data.
    url = get_url(code)

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        if code == "CA_NB":
            # Remove unknown code from the time step values.
            dataset["TIME_PERIOD"] = dataset["TIME_PERIOD"].str.replace(
                ".000Z", ""
            )
        if code == "CA_ON":
            # Remove dummy time steps where the time is equal to
            # 06:59:59 right before the daylight saving time change.
            dataset = dataset[~dataset["TIME_PERIOD"].str.contains("06:59:59")]

        # Extract the electricity demand time series with UTC time zone.
        electricity_demand_time_series = pandas.Series(
            data=dataset["OBS_VALUE"].values,
            index=pandas.to_datetime(dataset["TIME_PERIOD"]),
        ).tz_localize("UTC")

        return electricity_demand_time_series

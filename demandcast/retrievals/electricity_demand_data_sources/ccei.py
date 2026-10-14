"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Canadian Centre for Energy Information
    (CCEI). The data is retrieved from different starting dates
    depending on the subdivision until the current date. The data has
    various time resolutions.

    Source: https://energy-information.canada.ca/en/resources/high-frequency-electricity-data
"""

import logging

import pandas as pd
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
    utils.entities.check_code_in_data_source(code, "ccei")

    logging.debug("The data is retrieved all at once.")


def get_url(code: str) -> str:
    """
    Get the URL of the electricity demand data on the CCEI website.

    Parameters
    ----------
    code : str
        The code of the Province or Territory of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the subdivision code is not supported.
    """
    # Check if the code is valid.
    utils.entities.check_code_in_data_source(code, "ccei")

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

    if subdivision_code not in variable_names:
        raise ValueError(
            f"Subdivision code {subdivision_code} is not supported."
        )

    # Return the URL of the electricity demand data.
    return (
        "https://api.statcan.gc.ca/hfed-dehf/sdmx/rest/data/"
        f"CCEI,DF_HFED_{variable_names[subdivision_code][0]},1.0/"
        f"N...{variable_names[subdivision_code][1]}?"
        "&dimensionAtObservation=AllDimensions&format=csv"
    )


def download_and_extract_data(code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CCEI website.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the code is valid.
    utils.entities.check_code_in_data_source(code, "ccei")

    # Get the URL of the electricity demand data.
    url = get_url(code)

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv")

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    if code == "CAN_NB":
        # Remove unknown code from the time step values.
        dataset["TIME_PERIOD"] = dataset["TIME_PERIOD"].str.replace(
            ".000Z", ""
        )

    if code == "CAN_ON":
        # The data of Ontario comes from IESO, whose hours end at 1:00
        # to 24:00 in Eastern Standard Time all year. CCEI keeps these
        # times in DATETIME_LOCAL, with the hour 24 at 00:00 of the same
        # day, and converts them to UTC (TIME_PERIOD) as if they
        # followed daylight saving time: an hour early in summer, and a
        # day early at midnight. Read them in Eastern Standard Time
        # (UTC-5), with the hour 24 at midnight of the next day.
        local_times = pd.to_datetime(dataset["DATETIME_LOCAL"])
        local_times += pd.to_timedelta(
            (local_times.dt.hour == 0).astype(int), unit="D"
        )
        times = pd.DatetimeIndex(local_times + pd.Timedelta(hours=5))
    else:
        times = pd.DatetimeIndex(pd.to_datetime(dataset["TIME_PERIOD"]))

    # Extract the electricity demand time series with UTC time zone.
    electricity_demand_time_series = (
        pd.Series(data=dataset["OBS_VALUE"].values, index=times)
        .tz_localize("UTC")
        .sort_index()
    )

    return electricity_demand_time_series

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Ontario's Independent Electricity System
    Operator (IESO) in Canada. The data is retrieved for the years from
    1994 to current year. The data is retrieved from the available CSV
    files on the IESO website.

    Source: https://www.ieso.ca/Power-Data/Data-Directory
    Source: https://reports-public.ieso.ca/public/Demand/
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
    logging.debug(
        "Limited, non-exclusive, non-sublicensable, non-transferrable licence "
        "to use and reproduce."
    )
    logging.debug("Source: https://www.ieso.ca/Terms-of-Use")
    return False


def _check_input_parameters(year: int | None, before_apr_2002: bool) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    before_apr_2002 : bool
        Whether the url is for the time period before April 2002.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Check if the request is supported.
    if (year, before_apr_2002) not in get_available_requests():
        raise ValueError("The request is not available.")


def get_available_requests() -> list[tuple[int | None, bool]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the IESO website.

    Returns
    -------
    list[tuple[int | None, bool]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    __, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "ieso"
        )["CAN_ON"]
    )

    # Define the date that separates the two periods of data.
    date_after_apr_2002 = pd.Timestamp("2002-04-01")

    # Return the available requests, which are a combination of a year
    # number and a boolean indicating whether the data is before April
    # 2002.
    # available_requests = [(year = None, before_apr_2002 = True)
    #                       (year = 2002, before_apr_2002 = False),
    #                       (year = 2003, before_apr_2002 = False),
    #                       ...
    #                       (year = last year, before_apr_2002 = False)]
    return [(None, True)] + [
        (year, False)
        for year in range(date_after_apr_2002.year, end_date.year + 1)
    ]


def get_url(year: int | None, before_apr_2002: bool) -> str:
    """
    Get the URL of the electricity demand data on the IESO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    before_apr_2002 : bool
        Whether the url is for the time period before April 2002.

    Returns
    -------
    url : str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year=year, before_apr_2002=before_apr_2002)

    # Define the URL of the electricity demand data.
    if before_apr_2002:
        url = (
            "https://www.ieso.ca/-/media/Files/IESO/Power-Data/data-directory/"
            "HourlyDemands_1994-2002.csv"
        )
    elif year is not None and year >= 2002 and year <= pd.Timestamp.now().year:
        url = (
            "https://reports-public.ieso.ca/public/Demand/"
            f"PUB_Demand_{year}.csv"
        )

    return url


def download_and_extract_data_for_request(
    year: int | None, before_apr_2002: bool
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the IESO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    before_apr_2002 : bool
        Whether the url is for the time period before April 2002.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year=year, before_apr_2002=before_apr_2002)

    # Get the URL of the electricity demand data.
    url = get_url(year=year, before_apr_2002=before_apr_2002)

    if before_apr_2002:
        logging.info(
            "Retrieving electricity demand data for the years 1994 to 2002."
        )

        # Fetch HTML content from the URL.
        dataset = utils.fetcher.fetch_data(
            url,
            "html",
            read_with="requests.get",
            verify_ssl=False,
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pd.DataFrame):
            raise TypeError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pd.Series(
            dataset["OntarioDemand"].values,
            index=pd.to_datetime(dataset["DateTime"]),
        )

        # Convert the time zone of the electricity demand time
        # series to UTC.
        electricity_demand_time_series = (
            electricity_demand_time_series.tz_localize(
                "America/Toronto", ambiguous="NaT", nonexistent="NaT"
            )
        )

        # Add one hour to the time index because the time values
        # appear to be provided at the beginning of the time
        # interval.
        electricity_demand_time_series.index += pd.Timedelta(hours=1)

        return electricity_demand_time_series

    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(url, "csv", csv_kwargs={"skiprows": 3})

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the index of the electricity demand time series.
    index = pd.to_datetime(
        [
            date + " " + str(time - 1) + ":00"
            for date, time in zip(
                dataset["Date"], dataset["Hour"], strict=True
            )
        ]
    ).tz_localize("America/Toronto", ambiguous="NaT", nonexistent="NaT")

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Ontario Demand"].values, index=index
    )

    return electricity_demand_time_series

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Ontario's Independent Electricity System
    Operator (IESO) in Canada. The data is retrieved for the years from
    1994 to current year. The data is retrieved from the available CSV
    files on the IESO website.

    The times of IESO are in Eastern Standard Time all year, without
    daylight saving time, as on the Power Data page below ("Hour Ending
    (EST)").

    Source: https://www.ieso.ca/Power-Data/Data-Directory
    Source: https://reports-public.ieso.ca/public/Demand/
    Source: https://www.ieso.ca/power-data
"""

import datetime
import logging

import pandas as pd
import utils.fetcher

# Eastern Standard Time, the time of IESO all year.
EASTERN_STANDARD_TIME = datetime.timezone(datetime.timedelta(hours=-5))


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


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[int | None, bool]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the IESO website.

    Parameters
    ----------
    code : str
        The code of Ontario.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[int | None, bool]]
        The list of available requests.
    """
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
    year_and_old_file: tuple[int | None, bool], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the IESO website.

    Parameters
    ----------
    year_and_old_file : tuple[int | None, bool]
        The year of the electricity demand data, and whether the data
        is in the file of the time period before April 2002, whose year
        is None.
    code : str
        The code of Ontario.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    year, before_apr_2002 = year_and_old_file

    # Get the URL of the electricity demand data.
    url = get_url(year=year, before_apr_2002=before_apr_2002)

    if before_apr_2002:
        logging.info(
            "Retrieving electricity demand data for the years 1994 to 2002."
        )

        # Fetch HTML content from the URL.
        dataset = utils.fetcher.fetch_data(
            url, "html", read_with="requests.get"
        )

        # Make sure the dataset is a pandas DataFrame.
        if not isinstance(dataset, pd.DataFrame):
            raise TypeError(
                f"The extracted data is a {type(dataset)} object, "
                "expected a pandas DataFrame."
            )

        # Extract the electricity demand time series. The times of 1996
        # have a different format from the other years.
        electricity_demand_time_series = pd.Series(
            dataset["OntarioDemand"].values,
            index=pd.to_datetime(dataset["DateTime"], format="mixed"),
        ).tz_localize(EASTERN_STANDARD_TIME)

        # The times are the starts of the hours: the file ends at 23:00
        # on 30 April 2002, the hour before the first one of the yearly
        # files. Move them to the ends of the hours.
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

    # The hours of each day are numbered from 1 to 24 by their ends, so
    # the hour 24 ends at midnight of the next day.
    index = pd.DatetimeIndex(
        pd.to_datetime(dataset["Date"])
        + pd.to_timedelta(dataset["Hour"], unit="h")
    ).tz_localize(EASTERN_STANDARD_TIME)

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Ontario Demand"].values, index=index
    )

    return electricity_demand_time_series

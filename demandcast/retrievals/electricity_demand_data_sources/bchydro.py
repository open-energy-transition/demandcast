"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the British Columbia Hydro and Power
    Authority (BC Hydro) in Canada. The data is retrieved for the years
    from 2001 to current year. The data is retrieved from the available
    Excel files on the BC Hydro website.

    Source: https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html
"""

import datetime
import logging

import numpy as np
import pandas as pd
import utils.fetcher


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Informational and noncommercial uses offline only.")
    logging.debug("Source: https://www.bchydro.com/siteinfo/legal.html")
    return False


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the BC Hydro website.

    Parameters
    ----------
    code : str
        The code of British Columbia.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Return the available requests, which are the years.
    return list(range(start_date.year, end_date.year + 1))


def get_url(year: int) -> str:
    """
    Get the URL of the electricity demand data on the BC Hydro website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    url : str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the year is not implemented.
    """
    # Define the URL of the electricity demand data.
    url = (
        "https://www.bchydro.com/content/dam/BCHydro/customer-portal/"
        "documents/corporate/suppliers/transmission-system/"
        "balancing_authority_load_data/Historical%20Transmission%20Data/"
    )
    if year == 2001:
        url += "BalancingAuthorityLoadApr-Dec2001.xls"
    elif (
        (year >= 2002 and year <= 2006)
        or year == 2013
        or (year >= 2015 and year <= 2023)
    ):
        url += f"BalancingAuthorityLoad{year}.xls"
    elif (year >= 2007 and year <= 2008) or year == 2014:
        url += f"{year}controlareaload.xls"
    elif year >= 2009 and year <= 2012:
        url += f"jandec{year}controlareaload.xls"
    elif year >= 2024:
        url += f"BalancingAuthorityLoad%20{year}.xls"
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    return url


# Format of the Excel files from each year until the next one, and the
# last one also for the later years: the number of rows to skip, the
# header, the index columns, and the column of the electricity demand
# data.
_EXCEL_FORMATS: dict[
    int, tuple[int, int | None, tuple[str | int, ...], tuple[str | int, ...]]
] = {
    2001: (1, 0, ("Date", "HE"), ("Balancing Authority Load",)),
    2007: (2, None, (0, 1), (2,)),
    2008: (2, 0, ("Date", "HE"), ("MWh",)),
    2012: (3, 0, ("Date ▲", "HE"), ("Control Area Load",)),
    2014: (1, 0, ("Date ▲", "HE"), ("Control Area Load",)),
    2015: (1, 0, ("Date ▲", "HE"), ("Balancing Authority Load",)),
    2016: (1, 0, ("Date", "HE"), ("Balancing Authority Load",)),
    2021: (1, 0, ("Date ?", "HE"), ("Control Area Load",)),
    2022: (3, 0, ("Date ?", "HE"), ("Control Area Load",)),
    2025: (3, 0, ("Date ", "HE"), ("Control Area Load",)),
}


def _get_excel_information(
    year: int,
) -> tuple[int, int | None, list[str | int], list[str | int]]:
    """
    Get the information to read the Excel files.

    This function returns the information needed to read the
    Excel files containing the electricity demand data from the BC Hydro
    website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

    Returns
    -------
    tuple[int, int | None, list[str | int], list[str | int]]
        The number of rows to skip, the header of the Excel file,
        the index columns of the Excel file, and the column of the
        electricity demand data.
    """
    # Return the format of the latest period that starts by the year.
    first_year = max(
        first_year for first_year in _EXCEL_FORMATS if first_year <= year
    )
    rows_to_skip, header, index_columns, load_column = _EXCEL_FORMATS[
        first_year
    ]
    return rows_to_skip, header, list(index_columns), list(load_column)


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the BC  Hydro website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of British Columbia.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    # Get the URL of the electricity demand data.
    url = get_url(year)

    # Get the Excel information of the electricity demand data.
    rows_to_skip, header, index_columns, load_column = _get_excel_information(
        year
    )

    # Fetch HTML content from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "excel",
        excel_kwargs={
            "skiprows": rows_to_skip,
            "header": header,
            "usecols": index_columns + load_column,
        },
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the first and last time steps of the electricity
    # demand time series.
    first_time_step = pd.to_datetime(
        str(dataset[index_columns[0]].iloc[0])
        + " "
        + str(int(dataset[index_columns[1]].iloc[0]) - 1)
        + ":00"
    ) + pd.Timedelta("1h")
    last_time_step = pd.to_datetime(
        str(dataset[index_columns[0]].iloc[-1])
        + " "
        + str(int(dataset[index_columns[1]].iloc[-1]) - 1)
        + ":00"
    ) + pd.Timedelta("1h")

    # Remove NaN and zero values where daylight saving time switch
    # occurs. The other data points are typically nice and clean.
    available_data = dataset[load_column[0]][
        (
            np.logical_and(
                dataset[load_column[0]] != 0,
                dataset[load_column[0]].notna(),
            )
        )
    ]

    # Construct the index of the electricity demand time series.
    timestamps = pd.date_range(
        start=first_time_step,
        end=last_time_step,
        freq="h",
        tz="America/Vancouver",
    )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        available_data.values, index=timestamps
    )

    return electricity_demand_time_series

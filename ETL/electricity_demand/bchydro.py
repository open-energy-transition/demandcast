# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the British Columbia Hydro and Power
    Authority (BC Hydro) in Canada. The data is retrieved for the years
    from 2001 to current year. The data is retrieved from the available
    Excel files on the BC Hydro website.

    Source: https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html
"""  # noqa: W505

import logging

import numpy
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
    logging.debug("Informational and noncommercial uses offline only.")
    logging.debug("Source: https://www.bchydro.com/siteinfo/legal.html")
    return False


def _check_input_parameters(year: int) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    year : int
        The year of the data to retrieve.
    """
    # Check if the year is supported.
    assert year in get_available_requests(), (
        f"The year {year} is not in the supported range."
    )


def get_available_requests() -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the BC Hydro website.

    Returns
    -------
    list[int]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="bchydro"
    )["CA_BC"]

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
    # Check if the input parameters are valid.
    _check_input_parameters(year)

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
    elif year >= 2007 and year <= 2008 or year == 2014:
        url += f"{year}controlareaload.xls"
    elif year >= 2009 and year <= 2012:
        url += f"jandec{year}controlareaload.xls"
    elif year == 2024:
        url += "BalancingAuthorityLoad%202024.xls"
    elif year == 2025:
        url = (
            "https://www.bchydro.com/content/dam/BCHydro/customer-portal/"
            "documents/corporate/suppliers/transmission-system/"
            "actual_flow_data/historical_data/"
            "BalancingAuthorityLoad%202025.xls"
        )
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    return url


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

    Raises
    ------
    ValueError
        If the year is not implemented.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(year)

    # Define the number of rows to skip.
    if (year >= 2001 and year <= 2006) or (year >= 2014 and year <= 2021):
        rows_to_skip = 1
    elif year >= 2007 and year <= 2011:
        rows_to_skip = 2
    elif (year >= 2012 and year <= 2013) or (year >= 2022 and year <= 2025):
        rows_to_skip = 3
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    # Define the header of the Excel file.
    if year == 2007:
        header = None
    elif year >= 2001 and year <= 2006 or year >= 2008 and year <= 2025:
        header = 0
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    # Define the index columns of the Excel file.
    index_columns: list[str | int]
    if (
        (year >= 2001 and year <= 2006)
        or (year >= 2008 and year <= 2011)
        or (year >= 2016 and year <= 2020)
    ):
        index_columns = ["Date", "HE"]
    elif year == 2007:
        index_columns = [0, 1]
    elif year >= 2012 and year <= 2015:
        index_columns = ["Date ▲", "HE"]
    elif year >= 2021 and year <= 2024:
        index_columns = ["Date ?", "HE"]
    elif year == 2025:
        index_columns = ["Date ", "HE"]
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    # Define the column of the electricity demand data.
    load_column: list[str | int]
    if (year >= 2001 and year <= 2006) or (year >= 2015 and year <= 2020):
        load_column = ["Balancing Authority Load"]
    elif year == 2007:
        load_column = [2]
    elif year >= 2008 and year <= 2011:
        load_column = ["MWh"]
    elif year >= 2012 and year <= 2014 or year >= 2021 and year <= 2025:
        load_column = ["Control Area Load"]
    else:
        raise ValueError(f"The year {year} is not implemented yet.")

    return rows_to_skip, header, index_columns, load_column


def download_and_extract_data_for_request(year: int) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the BC  Hydro website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.

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
    _check_input_parameters(year)

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
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Extract the first and last time steps of the electricity
        # demand time series.
        first_time_step = pandas.to_datetime(
            str(dataset[index_columns[0]].iloc[0])
            + " "
            + str(int(dataset[index_columns[1]].iloc[0]) - 1)
            + ":00"
        ) + pandas.Timedelta("1h")
        last_time_step = pandas.to_datetime(
            str(dataset[index_columns[0]].iloc[-1])
            + " "
            + str(int(dataset[index_columns[1]].iloc[-1]) - 1)
            + ":00"
        ) + pandas.Timedelta("1h")

        # Remove NaN and zero values where daylight saving time switch
        # occurs. The other data points are typically nice and clean.
        available_data = dataset[load_column[0]][
            (
                numpy.logical_and(
                    dataset[load_column[0]] != 0,
                    dataset[load_column[0]].notna(),
                )
            )
        ]

        # Construct the index of the electricity demand time series.
        timestamps = pandas.date_range(
            start=first_time_step,
            end=last_time_step,
            freq="h",
            tz="America/Vancouver",
        )

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            available_data.values, index=timestamps
        )

        return electricity_demand_time_series

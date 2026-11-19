"""
License: AGPL-3.0.

Description:

    This module retrieves the electricity demand data from the website
    of the British Columbia Hydro and Power Authority (BC Hydro) in
    Canada. The data is retrieved from the yearly Excel files on the BC
    Hydro website, the file of the current year running until the end
    of a recent month.

    The files give the load of the balancing authority in MWh for each
    hour, the average load in MW, by date and hour ending in local time.
    The rows follow each other in time: the day when daylight saving
    time starts has 23 hours, or 24 with a value of 0 for the hour that
    does not exist, and the day when it ends has 25 hours.

    The balancing authority is BC Hydro's integrated system, without the
    area of Fort Nelson, which the Alberta Interconnected Electric
    System supplies, and the areas off it, such as Haida Gwaii, the
    Central Coast and Atlin.

    Source: https://www.bchydro.com/energy-in-bc/operations/transmission/transmission-system/balancing-authority-load-data/historical-transmission-data.html
"""

import datetime as dt
import logging

import numpy as np
import pandas as pd

import utils.fetcher

# The time zone of the dates and hours of the files.
TIME_ZONE = "America/Vancouver"


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[int]:
    """
    Get the available requests.

    Parameters
    ----------
    code : str
        The code of the integrated system of British Columbia.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[int]
        The years of the data.
    """
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
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the year has no file.
    """
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


# The format of the Excel files from each year until the next one, and
# the last one also for the later years: the number of rows to skip,
# the header, the index columns, and the column of the electricity
# demand data.
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

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of the integrated system of British Columbia.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Notes
    -----
    The hours ending of a day of 24 hours give the times of its values.
    Those of the days when the clocks change differ from year to year,
    such as "2" and "2*" for the repeated hour, or no hour 2 or 3 when
    daylight saving time starts, so the values of such a day are placed
    by their order, if it has a value for each hour, and are skipped
    otherwise.
    """
    logging.info(f"Retrieving electricity demand data for the year {year}.")

    url = get_url(year)

    rows_to_skip, header, index_columns, load_column = _get_excel_information(
        year
    )

    dataset = utils.fetcher.fetch_dataframe(
        url,
        "excel",
        excel_kwargs={
            "skiprows": rows_to_skip,
            "header": header,
            "usecols": index_columns + load_column,
        },
    )

    # Remove the missing values, and the value of 0 of the hour that
    # does not exist when daylight saving time starts.
    values = dataset[load_column[0]]
    days = pd.to_datetime(dataset[index_columns[0]], errors="coerce")
    available = values.notna() & (values != 0) & days.notna()
    values, days = values[available], days[available]
    hours_ending = pd.to_numeric(
        dataset[index_columns[1]][available], errors="coerce"
    ).to_numpy()

    midnights = pd.DatetimeIndex(days).tz_localize(TIME_ZONE)
    day_lengths = (
        (
            pd.DatetimeIndex(days + pd.Timedelta(days=1)).tz_localize(
                TIME_ZONE
            )
            - midnights
        )
        / pd.Timedelta(hours=1)
    ).to_numpy()
    positions = days.groupby(days).cumcount().to_numpy() + 1
    counts = days.groupby(days).transform("size").to_numpy()

    hours = np.where(day_lengths == 24, hours_ending, positions)
    placed = np.where(
        day_lengths == 24,
        (hours_ending >= 1) & (hours_ending <= 24),
        counts == day_lengths,
    )
    if not placed.all():
        logging.warning(
            f"{(~placed).sum()} values of {year} cannot be placed in "
            "time and are skipped."
        )

    electricity_demand_time_series = pd.Series(
        values.to_numpy()[placed],
        index=midnights[placed] + pd.to_timedelta(hours[placed], unit="h"),
    )

    return electricity_demand_time_series

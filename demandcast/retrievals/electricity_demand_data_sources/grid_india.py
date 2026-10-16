"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of the Grid Controller of India (Grid-India) from the dataset
    of Mukherjee, Kalita and Kumar on Mendeley Data, which has the data
    of the North-Eastern Regional Load Despatch Centre of Grid-India
    under the CC BY 4.0 license. The module reads the files of the
    dataset from its API, and downloads one file at a time.

    The dataset has a file for each month from September 2021 to
    December 2023, exported from the SCADA system of Grid-India, and a
    file from January 2024 to June 2025. The months of the files are
    read from their names, by the first three letters of the month, as
    the file of November 2023 is named "Novemeber 2023.xlsx".

    The monthly files give the demand of all India (NLDC_DEMAND), the
    combined demand of the five regional grids, in MW, as readings at
    their times in the time of India, which has no daylight saving
    time: every 5 minutes until December 2022, and every 10 seconds in
    2023, of which the module keeps the readings every 5 minutes. Some
    readings are 0, which the cleaning removes, or far from the demand,
    such as 402 GW in January 2023. The dataset describes its data as
    hourly, but the monthly files are not.

    The file from January 2024 has the hourly demand in MW until
    2025-06-24 23:00, with summary rows at the bottom. Its times are the
    starts of the hours: compared with the data of NITI from January to
    April 2024, the demand matches best one hour later.

    Source: https://data.mendeley.com/datasets/y58jknpgs8/2
"""

import datetime
import logging
import re

import pandas as pd
import utils.fetcher
import utils.time_series

# The identifier of the dataset on Mendeley Data.
DATASET_ID = "y58jknpgs8"

# The SCADA tag of the demand of all India in the monthly files.
DEMAND_TAG = "SCADA/ANALOG/044MQ067/0"


def _read_periods(file_name: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Read the period of a file of the dataset from its name.

    Parameters
    ----------
    file_name : str
        The name of the file, such as "September 2021.xlsx" or
        "January 2024- June 2025.xlsx".

    Returns
    -------
    tuple[pandas.Timestamp, pandas.Timestamp]
        The first day of the first month and the last day of the last
        month of the file.

    Raises
    ------
    ValueError
        If the name has no month and year.
    """
    months = re.findall(r"([A-Za-z]{3})[A-Za-z]* (\d{4})", file_name)
    if not months:
        raise ValueError(f"The file {file_name} of Grid-India has no month.")
    first_month = pd.Period(" ".join(months[0]), freq="M")
    last_month = pd.Period(" ".join(months[-1]), freq="M")
    return first_month.start_time, last_month.end_time.normalize()


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    """
    Get the available requests.

    This function reads the files of the dataset from the API of
    Mendeley Data and keeps those with data between the dates.

    Parameters
    ----------
    code : str
        The code of India.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp, str]]
        The first and last day of the months of each file, and the
        identifier of the file, in chronological order.
    """
    files = utils.fetcher.fetch_dataframe(
        f"https://data.mendeley.com/public-api/datasets/{DATASET_ID}",
        "html",
        read_as="json",
        json_keys=["files"],
    )
    requests = []
    for file_name, file_id in zip(files["filename"], files["id"], strict=True):
        first_day, last_day = _read_periods(file_name)
        if first_day.date() <= end_date and start_date <= last_day.date():
            requests.append((first_day, last_day, file_id))
    return sorted(requests)


def get_url(file_id: str) -> str:
    """
    Get the URL of a file of the dataset on Mendeley Data.

    Parameters
    ----------
    file_id : str
        The identifier of the file.

    Returns
    -------
    str
        The URL of the file.
    """
    return (
        f"https://data.mendeley.com/public-files/datasets/{DATASET_ID}/"
        f"files/{file_id}/file_downloaded"
    )


def download_and_extract_data_for_request(
    file: tuple[pd.Timestamp, pd.Timestamp, str], code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from a file of the dataset on Mendeley Data.

    Parameters
    ----------
    file : tuple[pandas.Timestamp, pandas.Timestamp, str]
        The first and last day of the months of the file, and the
        identifier of the file.
    code : str
        The code of India.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    first_day, last_day, file_id = file
    logging.info(
        "Retrieving electricity demand data from "
        f"{first_day.date()} to {last_day.date()}."
    )

    if first_day.to_period("M") == last_day.to_period("M"):
        # The monthly files have the SCADA tags in the first row and
        # their names in the second one.
        dataset = utils.fetcher.fetch_dataframe(
            get_url(file_id),
            "html",
            timeout=300,
            read_as="excel_table",
            excel_kwargs={
                "sheet_name": "Sheet1",
                "skiprows": [1],
                "usecols": ["Time", DEMAND_TAG],
            },
        )
        times = pd.to_datetime(dataset["Time"])

        # Keep the readings every 5 minutes, at their times in India.
        every_5_minutes = (times.dt.minute % 5 == 0) & (times.dt.second == 0)
        return pd.Series(
            dataset[DEMAND_TAG][every_5_minutes].to_numpy(dtype="float64"),
            index=pd.DatetimeIndex(times[every_5_minutes]).tz_localize(
                "Asia/Kolkata"
            ),
        )

    # The other file has the hourly demand, and summary rows without
    # times at the bottom.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(file_id),
        "html",
        timeout=300,
        read_as="excel_table",
        excel_kwargs={
            "sheet_name": "Report",
            "usecols": ["Timestamp", "Demand (MW)"],
        },
    )
    times = pd.to_datetime(
        dataset["Timestamp"], format="%d-%m-%Y %H:%M:%S", errors="coerce"
    )
    electricity_demand_time_series = pd.Series(
        dataset["Demand (MW)"][times.notna()].to_numpy(dtype="float64"),
        index=times[times.notna()],
    )

    # Move the starts of the hours to their ends.
    return utils.time_series.localize_interval_starts(
        electricity_demand_time_series, "Asia/Kolkata", pd.Timedelta(hours=1)
    )

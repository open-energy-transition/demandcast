"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of the 31 provinces of mainland China from the dataset of Wu
    and Kan on Zenodo, under the CC BY 4.0 license. The data is
    retrieved all at once, from a single CSV file of 2018.

    The file gives the hourly load of each province in MWh, the average
    power in MW, for the hours that start from 00:00 on 2018-01-01 to
    23:00 on 2018-12-31 in the time of China (UTC+8), which has no
    daylight saving time. The load is modelled: the authors trace the
    highest and lowest load of each day in the charts of the National
    Development and Reform Commission, and scale a typical load profile
    of a workday or a holiday between them, so each day has the shape of
    a typical day. The annual totals match the electricity consumption
    of 2018, such as 632 TWh in Guangdong and 6,900 TWh in all.

    The columns are named after the provinces, as in ISO 3166-2, except
    for Hebei, which is named "HB" like Hubei, and which is the third
    column: the module reads the columns by their order.

    Source: https://zenodo.org/records/8322210
"""

import datetime

import pandas as pd
import utils.fetcher
import utils.time_series

# The provinces in the order of the columns of the file, by the code of
# their subdivision. The file names Hebei (HE) "HB", like Hubei.
PROVINCES = [
    "BJ",
    "TJ",
    "HE",
    "SX",
    "NM",
    "LN",
    "JL",
    "HL",
    "SH",
    "JS",
    "ZJ",
    "AH",
    "FJ",
    "JX",
    "SD",
    "HA",
    "HB",
    "HN",
    "GD",
    "GX",
    "HI",
    "CQ",
    "SC",
    "GZ",
    "YN",
    "XZ",
    "SN",
    "GS",
    "QH",
    "NX",
    "XJ",
]


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is retrieved all at once, so there is a single request,
    without parameters.

    Parameters
    ----------
    code : str
        The code of the province.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data for China.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://zenodo.org/records/8322210/files/Appendix%201_Hourly%20electric%20power%20load%20final.csv?download=1"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data of a province of China.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of the province, such as CHN_GD.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ValueError
        If the columns of the file are not the provinces in the expected
        order.
    """
    # Fetch the data from the URL, with the hours numbered from 1 in the
    # first column and a column for each province.
    dataset = utils.fetcher.fetch_dataframe(
        get_url(),
        "csv",
        csv_kwargs={"sep": ";", "encoding": "utf-8-sig"},
    )

    # Check the names of the columns, which pandas reads as "HB" and
    # "HB.1" for Hebei and Hubei.
    expected = [
        "HB" if province == "HE" else province for province in PROVINCES
    ]
    expected[PROVINCES.index("HB")] = "HB.1"
    if dataset.columns[1:].tolist() != expected:
        raise ValueError(
            "The columns of the file of Wu et al. are not the provinces "
            f"in the expected order: {dataset.columns[1:].tolist()}."
        )

    # Extract the load of the province, at the starts of the hours, and
    # move them to their ends.
    column = 1 + PROVINCES.index(code.split("_")[1])
    starts = pd.Timestamp("2018-01-01") + pd.to_timedelta(
        dataset.iloc[:, 0] - 1, unit="h"
    )
    return utils.time_series.localize_interval_starts(
        pd.Series(
            dataset.iloc[:, column].to_numpy(dtype="float64"),
            index=pd.DatetimeIndex(starts),
        ),
        "Asia/Shanghai",
        pd.Timedelta(hours=1),
    )

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Korean Open Government Data (KROGD) portal
    in South Korea. The data is downloaded manually from the portal.

    Source: https://www.data.go.kr/
"""

import datetime

import pandas as pd
import utils.fetcher
import utils.time_series


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[None]:
    """
    Get the available requests.

    The data is read at once from the files downloaded manually, so
    there is a single request, without parameters.

    Parameters
    ----------
    code : str
        The code of South Korea.
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
    Get the URL of the electricity demand data from the KROGD portal.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.data.go.kr/data/15065266/fileData.do"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the
    KROGD portal. This function assumes that the data has been
    downloaded and is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of South Korea.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="KROGD",
        url=get_url(),
        prefix="KRO",
        read_file=lambda file_path: pd.read_csv(file_path, encoding="euc-kr"),
    )

    # The column names have the time information. Rearrange the
    # columns to have the time information on another column.
    dataset = dataset.melt(
        id_vars=dataset.columns[0], var_name="Hour", value_name="Value"
    )

    # Define the new index, at the starts of the hours.
    index = pd.to_datetime(
        dataset.iloc[:, 0].astype(str)
        + " "
        + (
            dataset.iloc[:, 1].astype(str).str.replace("시", "").astype(int)
            - 1
        ).astype(str),
        format="%Y-%m-%d %H",
    )

    # Define the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["Value"].values,
        index=index,
    )

    # Move the times to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series, "Asia/Seoul", pd.Timedelta(hours=1)
        )
    )

    return electricity_demand_time_series

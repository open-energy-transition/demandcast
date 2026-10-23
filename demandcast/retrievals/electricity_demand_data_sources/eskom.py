"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Eskom in South Africa. The data is
    retrieved by submitting a request to the Eskom website. The user
    then receives a link on the provided email address to download the
    data.

    The files give the hourly RSA contracted demand in MW, the larger of
    the two demands of the data portal, by the start of each hour
    ("Date Time Hour Beginning") in South African time, which has no
    daylight saving time.

    The demand leaves out the demand that the rooftop solar of the
    consumers supplies, which Eskom estimates at about 1 GW in March
    2022, 4.4 GW in June 2023 and 7.3 GW in August 2025, so it is not
    the gross demand of DemandCast: its demand at midday falls compared
    with the morning and afternoon, and the cleaning flags it
    (midday_dip). Eskom does not publish this generation hourly.

    The data starts on 2021-04-01, in a file downloaded in July 2025
    that ends on 2025-07-26; a later download starts on 2022-04-01.
    Where the files overlap, they agree except for about 700 hours from
    April to July 2025, which Eskom revised, by up to 509 MW. Each hour
    therefore takes the value of the file whose data ends last, the
    latest download, unless it has no number for that hour.

    Source: https://www.eskom.co.za/dataportal/data-request-form/
"""

import datetime
import logging

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
        The code of South Africa.
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
    Get the URL of the electricity demand data from the Eskom website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return "https://www.eskom.co.za/dataportal/cf-api/CF600011bdba174"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Extract electricity demand data.

    This function extracts the electricity demand data from the Eskom
    website. This function assumes that the data has been downloaded and
    is available in the specified folder.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of South Africa.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Read the downloaded files.
    dataset = utils.fetcher.read_manual_files(
        data_source_name="Eskom",
        url=get_url(),
        prefix="ESK",
        read_file=pd.read_csv,
        access=" after sending a request via the form on the website",
    )

    # Read the values as numbers. A value that is not a number, such as
    # the text "ast" in the data of 2025-07-11, becomes a missing value,
    # which the cleaning of the data then removes.
    load = pd.to_numeric(dataset["RSA Contracted Demand"], errors="coerce")
    not_numbers = dataset["RSA Contracted Demand"][
        load.isna() & dataset["RSA Contracted Demand"].notna()
    ]
    if not not_numbers.empty:
        logging.warning(
            f"{len(not_numbers)} values of Eskom are not numbers and are "
            f"left out, such as {not_numbers.iloc[0]!r}."
        )

    # Extract the electricity demand time series, with one value of
    # each hour from the latest download.
    electricity_demand_time_series = utils.time_series.keep_latest_download(
        pd.Series(
            load.to_numpy(),
            index=pd.to_datetime(
                dataset["Date Time Hour Beginning"],
                format="%Y-%m-%d %I:%M:%S %p",
            ),
        ),
        dataset["File"],
    )

    # The times are the starts of the hours, as the name of their column
    # says. Move them to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Africa/Johannesburg",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of Eskom in South Africa. The data is
    retrieved by submitting a request to the Eskom website. The user
    then receives a link on the provided email address to download the
    data.

    Source: https://www.eskom.co.za/dataportal/data-request-form/
"""

import datetime
import logging
import os

import pandas as pd
import utils.config


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug(
        "Content may not be used for any commercial and non-private purposes."
    )
    logging.debug(
        "Source: https://www.eskom.co.za/wp-content/uploads/2021/10/WEBSITE-TERMS-AND-CONDITIONS_Sep2021.pdf"
    )
    return False


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

    Raises
    ------
    FileNotFoundError
        If the data file is not found in the specified folder.
    """
    # Get the data folder.
    data_directory = utils.config.read_folders_structure()[
        "manually_downloaded_electricity_demand_folder"
    ]

    # Get the paths of the downloaded files that start with "ESK".
    downloaded_file_paths = [
        os.path.join(data_directory, file)
        for file in os.listdir(data_directory)
        if file.startswith("ESK")
    ]

    if not downloaded_file_paths:
        raise FileNotFoundError(
            f"The data for Eskom has not been found in the folder "
            f"{data_directory}. Please download the data manually from "
            f"{get_url()} after sending a request via the form on the "
            f"website. The data files must be named starting with 'ESK'."
        )

    # Load the data from the downloaded files into a pandas DataFrame.
    dataset = pd.concat(
        [pd.read_csv(file_path) for file_path in downloaded_file_paths]
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

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        load.to_numpy(),
        index=pd.to_datetime(
            dataset["Date Time Hour Beginning"], format="%Y-%m-%d %I:%M:%S %p"
        ),
    )

    # Add one hour to the index because the electricity demand seems to
    # be provided at the beginning of the hour.
    electricity_demand_time_series.index = (
        electricity_demand_time_series.index + pd.Timedelta(hours=1)
    )

    # Add the timezone information to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("Africa/Johannesburg")
    )

    return electricity_demand_time_series

"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the National Energy System Operator (NESO)
    in the UK. The data is retrieved for the years from 2009 to the
    current year.
    The data is retrieved in one-year intervals.

    Source: https://www.neso.energy/data-portal/historic-demand-data
"""

import datetime
import logging

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
    logging.debug("Use for any purpose with attribution.")
    logging.debug(
        "Source: https://www.neso.energy/data-portal/neso-open-licence"
    )
    return True


def get_available_requests(
    code: str, start_date: datetime.date, end_date: datetime.date
) -> list[int]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the NESO website.

    Parameters
    ----------
    code : str
        The code of Great Britain.
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
    Get the URL of the electricity demand data on the NESO website.

    The identifier of the dataset of the year is read from the
    catalogue of NESO, which names it "Historic Demand Data" followed
    by the year.

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
    TypeError
        If the extracted catalogue is not a pandas DataFrame.
    ValueError
        If the catalogue has no dataset for the year.
    """
    # Fetch the datasets in the catalogue, one for each year.
    datasets = utils.fetcher.fetch_data(
        "https://api.neso.energy/api/3/action/package_show?"
        "id=historic-demand-data",
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["result", "resources"],
    )

    # Make sure the datasets are in a pandas DataFrame.
    if not isinstance(datasets, pd.DataFrame):
        raise TypeError(
            f"The extracted catalogue is a {type(datasets)} object, "
            "expected a pandas DataFrame."
        )

    # Get the identifier of the dataset of the year.
    dataset_ids = datasets.loc[
        datasets["name"] == f"Historic Demand Data {year}", "id"
    ]
    if dataset_ids.empty:
        raise ValueError(f"The year {year} is not supported for the dataset.")

    # Return the URL of the electricity demand data.
    return (
        "https://api.neso.energy/api/3/action/datastore_search_sql?"
        f"sql=SELECT%20*%20FROM%20%22{dataset_ids.iloc[0]}%22%20"
        "ORDER%20BY%20%22_id%22%20ASC%20LIMIT%20100000"
    )


def download_and_extract_data_for_request(year: int, code: str) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the NESO website.

    Parameters
    ----------
    year : int
        The year of the electricity demand data.
    code : str
        The code of Great Britain.

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

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["result", "records"],
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Extract the electricity demand time series.
    electricity_demand_time_series = pd.Series(
        dataset["ND"].values,
        index=pd.date_range(
            start=f"{year}-01-01 00:30",
            periods=len(dataset),
            freq="30min",
            tz="Europe/London",
        ),
    )

    return electricity_demand_time_series

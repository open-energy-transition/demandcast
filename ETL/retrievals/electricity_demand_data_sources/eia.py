# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the US Energy Information Administration
    (EIA). The data is retrieved for the years from 2020 to the current
    year. The data is retrieved in six-month intervals.

    Source: https://www.eia.gov/opendata/browser/electricity/rto/region-data
"""  # noqa: W505

import logging
import os

import pandas
import utils.directories
import utils.entities
import utils.fetcher
from dotenv import load_dotenv


def redistribute() -> bool:
    """
    Return a boolean indicating if the data can be redistributed.

    Returns
    -------
    bool
        True if the data can be redistributed, False otherwise.
    """
    logging.debug("Use for any purpose with attribution to EIA.")
    logging.debug("Source: https://www.eia.gov/about/copyrights_reuse.php")
    return True


def _check_input_parameters(
    code: str,
    start_date: pandas.Timestamp | None = None,
    end_date: pandas.Timestamp | None = None,
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.
    start_date : pandas.Timestamp, optional
        The start date of the data retrieval.
    end_date : pandas.Timestamp, optional
        The end date of the data retrieval.
    """
    # Check if the code is valid.
    utils.entities.check_code(code, "eia")

    if start_date is not None and end_date is not None:
        # Check that the number of time points is less than 5000.
        assert (end_date - start_date).days * 24 < 5000, (
            "The number of time points is greater than 5000."
        )

        # Read the start date of the available data.
        start_date_of_data_availability = pandas.to_datetime(
            utils.entities.read_date_ranges(data_source="eia")[code][0]
        )

        # Check that the start date is greater than or equal to the
        # beginning of the data availability.
        assert start_date >= start_date_of_data_availability, (
            "The beginning of the data availability is "
            f"{start_date_of_data_availability}."
        )


def get_available_requests(
    code: str,
) -> list[tuple[pandas.Timestamp, pandas.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the EIA website.

    Parameters
    ----------
    code : str
        The code of the subdivision.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(code)

    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="eia")[
        code
    ]

    # Define intervals for the retrieval periods. A six-month period
    # avoids the limitation of the API to retrieve a maximum of 5000
    # data points.
    intervals = pandas.date_range(start_date, end_date, freq="6MS")
    intervals = intervals.union(pandas.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each six-month period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url(
    start_date: pandas.Timestamp,
    end_date: pandas.Timestamp,
    code: str,
) -> str:
    """
    Get the URL of the electricity demand data on the EIA website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    str
        The URL of the electricity demand data.

    Raises
    ------
    ValueError
        If the EIA API key is not set.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(code, start_date=start_date, end_date=end_date)

    # Get the root directory of the project.
    root_directory = utils.directories.read_folders_structure()["root_folder"]

    # Load the environment variables.
    load_dotenv(dotenv_path=os.path.join(root_directory, ".env"))

    # Get the API key.
    api_key = os.getenv("EIA_API_KEY")

    # Check if the API key is set.
    if api_key is None:
        raise ValueError(
            "The EIA API key is not set. Please set the EIA_API_KEY "
            "environment variable."
        )

    # Convert the start and end dates and times to the required format.
    start = start_date.strftime("%Y-%m-%dT%H")
    end = end_date.strftime("%Y-%m-%dT%H")

    # Extract the subdivision code.
    subdivision_code = code.split("_")[1]

    # Return the URL of the electricity demand data.
    return (
        "https://api.eia.gov/v2/electricity/rto/region-data/data/?"
        f"api_key={api_key}&facets[type][]=D&"
        f"facets[respondent][]={subdivision_code}&"
        f"start={start}&end={end}&frequency=hourly&data[0]=value&"
        "sort[0][column]=period&sort[0][direction]=asc&offset=0&length=5000"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp,
    end_date: pandas.Timestamp,
    code: str,
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the EIA website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    code : str
        The code of the subdivision of interest.

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
    _check_input_parameters(code, start_date=start_date, end_date=end_date)

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date, code)

    # Fetch the electricity demand data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.get",
        read_as="json",
        json_keys=["response", "data"],
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Create the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["value"].values,
            index=pandas.to_datetime(dataset["period"]),
        ).tz_localize("UTC")

        return electricity_demand_time_series

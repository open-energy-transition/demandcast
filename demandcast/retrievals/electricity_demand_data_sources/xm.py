"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the XM Adminstradores del mercado electrico
    in Colombia. The data is actually made available through the website
    of "Energia de Colombia" (https://www.energiadecolombia.com). The
    data is retrieved from 2000-01-01 to today. The data is retrieved in
    one-month intervals.

    Source: https://xm.com.co
    Source: https://www.energiadecolombia.com/consulta
"""

import logging

import pandas as pd
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
    logging.debug(
        "Reproducing, copying, or distributing this data is not allowed."
    )
    logging.debug(
        "Source: https://www.xm.com.co/legales/terminos-legales-del-sitio-web"
    )
    return False


def _check_input_parameters(
    start_date: pd.Timestamp, end_date: pd.Timestamp
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.

    Raises
    ------
    ValueError
        If the input parameters are not valid.
    """
    # Check that the retrieval period is less than one month.
    if end_date - start_date > pd.Timedelta("31days"):
        raise ValueError(
            "The retrieval period is greater than 1 month. Please reduce the "
            "period to 1 month."
        )

    # Read the start date of the available data.
    start_date_of_data_availability = pd.to_datetime(
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "xm"
        )["COL"][0]
    )

    # Check that the start date is greater than or equal to the
    # beginning of the data availability.
    if start_date < start_date_of_data_availability:
        raise ValueError(
            "The beginning of the data availability is "
            f"{start_date_of_data_availability}."
        )


def get_available_requests() -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the XM website.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            "xm"
        )["COL"]
    )

    # Define one-month intervals for the retrieval periods.
    intervals = pd.date_range(start_date, end_date, freq="MS")
    intervals = intervals.union(pd.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-month period.
    return list(zip(start_dates_and_times, end_dates_and_times, strict=True))


def get_url(start_date: pd.Timestamp, end_date: pd.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the XM website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date, end_date)

    # Return the URL of the electricity demand data.
    return (
        "https://50uclmn31c.execute-api.us-east-1.amazonaws.com/prod/xmproxy?"
        f"metricId=DemaReal&entity=Sistema&start={start_date:%Y-%m-%d}"
        f"&end={end_date:%Y-%m-%d}"
    )


def download_and_extract_data_for_request(
    start_date: pd.Timestamp, end_date: pd.Timestamp
) -> pd.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the XM website.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    TypeError
        If the extracted data is not a pandas DataFrame.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(start_date, end_date)

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url(start_date, end_date)

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.post",
        read_as="json",
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )

    # Initialize the list to store the daily values.
    daily_values_list = []

    # Iterate over the dates in the dataset.
    for date in dataset["Date"]:
        # Extract the row corresponding to the date.
        values_dict = dataset[dataset["Date"] == date]

        # Extract the values for each hour of the day.
        hourly_values = [
            (values_dict["Values"].to_numpy()[0])[f"Hour{hour:02d}"]
            for hour in range(1, 25)
        ]

        # Define the date and time for each hour of the day.
        date_and_time = [date + f" {hour:02d}:00" for hour in range(24)]

        # Create and append a pandas Series for the day.
        daily_values_list.append(
            pd.Series(
                hourly_values,
                index=pd.to_datetime(date_and_time),
            )
        )

    # Concatenate the daily values into a single pandas Series.
    electricity_demand_time_series = pd.concat(daily_values_list)

    # Convert the electricity demand values to float type.
    electricity_demand_time_series = electricity_demand_time_series.astype(
        float
    )

    # Values are in kWh with a frequency of 1 hour. Convert to MW.
    electricity_demand_time_series = electricity_demand_time_series / 1000

    # Add the timezone to the index.
    electricity_demand_time_series = (
        electricity_demand_time_series.tz_localize("America/Bogota")
    )

    # Add 1 hour to the index to account for the fact that the time
    # is given at the beginning of the hour.
    electricity_demand_time_series.index += pd.Timedelta(hours=1)

    return electricity_demand_time_series

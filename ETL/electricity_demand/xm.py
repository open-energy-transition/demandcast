# -*- coding: utf-8 -*-
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
    logging.debug(
        "Reproducing, copying, or distributing this data is not allowed."
    )
    logging.debug(
        "Source: https://www.xm.com.co/legales/terminos-legales-del-sitio-web"
    )
    return False


def _check_input_parameters(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> None:
    """
    Check if the input parameters are valid.

    Parameters
    ----------
    start_date : pandas.Timestamp
        The start date of the data retrieval.
    end_date : pandas.Timestamp
        The end date of the data retrieval.
    """
    # Check that the retrieval period is less than one month.
    assert (end_date - start_date) <= pandas.Timedelta("31days"), (
        "The retrieval period is greater than 1 month. Please reduce the "
        "period to 1 month."
    )

    # Read the start date of the available data.
    start_date_of_data_availability = pandas.to_datetime(
        utils.entities.read_date_ranges(data_source="xm")["CO"][0]
    )

    # Check that the start date is greater than or equal to the
    # beginning of the data availability.
    assert start_date >= start_date_of_data_availability, (
        "The beginning of the data availability is "
        f"{start_date_of_data_availability}."
    )


def get_available_requests() -> list[
    tuple[pandas.Timestamp, pandas.Timestamp]
]:
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
    start_date, end_date = utils.entities.read_date_ranges(data_source="xm")[
        "CO"
    ]

    # Define one-month intervals for the retrieval periods.
    intervals = pandas.date_range(start_date, end_date, freq="MS")
    intervals = intervals.union(pandas.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-month period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url(start_date: pandas.Timestamp, end_date: pandas.Timestamp) -> str:
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

    # Convert the start and end date to string format.
    start_date = start_date.strftime("%Y-%m-%d")
    end_date = end_date.strftime("%Y-%m-%d")

    # Return the URL of the electricity demand data.
    return (
        "https://50uclmn31c.execute-api.us-east-1.amazonaws.com/prod/xmproxy?"
        f"metricId=DemaReal&entity=Sistema&start={start_date}&end={end_date}"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> pandas.Series:
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
    ValueError
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
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Initialize the list to store the daily values.
        dayly_values_list = []

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
            dayly_values_list.append(
                pandas.Series(
                    hourly_values,
                    index=pandas.to_datetime(date_and_time),
                )
            )

        # Concatenate the daily values into a single pandas Series.
        electricity_demand_time_series = pandas.concat(dayly_values_list)

        # Values are in kWh with a frequency of 1 hour. Convert to MW.
        electricity_demand_time_series = electricity_demand_time_series / 1000

        # Add the timezone to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize("America/Bogota")
        )

        # Add 1 hour to the index to account for the fact that the time
        # is given at the beginning of the hour.
        electricity_demand_time_series.index += pandas.Timedelta(hours=1)

        return electricity_demand_time_series

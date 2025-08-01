# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Coordinador Eléctrico Nacional (CEN)
    in Chile. The data is retrieved for the years from 1999 to the
    current year. The data is retrieved in one-year intervals.

    Source: https://www.coordinador.cl/operacion/graficos/operacion-real/demanda-real/
"""  # noqa: W505

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
    logging.debug("Open data.")
    logging.debug("Source: http://energiaabierta.cl")
    return True


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
    # Check that the retrieval period is less than one year.
    assert (end_date - start_date) <= pandas.Timedelta("366days"), (
        "The retrieval period is greater than 1 year. "
        "Please reduce the period to 1 year."
    )

    # Read the start date of the available data.
    start_date_of_data_availability = pandas.to_datetime(
        utils.entities.read_date_ranges(data_source="cen")["CL"][0]
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
    demand data from the CEN website.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(data_source="cen")[
        "CL"
    ]

    # Define one-year intervals for the retrieval periods.
    intervals = pandas.date_range(start_date, end_date, freq="YS")
    intervals = intervals.union(pandas.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url(start_date: pandas.Timestamp, end_date: pandas.Timestamp) -> str:
    """
    Get the URL of the electricity demand data on the CEN website.

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
        "https://sipub.coordinador.cl/api/v1/recursos/"
        f"demandasistemareal?fecha__gte={start_date}&fecha__lte={end_date}"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp, end_date: pandas.Timestamp
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CEN website.

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

    # Define the headers for the request.
    header_params = {
        "Referer": (
            "https://www.coordinador.cl/operacion/graficos/"
            "operacion-real/demanda-real/"
        ),
        "Origin": "https://www.coordinador.cl",
    }

    # Fetch the data from the URL.
    dataset = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.get",
        header_params=header_params,
        read_as="json",
        json_keys=["data"],
    )

    # Make sure the dataset is a pandas DataFrame.
    if not isinstance(dataset, pandas.DataFrame):
        raise ValueError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    else:
        # Merge the date and time columns into a single column. Consider
        # that the time is given at the end of the hour. In some years
        # where there is the switch to or from daylight saving time,
        # there is a 25th hour.
        dataset["date and time"] = [
            date + f" {(min(time, 24) - 1):02d}:00"
            for date, time in zip(dataset["fecha"], dataset["hora"])
        ]

        # Sort the dataset by date and time.
        dataset = dataset.sort_values(by="date and time", ascending=True)

        # Extract the electricity demand time series.
        electricity_demand_time_series = pandas.Series(
            dataset["demanda"].values,
            index=pandas.to_datetime(dataset["date and time"]),
        )

        # Add the timezone to the index.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index.tz_localize(
                "America/Santiago", ambiguous="NaT", nonexistent="NaT"
            )
        )

        # Add 1 hour to the index to match the original dataset.
        electricity_demand_time_series.index += pandas.Timedelta(hours=1)

        return electricity_demand_time_series

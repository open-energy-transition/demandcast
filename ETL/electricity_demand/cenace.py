# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data from the website of the Centro Nacional de Control de Energía
    (CENACE) in Mexico. The data is retrieved for the period from 2016
    to today. The data is retrieved in one-year intervals.

    Source: https://www.cenace.gob.mx/Paginas/SIM/Reportes/EstimacionDemandaReal.aspx
"""  # noqa: W505

import logging
import zipfile
from io import BytesIO, StringIO

import pandas
import requests
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
        "User must not modify, reproduce or publicly or commercially display "
        "the material."
    )
    logging.debug("Source: https://www.gob.mx/terminos")
    return False


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
    utils.entities.check_code(code, "cenace")

    if start_date is not None and end_date is not None:
        # Check if the retrieval period is less than 1 year.
        assert (end_date - start_date) <= pandas.Timedelta("366days"), (
            "The retrieval period must be less than or equal to 1 year. "
            f"start_date: {start_date}, end_date: {end_date}"
        )

        # Read the start date of the available data.
        start_date_of_data_availability = pandas.to_datetime(
            utils.entities.read_date_ranges(data_source="cenace")[code][0]
        )

        # Check that the start date is greater than or equal to the
        # beginning of the data availability.
        assert start_date >= start_date_of_data_availability, (
            f"The beginning of the data availability is {start_date_of_data_availability}."
        )


def get_available_requests(
    code: str,
) -> list[tuple[pandas.Timestamp, pandas.Timestamp]]:
    """
    Get the available requests.

    This function retrieves the available requests for the electricity
    demand data from the CENACE website.

    Parameters
    ----------
    code : str
        The code of the subdivision of interest.

    Returns
    -------
    list[tuple[pandas.Timestamp, pandas.Timestamp]]
        The list of available requests.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(code)

    # Read the start and end date of the available data.
    start_date, end_date = utils.entities.read_date_ranges(
        data_source="cenace"
    )[code]

    # Mexico has data until 15 days before the current date. Subtract
    # 10 days to the end date on top of the 5 days already considered.
    end_date = pandas.to_datetime(end_date) - pandas.Timedelta("10days")

    # Define intervals for the retrieval periods.
    intervals = pandas.date_range(start_date, end_date, freq="YS")
    intervals = intervals.union(pandas.to_datetime([start_date, end_date]))

    # Define start and end dates of the retrieval periods.
    start_dates_and_times = intervals[:-1]
    end_dates_and_times = intervals[1:]

    # Return the available requests, which are the beginning and end of
    # each one-year period.
    return list(zip(start_dates_and_times, end_dates_and_times))


def get_url() -> str:
    """
    Get the URL of the electricity demand data on the CENACE website.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    # Return the URL of the electricity demand data.
    return (
        "https://www.cenace.gob.mx/Paginas/SIM/Reportes/"
        "EstimacionDemandaReal.aspx"
    )


def download_and_extract_data_for_request(
    start_date: pandas.Timestamp,
    end_date: pandas.Timestamp,
    code: str,
) -> pandas.Series:
    """
    Download and extract electricity demand data.

    This function downloads and extracts the electricity demand data
    from the CENACE website.

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
        If the response is not a requests.Response object or if no data
        is found for the specified date.
    """
    # Check if the input parameters are valid.
    _check_input_parameters(code, start_date=start_date, end_date=end_date)

    logging.info(
        "Retrieving electricity demand data from "
        f"{start_date.date()} to {end_date.date()}."
    )

    # Get the URL of the electricity demand data.
    url = get_url()

    # Define the parameters for the POST request.
    post_data_params = {
        "ctl00$ContentPlaceHolder1$RadDatePickerFIVisualizarPorBalance"
        "$dateInput": start_date.strftime("%d/%m/%Y"),
        "ctl00_ContentPlaceHolder1_RadDatePickerFIVisualizarPorBalance"
        "_dateInput_ClientState": (
            '{"valueAsString":"'
            + start_date.strftime("%Y-%m-%d")
            + '-00-00-00","lastSetTextBoxValue":"'
            + start_date.strftime("%d/%m/%Y")
            + '"}'
        ),
        "ctl00$ContentPlaceHolder1$RadDatePickerFFVisualizarPorBalance"
        "$dateInput": end_date.strftime("%d/%m/%Y"),
        "ctl00_ContentPlaceHolder1_RadDatePickerFFVisualizarPorBalance"
        "_dateInput_ClientState": (
            '{"valueAsString":"'
            + end_date.strftime("%Y-%m-%d")
            + '-00-00-00","lastSetTextBoxValue":"'
            + end_date.strftime("%d/%m/%Y")
            + '"}'
        ),
        "ctl00$ContentPlaceHolder1$DescargarArchivosCsv"
        "_PorBalance": "Descargar+en+archivo+.zip",
    }

    # Define the headers for the request.
    header_params = {"User-Agent": "Mozilla/5.0"}

    # Fetch HTML content from the URL.
    response = utils.fetcher.fetch_data(
        url,
        "html",
        read_with="requests.post",
        read_as="plain",
        header_params=header_params,
        post_data_params=post_data_params,
        query_aspx_webpage=True,
    )

    # Make sure the response is a requests.Response object.
    if not isinstance(response, requests.Response):
        raise ValueError(
            f"The extracted response is a {type(response)} object, "
            "expected a requests.Response object."
        )
    else:
        # Extract the zip file from the HTML content.
        archive = zipfile.ZipFile(BytesIO(response.content), "r")

        # Get the names of the files in the archive.
        file_names = archive.namelist()

        # Get all the dates in the time range.
        dates = (
            pandas.date_range(start_date, end_date, freq="d")
            .strftime("%Y-%m-%d")
            .tolist()
        )

        # Get the subdivision code.
        subdivision_code = code.split("_")[1]

        # Get the time zone of the country or subdivision.
        time_zone = utils.entities.get_time_zone(code)

        # Initialize the list to store the daily values.
        daily_values_list = []

        # Iterate over the dates and extract the corresponding files.
        for date in dates:
            # Define the file version to be extracted. Start with the
            # latest version and go backwards.
            file_version = -1

            # Define a flag to indicate if the data for the date was
            # found.
            found_data = False

            # Loop until the data for the date is found or all file
            # versions are exhausted.
            while not found_data:
                # Get the file name corresponding to the date.
                file_name = [name for name in file_names if date in name][
                    file_version
                ]

                # Extract the file content from the archive.
                file_content = archive.open(file_name).read().decode("utf-8")

                # Find the line that contains the header of the CSV
                # file.
                skip_rows = file_content.split("\n").index(
                    [
                        line
                        for line in file_content.split("\n")
                        if "Estimacion de Demanda por Balance (MWh)" in line
                    ][0]
                )

                # Check if the line after the header has some data.
                if file_content.split("\n")[skip_rows + 1] != "":
                    found_data = True
                else:
                    # If the line after the header is empty, try the
                    # previous version of the file.
                    file_version -= 1

                    if file_version < -len(file_names):
                        # If there are no more versions of the file,
                        # raise an error.
                        raise ValueError(
                            f"No data found for the date {date} "
                            f"in the file {file_name}."
                        )

            # Read the file content into a pandas DataFrame.
            dataset = pandas.read_csv(
                StringIO(file_content), skiprows=skip_rows, index_col=False
            )

            # Define the column name for the subdivision code.
            column_name = (
                "Sistema"
                if subdivision_code == "BCA" or subdivision_code == "BCS"
                else " Area"
            )

            # Extract the daily values for the subdivision.
            daily_values = dataset[dataset[column_name] == subdivision_code][
                " Estimacion de Demanda por Balance (MWh) "
            ].reset_index(drop=True)

            # For the Norte subdivision on 2022-10-30, there seems to be
            # an extra hour in the data.
            if subdivision_code == "NTE" and date == "2022-10-30":
                # Remove the third value from the list.
                daily_values = daily_values.drop(2)

            # Set a new index with the date and time for each hour of
            # the day.
            daily_values.index = pandas.date_range(
                start=date + " 00:00:00",
                end=date + " 23:59:59",
                freq="h",
                tz=time_zone,
            )

            # Append the daily values to the list.
            daily_values_list.append(daily_values)

        # Concatenate the daily values into a single pandas Series.
        electricity_demand_time_series = pandas.concat(daily_values_list)

        # Add 1 hour to the index to indicate the end of the hour.
        electricity_demand_time_series.index = (
            electricity_demand_time_series.index + pandas.Timedelta("1h")
        )

        return electricity_demand_time_series

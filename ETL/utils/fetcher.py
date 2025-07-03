# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides a function to fetch data from various online
    content sources, including CSV, Excel, HTML, and JSON formats. It
    also includes a function to fetch hourly electricity demand time
    series from the ENTSO-E API.
"""

import logging
import re
import time
import urllib.error
import urllib.request
from io import StringIO

import pandas
import requests
import requests.exceptions
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError


def _read_aspx_params(
    response: requests.Response, post_data_params: dict[str, str | int]
) -> dict[str, str | int]:
    """
    Read the ASPX parameters from the response.

    This function extracts relevant ASPX parameters such as
    `__VIEWSTATE` and `__EVENTVALIDATION` from the HTML content of the
    response and adds them to the provided POST data parameters.

    Parameters
    ----------
    response : requests.Response
        The response object from the GET request.
    post_data_params : dict[str, str | int]
        The original POST data parameters.

    Returns
    -------
    dict[str, str | int]
        The updated POST data parameters with the ASPX parameters added.
    """
    # Read the content of the response.
    html_content = response.text

    # Extract the parameters from the HTML content.
    viewstate = re.findall(r"id=\"__VIEWSTATE\" value=\"(.+)\"", html_content)[
        0
    ]
    eventvalidation = re.findall(
        r"id=\"__EVENTVALIDATION\" value=\"(.+)\"", html_content
    )[0]

    # Prepare the parameters for the POST request.
    additional_post_data_params = {
        "__VIEWSTATE": viewstate,
        "__EVENTVALIDATION": eventvalidation,
    }

    # Add the additional parameters for the POST request.
    for key, value in additional_post_data_params.items():
        post_data_params[key] = value

    return post_data_params


def fetch_data(
    url: str,
    content_type: str,
    retries: int = 5,
    retry_delay: int = 5,
    read_with: str = "requests.get",
    read_as: str = "tabular",
    csv_kwargs: dict[str, str | int] = {},
    excel_kwargs: dict[
        str, str | int | list[str] | list[str | int] | None
    ] = {},
    verify_ssl: bool = True,
    request_params: dict[str, str] = {},
    post_data_params: dict[str, str | int] = {},
    header_params: dict[str, str] = {},
    json_keys: list[str] = [],
    query_aspx_webpage: bool = False,
) -> pandas.DataFrame | str | requests.Response:
    """
    Fetch the data from the specified URL.

    This function supports fetching data in various formats such as CSV,
    Excel, HTML, and JSON. It includes retry logic for handling
    connection errors and allows customization of the request
    parameters, headers, and data formats.

    Parameters
    ----------
    url : str
        The URL of the data source.
    content_type : str
        The type of the content to be fetched.
    retries : int, optional
        The number of retries in case of connection errors.
    delay : int, optional
        The delay between retries in seconds.
    read_with : str, optional
        The library to use for reading the html content.
    read_as : str, optional
        The format to read the content as.
    csv_kwargs : dict[str, str | int], optional
        The keyword arguments for reading CSV files.
    excel_kwargs : dict[str, str | int | list[str] | list[str | int] |
                        None], optional
        The keyword arguments for reading Excel files.
    verify_ssl : bool, optional
        Verify the SSL certificate.
    header_params : dict[str, str], optional
        The headers for the request.
    request_params : dict[str, str], optional
        The parameters for the request.
    post_data_params : dict[str, str | int], optional
        The data for the POST request.
    json_keys : list[str], optional
        The keys to extract from the JSON response.
    query_aspx_webpage : bool, optional
        Whether to query the ASPX webpage.

    Returns
    -------
    pandas.DataFrame | str | requests.Response
        The fetched data as a DataFrame, string, or response object.

    Raises
    ------
    ValueError
        If the content type is not supported.
    Exception
        If the request fails after the specified number of retries.
    """
    # Try to fetch the data from the URL. These multiple try and except
    # blocks are used to handle different types of errors that may occur
    # at different stages of the request.
    try:
        for attempt in range(retries):
            try:
                try:
                    if content_type == "csv":
                        # Read the CSV file from the URL.
                        return pandas.read_csv(url, **csv_kwargs)

                    elif content_type == "excel":
                        # Read the Excel file from the URL.
                        return pandas.read_excel(url, **excel_kwargs)

                    elif content_type == "html":
                        if read_with == "urllib.request":
                            # Read the HTML content from the URL using
                            # the urlib.request module.
                            request = urllib.request.Request(url)
                            for key, value in header_params.items():
                                request.add_header(key, value)

                            # Send the request and return the response
                            # as a string.
                            return (
                                urllib.request.urlopen(request)
                                .read()
                                .decode("utf-8")
                            )

                        elif (
                            read_with == "requests.get"
                            or read_with == "requests.post"
                        ):
                            if read_with == "requests.get":
                                # Send a GET request to the URL.
                                response = requests.get(
                                    url,
                                    timeout=10,
                                    verify=verify_ssl,
                                    headers=header_params,
                                    params=request_params,
                                )

                            elif read_with == "requests.post":
                                if query_aspx_webpage:
                                    # Read the HTML content from the URL
                                    # using the requests module.
                                    response = requests.get(
                                        url,
                                        timeout=10,
                                        verify=verify_ssl,
                                        headers=header_params,
                                        params=request_params,
                                    )

                                    # Read the ASPX parameters from the
                                    # response and add them to the POST
                                    # data parameters.
                                    post_data_params = _read_aspx_params(
                                        response, post_data_params
                                    )

                                # Send a POST request to the URL.
                                response = requests.post(
                                    url,
                                    timeout=10,
                                    verify=verify_ssl,
                                    headers=header_params,
                                    params=request_params,
                                    data=post_data_params,
                                )

                            # Check if the request was successful.
                            response.raise_for_status()

                            if read_as == "tabular":
                                # Return the content as a DataFrame.
                                return pandas.read_csv(
                                    StringIO(response.text), **csv_kwargs
                                )
                            elif read_as == "text":
                                # Return the content as a string.
                                return response.text
                            elif read_as == "json":
                                # Read the content of the response
                                content = response.json()

                                # Loop over the JSON keys and extract
                                # the content.
                                for json_key in json_keys:
                                    content = content[json_key]

                                # Return the content as a DataFrame.
                                return pandas.DataFrame(content)
                            elif read_as == "plain":
                                # Return just the response.
                                return response
                            else:
                                raise ValueError(
                                    f"The read_as parameter {read_as} is not "
                                    "supported."
                                )

                        else:
                            raise ValueError(
                                f"Library {read_with} is not supported."
                            )

                    else:
                        raise ValueError(
                            f"The content type {content_type} is not "
                            "supported."
                        )

                except requests.exceptions.SSLError as e:
                    logging.error(
                        f"SSL error: {e}.\nPlease verify the SSL certificate."
                    )
                    raise Exception(f"SSL error: {e}")

            except requests.exceptions.ConnectionError as e:
                logging.error(
                    f"Connection error: {e}.\n"
                    f"Retrying ({attempt + 1}/{retries})..."
                )
                time.sleep(retry_delay)

            except requests.exceptions.Timeout as e:
                logging.error(
                    f"Timeout error: {e}.\n"
                    f"Retrying ({attempt + 1}/{retries})..."
                )
                time.sleep(retry_delay)

            except (
                requests.exceptions.HTTPError,
                urllib.error.HTTPError,
            ) as e:
                logging.error(
                    f"HTTP error: {e}.\n"
                    f"The URL {url} is not valid or the server is not "
                    f"responding. Retrying ({attempt + 1}/{retries})..."
                )
                time.sleep(retry_delay)

    except (requests.exceptions.RequestException, urllib.error.URLError) as e:
        logging.error(
            f"Request error: {e}.\n"
            f"The URL {url} is not valid or the server is "
            "not responding."
        )
        raise Exception(f"Request error: {e}")

    raise Exception(
        f"Failed to fetch data from {url} after {retries} retries."
    )


def fetch_entsoe_demand(
    api_key: str,
    iso_alpha_2_code: str,
    start_date_and_time: pandas.Timestamp,
    end_date_and_time: pandas.Timestamp,
    retries: int = 3,
    retry_delay: int = 5,
) -> pandas.Series:
    """
    Fetch the electricity demand time series from the ENTSO-E API.

    This function retrieves the hourly electricity demand time series
    for a specified country using the ENTSO-E API. It handles connection
    errors and retries the request if necessary. The data is returned
    as a pandas Series with the time index in UTC and the values in MW.

    Parameters
    ----------
    api_key : str
        The API key for the ENTSO-E API.
    iso_alpha_2_code : str
        The ISO Alpha-2 code of the country.
    start_date_and_time : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date_and_time : pandas.Timestamp
        The end date and time of the data retrieval.
    max_attempts : int, optional
        The maximum number of retry attempts.
    retry_delay : int, optional
        The delay between retry attempts in seconds.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.

    Raises
    ------
    ConnectionError
        If the connection to the ENTSO-E API fails after the specified
        number of retries.
    """
    # Define the ENTSO-E API client.
    client = EntsoePandasClient(api_key=api_key)

    try:
        for attempt in range(retries):
            try:
                return client.query_load(
                    iso_alpha_2_code,
                    start=start_date_and_time,
                    end=end_date_and_time,
                )["Actual Load"]

            except ConnectionError:
                logging.error(
                    f"Connection error. Retrying ({attempt}/{retries})..."
                )
                time.sleep(retry_delay)

        raise ConnectionError(
            f"Failed to connect to the ENTSO-E API after {retries} retries."
        )

    except NoMatchingDataError:
        # If the data is not available, skip to the next country.
        logging.warning(
            f"No data available for {iso_alpha_2_code} between "
            f"{start_date_and_time.date()} and {end_date_and_time.date()}."
        )

        return pandas.Series()

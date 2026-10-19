"""
License: AGPL-3.0.

Description:

    This module provides a function to fetch data from various online
    content sources, including CSV, Excel, HTML, and JSON formats. It
    also includes a function to fetch hourly electricity demand time
    series from the ENTSO-E API.
"""

import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from io import BytesIO, StringIO
from typing import Any

import pandas as pd
import requests
import requests.exceptions
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

import utils.config
import utils.entities

# The HTTP status codes of the data that does not exist, for example a
# file that is not published yet.
NOT_FOUND_STATUS_CODES = {404, 410}

# The HTTP status codes of the client errors that can be temporary:
# request timeout, too early and too many requests. The server errors
# (5xx) can be temporary too.
TEMPORARY_CLIENT_STATUS_CODES = {408, 425, 429}


class DataNotFoundError(ConnectionError):
    """
    Error raised when the remote data does not exist.

    The server answers that the URL is not found, for example because
    the file of the latest period is not published yet.
    """


def redact(text: str) -> str:
    """
    Hide the API keys and passwords in a text.

    The URL of a download, and so its errors, can include an API key,
    which must not end up in logs and reports, and so must passwords.
    Their values are also hidden as they appear in URLs and forms, with
    their special characters encoded.

    Parameters
    ----------
    text : str
        The text.

    Returns
    -------
    str
        The text without the values of the API keys and passwords.
    """
    for name, value in os.environ.items():
        if name.endswith(("_API_KEY", "_PASSWORD")) and value:
            for form in (
                value,
                urllib.parse.quote(value, safe=""),
                urllib.parse.quote_plus(value),
            ):
                text = text.replace(form, "***")
    return text


def _get_status_code(
    error: requests.exceptions.HTTPError | urllib.error.HTTPError,
) -> int | None:
    """
    Get the HTTP status code of an HTTP error.

    Parameters
    ----------
    error : requests.exceptions.HTTPError | urllib.error.HTTPError
        The HTTP error.

    Returns
    -------
    int | None
        The status code, or None if the error has no response.
    """
    if isinstance(error, urllib.error.HTTPError):
        return error.code
    if error.response is None:
        return None
    return error.response.status_code


def _is_temporary(status_code: int | None) -> bool:
    """
    Check whether an HTTP error can be temporary, and so be retried.

    Parameters
    ----------
    status_code : int | None
        The status code of the error, or None if it is unknown.

    Returns
    -------
    bool
        Whether the error can be temporary.
    """
    return (
        status_code is None
        or status_code >= 500
        or status_code in TEMPORARY_CLIENT_STATUS_CODES
    )


def _read_aspx_params(
    response: requests.Response, post_data_params: Mapping[str, str | int]
) -> dict[str, str | int]:
    """
    Read the ASPX parameters from the response.

    This function extracts relevant ASPX parameters such as
    `__VIEWSTATE` and `__EVENTVALIDATION` from the HTML content of the
    response and returns them with the provided POST data parameters.

    Parameters
    ----------
    response : requests.Response
        The response object from the GET request.
    post_data_params : Mapping[str, str | int]
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

    # Return the POST data parameters with the ASPX parameters added.
    return {
        **post_data_params,
        "__VIEWSTATE": viewstate,
        "__EVENTVALIDATION": eventvalidation,
    }


def fetch_data(  # noqa: C901
    url: str,
    content_type: str,
    timeout: int = 10,
    retries: int = 5,
    retry_delay: int = 5,
    read_with: str = "requests.get",
    encoding_type: str | None = None,
    read_as: str = "csv_table",
    csv_kwargs: dict[str, Any] | None = None,
    excel_kwargs: dict[str, Any] | None = None,
    verify_ssl: bool | str = True,
    request_params: Mapping[str, str] | None = None,
    post_data_params: Mapping[str, str | int] | None = None,
    post_json: Mapping[str, Any] | None = None,
    header_params: Mapping[str, str] | None = None,
    json_keys: list[str] | None = None,
    query_aspx_webpage: bool = False,
    get_cookies: bool = False,
) -> pd.DataFrame | pd.ExcelFile | str | requests.Response:
    """
    Fetch the data from the specified URL.

    This function supports fetching data in various formats such as CSV,
    Excel, HTML, and JSON. It retries after the errors that can be
    temporary (lost connections, timeouts, and the HTTP errors of busy
    or failing servers), and allows customization of the request
    parameters, headers, and data formats.

    Parameters
    ----------
    url : str
        The URL of the data source.
    content_type : str
        The type of the content to be fetched.
    timeout : int, optional
        The timeout for the request in seconds.
    retries : int, optional
        The number of attempts, in case of temporary errors.
    retry_delay : int, optional
        The delay between attempts in seconds.
    read_with : str, optional
        The library to use for reading the html content.
    encoding_type : str, optional
        The encoding to use for reading the content.
    read_as : str, optional
        The format to read the content as.
    csv_kwargs : dict[str, Any], optional
        The keyword arguments for reading CSV files.
    excel_kwargs : dict[str, Any], optional
        The keyword arguments for reading Excel files.
    verify_ssl : bool | str, optional
        Verify the SSL certificate, with the default certificates or
        with those in the file at this path.
    header_params : Mapping[str, str], optional
        The headers for the request.
    request_params : Mapping[str, str], optional
        The parameters for the request.
    post_data_params : Mapping[str, str | int], optional
        The data for the POST request.
    post_json : Mapping[str, Any], optional
        The JSON body for the POST request, instead of the data.
    json_keys : list[str], optional
        The keys to extract from the JSON response.
    query_aspx_webpage : bool, optional
        Whether to query the ASPX webpage.
    get_cookies : bool, optional
        Whether to get cookies from the initial GET request.

    Returns
    -------
    pandas.DataFrame | pandas.ExcelFile | str | requests.Response
        The fetched data as a DataFrame, Excel file, string, or
        response object.

    Raises
    ------
    ValueError
        If the content type, the library or the URL scheme is not
        supported.
    DataNotFoundError
        If the server answers that the data does not exist.
    ConnectionError
        If the server answers with another client error, or the data
        cannot be fetched within the specified number of attempts.
    """
    if csv_kwargs is None:
        csv_kwargs = {}
    if excel_kwargs is None:
        excel_kwargs = {}
    if request_params is None:
        request_params = {}
    if post_data_params is None:
        post_data_params = {}
    # Copy the headers, which are updated with cookies below.
    header_params = dict(header_params or {})
    if json_keys is None:
        json_keys = []

    # Try to fetch the data from the URL, and retry after the errors
    # that can be temporary: lost connections, timeouts, and the HTTP
    # errors of busy or failing servers.
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            if content_type == "csv":
                # Read the CSV file from the URL.
                return pd.read_csv(url, **csv_kwargs)

            if content_type == "excel":
                # Read the Excel file from the URL.
                return pd.read_excel(url, **excel_kwargs)

            if content_type == "html":
                if read_with == "urllib.request":
                    # Only open web URLs, not local files.
                    if not url.startswith(("http://", "https://")):
                        raise ValueError(
                            f"The URL {url} must use HTTP or HTTPS."
                        )

                    # Read the HTML content from the URL using
                    # the urllib.request module.
                    request = urllib.request.Request(url)  # noqa: S310
                    for key, value in header_params.items():
                        request.add_header(key, value)

                    # Send the request and return the response
                    # as a string.
                    return (
                        urllib.request.urlopen(  # noqa: S310
                            request, timeout=timeout
                        )
                        .read()
                        .decode("utf-8")
                    )

                if read_with in {"requests.get", "requests.post"}:
                    if get_cookies:
                        # Create a session to persist cookies.
                        session = requests.Session()

                        # Send a GET request to the URL to
                        # retrieve cookies.
                        session.get(
                            url,
                            timeout=timeout,
                            verify=verify_ssl,
                            headers=header_params,
                            params=request_params,
                        )

                        # Update the header parameters with
                        # the cookies.
                        header_params.update(
                            {
                                "Cookie": "; ".join(
                                    [
                                        f"{key}={value}"
                                        for key, value in session.cookies.get_dict().items()
                                    ]
                                )
                            }
                        )

                    if read_with == "requests.get":
                        # Send a GET request to the URL.
                        response = requests.get(
                            url,
                            timeout=timeout,
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
                                timeout=timeout,
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
                            timeout=timeout,
                            verify=verify_ssl,
                            headers=header_params,
                            params=request_params,
                            data=post_data_params,
                            json=post_json,
                        )

                    # Check if the request was successful.
                    response.raise_for_status()

                    # Set the encoding if provided.
                    if encoding_type:
                        response.encoding = encoding_type

                    if read_as == "csv_table":
                        # Return the content read as a CSV
                        # table.
                        return pd.read_csv(
                            StringIO(response.text), **csv_kwargs
                        )
                    if read_as == "excel_table":
                        # Return the content read as an Excel
                        # table.
                        return pd.read_excel(
                            BytesIO(response.content), **excel_kwargs
                        )
                    if read_as == "excel_file":
                        # Return the content read as an Excel
                        # file.
                        return pd.ExcelFile(BytesIO(response.content))
                    if read_as == "text":
                        # Return the content as a string.
                        return response.text
                    if read_as == "json":
                        # Read the content of the response
                        content = response.json()

                        # Loop over the JSON keys and extract
                        # the content.
                        for json_key in json_keys:
                            content = content[json_key]

                        # Return the content as a DataFrame.
                        return pd.DataFrame(content)
                    if read_as == "plain":
                        # Return just the response.
                        return response
                    raise ValueError(
                        f"The read_as parameter {read_as} is not supported."
                    )

                raise ValueError(f"Library {read_with} is not supported.")

            raise ValueError(
                f"The content type {content_type} is not supported."
            )

        except (requests.exceptions.HTTPError, urllib.error.HTTPError) as e:
            status_code = _get_status_code(e)
            if not _is_temporary(status_code):
                message = (
                    f"HTTP error {status_code} while fetching {redact(url)}."
                )
                if status_code in NOT_FOUND_STATUS_CODES:
                    raise DataNotFoundError(message) from e
                raise ConnectionError(message) from e
            error = e

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            urllib.error.URLError,
            ConnectionError,
            TimeoutError,
        ) as e:
            error = e

        logging.warning(
            f"Attempt {attempt}/{retries} to fetch remote data failed: "
            f"{redact(str(error))}"
        )
        if attempt < retries:
            time.sleep(retry_delay)

    raise ConnectionError(
        f"Failed to fetch {redact(url)} after {retries} attempts: "
        f"{redact(str(error))}"
    ) from error


def fetch_dataframe(
    url: str, content_type: str, **kwargs: Any
) -> pd.DataFrame:
    """
    Fetch data that is read as a table.

    This function fetches the data with fetch_data and checks that it is
    a table, as the data sources expect.

    Parameters
    ----------
    url : str
        The URL of the data.
    content_type : str
        The type of content, as for fetch_data.
    **kwargs : Any
        The other arguments of fetch_data.

    Returns
    -------
    pandas.DataFrame
        The data.

    Raises
    ------
    TypeError
        If the data is not a pandas DataFrame.
    """
    dataset = fetch_data(url, content_type, **kwargs)
    if not isinstance(dataset, pd.DataFrame):
        raise TypeError(
            f"The extracted data is a {type(dataset)} object, "
            "expected a pandas DataFrame."
        )
    return dataset


def read_manual_files(
    data_source_name: str,
    url: str,
    prefix: str,
    read_file: Callable[[str], pd.DataFrame],
    access: str = "",
) -> pd.DataFrame:
    """
    Read the data files that were downloaded manually.

    Some data sources have no download that can be automated. Their
    files are downloaded manually into the folder of manually downloaded
    electricity demand data, with names that start with a prefix.

    Parameters
    ----------
    data_source_name : str
        The name of the data source, for the error message.
    url : str
        The URL to download the files from, for the error message.
    prefix : str
        The start of the names of the files.
    read_file : Callable[[str], pandas.DataFrame]
        The function that reads a file from its path.
    access : str, optional
        How to get access to the files, such as " after registering on
        the website", for the error message.

    Returns
    -------
    pandas.DataFrame
        The data of all the files.

    Raises
    ------
    FileNotFoundError
        If no file starts with the prefix.
    """
    data_directory = utils.config.read_folders_structure()[
        "manually_downloaded_electricity_demand_folder"
    ]
    file_paths = [
        os.path.join(data_directory, file)
        for file in sorted(os.listdir(data_directory))
        if file.startswith(prefix)
    ]
    if not file_paths:
        raise FileNotFoundError(
            f"The data for {data_source_name} has not been found in the "
            f"folder {data_directory}. Please download the data manually "
            f"from {url}{access}. The data files must be named starting "
            f"with '{prefix}'."
        )
    return pd.concat([read_file(file_path) for file_path in file_paths])


def fetch_entsoe_demand(
    api_key: str,
    iso_alpha_3_code: str,
    start_date_and_time: pd.Timestamp,
    end_date_and_time: pd.Timestamp,
    retries: int = 3,
    retry_delay: int = 5,
) -> pd.Series:
    """
    Fetch the electricity demand time series from the ENTSO-E API.

    This function retrieves the hourly electricity demand time series
    for a specified country using the ENTSO-E API, whose client retries
    the request after connection errors. The data is returned as a
    pandas Series with the time index in the time zone of the country
    and the values in MW.

    Parameters
    ----------
    api_key : str
        The API key for the ENTSO-E API.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.
    start_date_and_time : pandas.Timestamp
        The start date and time of the data retrieval.
    end_date_and_time : pandas.Timestamp
        The end date and time of the data retrieval.
    retries : int, optional
        The number of attempts, in case of connection errors.
    retry_delay : int, optional
        The delay between attempts in seconds.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.
    """
    # Get the ISO Alpha-2 code of the country.
    iso_alpha_2_code = utils.entities.get_iso_alpha_2_code(iso_alpha_3_code)

    # Define the ENTSO-E API client, which retries after connection
    # errors.
    client = EntsoePandasClient(
        api_key=api_key, retry_count=retries, retry_delay=retry_delay
    )

    try:
        return client.query_load(
            iso_alpha_2_code,
            start=start_date_and_time,
            end=end_date_and_time,
        )["Actual Load"]

    except NoMatchingDataError:
        # If the data is not available, skip to the next country.
        logging.warning(
            f"No data available for {iso_alpha_3_code} between "
            f"{start_date_and_time.date()} and {end_date_and_time.date()}."
        )

        return pd.Series()

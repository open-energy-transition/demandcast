"""
License: AGPL-3.0.

Description:

    This module fetches remote data, with one function for each type of
    result: the response of a request, its text, an Excel file, or a
    table read from CSV, Excel or JSON. All of them retry after the
    errors that can be temporary, and hide the API keys in their
    messages. It also reads the files downloaded manually, and fetches
    the electricity demand of the ENTSO-E API.
"""

import inspect
import itertools
import logging
import os
import re
import time
import urllib.error
import urllib.parse
from collections.abc import Callable, Mapping
from io import BytesIO, StringIO
from typing import Any, Literal

import pandas as pd
import requests
import requests.exceptions
from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError

import utils.codes
import utils.paths

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


def _with_retries[T](
    url: str, fetch: Callable[[], T], retries: int, retry_delay: int
) -> T:
    """
    Fetch remote data, retrying after the errors that can be temporary.

    The errors that can be temporary are the lost connections, the
    timeouts, and the HTTP errors of busy or failing servers.

    Parameters
    ----------
    url : str
        The URL of the data, for the messages.
    fetch : Callable[[], T]
        The function that fetches the data.
    retries : int
        The number of attempts.
    retry_delay : int
        The delay between attempts in seconds.

    Returns
    -------
    T
        The data.

    Raises
    ------
    DataNotFoundError
        If the server answers that the data does not exist.
    ConnectionError
        If the server answers with another client error, or the data
        cannot be fetched within the specified number of attempts.
    """
    error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            return fetch()

        # The errors are raised again without the original ones, whose
        # messages can have the URL with an API key, and which a
        # traceback would show.
        except (requests.exceptions.HTTPError, urllib.error.HTTPError) as e:
            status_code = _get_status_code(e)
            if not _is_temporary(status_code):
                message = (
                    f"HTTP error {status_code} while fetching {redact(url)}."
                )
                if status_code in NOT_FOUND_STATUS_CODES:
                    raise DataNotFoundError(message) from None
                raise ConnectionError(message) from None
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
        f"{type(error).__name__}: {redact(str(error))}"
    ) from None


def _send(
    url: str,
    method: Literal["GET", "POST"],
    timeout: int,
    verify_ssl: bool | str,
    header_params: Mapping[str, str] | None,
    request_params: Mapping[str, str] | None,
    post_data_params: Mapping[str, str | int] | None,
    post_json: Mapping[str, Any] | None,
    query_aspx_webpage: bool,
    get_cookies: bool,
    encoding_type: str | None,
) -> requests.Response:
    """
    Send a request and check its response.

    Parameters
    ----------
    url : str
        The URL.
    method : str
        "GET" or "POST".
    timeout : int
        The timeout of the request in seconds.
    verify_ssl : bool | str
        Verify the SSL certificate, with the default certificates or
        with those in the file at this path.
    header_params : Mapping[str, str] | None
        The headers.
    request_params : Mapping[str, str] | None
        The parameters of the URL.
    post_data_params : Mapping[str, str | int] | None
        The data of a POST request.
    post_json : Mapping[str, Any] | None
        The JSON body of a POST request, instead of the data.
    query_aspx_webpage : bool
        Whether to read the form parameters of an ASPX page with a GET
        request first, and send them with the POST request.
    get_cookies : bool
        Whether to get the cookies of the page with a GET request
        first, and send them with the request.
    encoding_type : str | None
        The encoding of the text of the response, if not the one that
        the server gives.

    Returns
    -------
    requests.Response
        The response, whose status is a success.
    """
    # Copy the headers, which are updated with cookies below.
    headers = dict(header_params or {})
    params = dict(request_params or {})
    data = dict(post_data_params or {})

    if get_cookies:
        # Send a GET request to the URL to retrieve the cookies, and
        # send them with the request.
        session = requests.Session()
        session.get(
            url,
            timeout=timeout,
            verify=verify_ssl,
            headers=headers,
            params=params,
        )
        headers["Cookie"] = "; ".join(
            f"{key}={value}"
            for key, value in session.cookies.get_dict().items()
        )

    if method == "GET":
        response = requests.get(
            url,
            timeout=timeout,
            verify=verify_ssl,
            headers=headers,
            params=params,
        )
    else:
        if query_aspx_webpage:
            # Read the ASPX parameters of the page and add them to the
            # data of the POST request.
            page = requests.get(
                url,
                timeout=timeout,
                verify=verify_ssl,
                headers=headers,
                params=params,
            )
            data = _read_aspx_params(page, data)
        response = requests.post(
            url,
            timeout=timeout,
            verify=verify_ssl,
            headers=headers,
            params=params,
            data=data,
            json=post_json,
        )

    response.raise_for_status()
    if encoding_type:
        response.encoding = encoding_type
    return response


def fetch_response(
    url: str,
    method: Literal["GET", "POST"] = "GET",
    *,
    timeout: int = 10,
    retries: int = 5,
    retry_delay: int = 5,
    verify_ssl: bool | str = True,
    header_params: Mapping[str, str] | None = None,
    request_params: Mapping[str, str] | None = None,
    post_data_params: Mapping[str, str | int] | None = None,
    post_json: Mapping[str, Any] | None = None,
    query_aspx_webpage: bool = False,
    get_cookies: bool = False,
    encoding_type: str | None = None,
) -> requests.Response:
    """
    Fetch the response of a request.

    Parameters
    ----------
    url : str
        The URL.
    method : str, optional
        "GET" or "POST".
    timeout : int, optional
        The timeout of each attempt in seconds.
    retries : int, optional
        The number of attempts, in case of temporary errors.
    retry_delay : int, optional
        The delay between attempts in seconds.
    verify_ssl : bool | str, optional
        Verify the SSL certificate, with the default certificates or
        with those in the file at this path.
    header_params : Mapping[str, str], optional
        The headers.
    request_params : Mapping[str, str], optional
        The parameters of the URL.
    post_data_params : Mapping[str, str | int], optional
        The data of a POST request.
    post_json : Mapping[str, Any], optional
        The JSON body of a POST request, instead of the data.
    query_aspx_webpage : bool, optional
        Whether to send the form parameters of the ASPX page with a
        POST request.
    get_cookies : bool, optional
        Whether to send the cookies of the page with the request.
    encoding_type : str, optional
        The encoding of the text of the response, if not the one that
        the server gives.

    Returns
    -------
    requests.Response
        The response, whose status is a success.
    """
    return _with_retries(
        url,
        lambda: _send(
            url,
            method,
            timeout,
            verify_ssl,
            header_params,
            request_params,
            post_data_params,
            post_json,
            query_aspx_webpage,
            get_cookies,
            encoding_type,
        ),
        retries,
        retry_delay,
    )


def fetch_text(
    url: str, method: Literal["GET", "POST"] = "GET", **kwargs: Any
) -> str:
    """
    Fetch the text of a response.

    Parameters
    ----------
    url : str
        The URL.
    method : str, optional
        "GET" or "POST".
    **kwargs : Any
        The other options of fetch_response.

    Returns
    -------
    str
        The text of the response.
    """
    return fetch_response(url, method, **kwargs).text


def fetch_excel_file(
    url: str, method: Literal["GET", "POST"] = "GET", **kwargs: Any
) -> pd.ExcelFile:
    """
    Fetch an Excel file, to read its sheets.

    Parameters
    ----------
    url : str
        The URL.
    method : str, optional
        "GET" or "POST".
    **kwargs : Any
        The other options of fetch_response.

    Returns
    -------
    pandas.ExcelFile
        The Excel file.
    """
    return pd.ExcelFile(BytesIO(fetch_response(url, method, **kwargs).content))


def _check_table_options(
    content_type: str, read_with: str, read_as: str, kwargs: Mapping[str, Any]
) -> None:
    """
    Check the options of the fetch of a table.

    Parameters
    ----------
    content_type : str
        The type of the content.
    read_with : str
        The request of an "html" content.
    read_as : str
        How to read the response.
    kwargs : Mapping[str, Any]
        The other options of the request.

    Raises
    ------
    ValueError
        If the content type or the way of reading is not supported.
    TypeError
        If an option of the request is unknown.
    """
    if content_type not in {"csv", "excel", "html"}:
        raise ValueError(f"The content type {content_type} is not supported.")
    if read_as not in {"csv_table", "excel_table", "json"}:
        raise ValueError(f"The read_as parameter {read_as} is not supported.")
    if read_with not in {"requests.get", "requests.post"}:
        raise ValueError(f"Library {read_with} is not supported.")
    unknown = set(kwargs) - set(inspect.signature(fetch_response).parameters)
    if unknown:
        raise TypeError(f"Unknown options of the request: {sorted(unknown)}.")


def fetch_dataframe(
    url: str,
    content_type: Literal["csv", "excel", "html"],
    *,
    read_with: Literal["requests.get", "requests.post"] = "requests.get",
    read_as: Literal["csv_table", "excel_table", "json"] = "csv_table",
    csv_kwargs: dict[str, Any] | None = None,
    excel_kwargs: dict[str, Any] | None = None,
    json_keys: list[str] | None = None,
    retries: int = 5,
    retry_delay: int = 5,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Fetch data that is read as a table.

    Parameters
    ----------
    url : str
        The URL of the data.
    content_type : str
        "csv" or "excel" for a file that pandas reads from the URL, or
        "html" for the response of a request, read as read_as says.
    read_with : str, optional
        The request of an "html" content, "requests.get" or
        "requests.post".
    read_as : str, optional
        How to read the response: "csv_table", "excel_table" or "json".
    csv_kwargs : dict[str, Any], optional
        The keyword arguments of pandas.read_csv.
    excel_kwargs : dict[str, Any], optional
        The keyword arguments of pandas.read_excel.
    json_keys : list[str], optional
        The keys of the table in the JSON response.
    retries : int, optional
        The number of attempts, in case of temporary errors.
    retry_delay : int, optional
        The delay between attempts in seconds.
    **kwargs : Any
        The other options of the request, as for fetch_response.

    Returns
    -------
    pandas.DataFrame
        The data.
    """
    csv_kwargs = csv_kwargs or {}
    excel_kwargs = excel_kwargs or {}

    def fetch() -> pd.DataFrame:
        """
        Fetch and read the table once.

        Returns
        -------
        pandas.DataFrame
            The data.
        """
        if content_type == "csv":
            return pd.read_csv(url, **csv_kwargs)
        if content_type == "excel":
            return pd.read_excel(url, **excel_kwargs)
        response = _send(
            url,
            "POST" if read_with == "requests.post" else "GET",
            kwargs.get("timeout", 10),
            kwargs.get("verify_ssl", True),
            kwargs.get("header_params"),
            kwargs.get("request_params"),
            kwargs.get("post_data_params"),
            kwargs.get("post_json"),
            kwargs.get("query_aspx_webpage", False),
            kwargs.get("get_cookies", False),
            kwargs.get("encoding_type"),
        )
        if read_as == "csv_table":
            return pd.read_csv(StringIO(response.text), **csv_kwargs)
        if read_as == "excel_table":
            return pd.read_excel(BytesIO(response.content), **excel_kwargs)
        content = response.json()
        for json_key in json_keys or []:
            content = content[json_key]
        return pd.DataFrame(content)

    _check_table_options(content_type, read_with, read_as, kwargs)
    return _with_retries(url, fetch, retries, retry_delay)


def find_manual_files(prefix: str) -> list[str]:
    """
    Find the data files that were downloaded manually.

    The raw data (see utils.raw_data) keeps the files found while a
    request is downloaded, and gives them back when it is processed
    again.

    Parameters
    ----------
    prefix : str
        The start of the names of the files.

    Returns
    -------
    list[str]
        The paths of the files in the folder of manually downloaded
        electricity demand data whose names start with the prefix, in
        the order of their names.
    """
    data_directory = utils.paths.get_electricity_demand_folder(
        "manual_downloads"
    )
    if not os.path.isdir(data_directory):
        return []
    return [
        os.path.join(data_directory, file)
        for file in sorted(os.listdir(data_directory))
        if file.startswith(prefix)
    ]


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
    electricity demand data, with names that start with a prefix (see
    find_manual_files).

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
    file_paths = find_manual_files(prefix)
    if not file_paths:
        data_directory = utils.paths.get_electricity_demand_folder(
            "manual_downloads"
        )
        raise FileNotFoundError(
            f"The data for {data_source_name} has not been found in the "
            f"folder {data_directory}. Please download the data manually "
            f"from {url}{access}. The data files must be named starting "
            f"with '{prefix}'."
        )
    return pd.concat([read_file(file_path) for file_path in file_paths])


# The periods into which a request to ENTSO-E is split when it answers
# with an error, from the largest.
ENTSOE_SPLITS = ["MS", "D"]


def _query_entsoe_load(
    client: EntsoePandasClient,
    area: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    splits: list[str],
) -> pd.Series:
    """
    Query the load of an area of ENTSO-E, around the periods it fails.

    ENTSO-E answers some periods with an error of the server (400,
    "Unexpected ERROR occurred during processing of use case"), such as
    the load of Cyprus on 2025-10-09, while it gives the days around
    them. The period is then split into months, and a month that fails
    into days, and the days that fail are left out.

    Parameters
    ----------
    client : entsoe.EntsoePandasClient
        The client of the API of ENTSO-E.
    area : str
        The area of ENTSO-E.
    start : pandas.Timestamp
        The start of the period.
    end : pandas.Timestamp
        The end of the period.
    splits : list[str]
        The frequencies of the periods into which the period is split if
        it fails, from the largest.

    Returns
    -------
    pandas.Series
        The actual load in MW, without the days that fail.

    Raises
    ------
    requests.exceptions.HTTPError
        If ENTSO-E answers with another error than 400.
    """
    try:
        return client.query_load(area, start=start, end=end)["Actual Load"]
    except requests.exceptions.HTTPError as error:
        if error.response is None or error.response.status_code != 400:
            raise
    if not splits:
        # The error is not logged, since its URL has the API key.
        logging.warning(
            f"ENTSO-E answers the load of {area} from {start} to {end} "
            "with an error, so this period is left out."
        )
        return pd.Series(dtype="float64")

    edges = sorted(
        {
            start,
            end,
            *pd.date_range(start, end, freq=splits[0], inclusive="neither"),
        }
    )
    parts = []
    for part_start, part_end in itertools.pairwise(edges):
        try:
            part = _query_entsoe_load(
                client, area, part_start, part_end, splits[1:]
            )
        except NoMatchingDataError:
            continue
        if not part.empty:
            parts.append(part)
    if not parts:
        return pd.Series(dtype="float64")
    load = pd.concat(parts)
    return load[~load.index.duplicated()]


def fetch_entsoe_demand(
    api_key: str,
    iso_alpha_3_code: str,
    start_date_and_time: pd.Timestamp,
    end_date_and_time: pd.Timestamp,
    retries: int = 3,
    retry_delay: int = 5,
    area: str | None = None,
) -> pd.Series:
    """
    Fetch the electricity demand time series from the ENTSO-E API.

    This function retrieves the hourly electricity demand time series
    for a specified country using the ENTSO-E API, whose client retries
    the request after connection errors. The periods that ENTSO-E
    answers with an error of the server are split into months and days,
    and the days that still fail are left out (see _query_entsoe_load).
    The errors of the requests are raised without the API key, which
    their URL has.
    The data is returned as a
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
    area : str | None, optional
        The area of ENTSO-E, such as GB_NIR for Northern Ireland,
        instead of the country of the code.

    Returns
    -------
    pandas.Series
        The electricity demand time series in MW.
    """
    # Get the area of ENTSO-E: the ISO Alpha-2 code of the country, if
    # no other area is given.
    if area is None:
        area = utils.codes.get_iso_alpha_2_code(iso_alpha_3_code)

    # Define the ENTSO-E API client, which retries after connection
    # errors.
    client = EntsoePandasClient(
        api_key=api_key, retry_count=retries, retry_delay=retry_delay
    )

    try:
        return _query_entsoe_load(
            client,
            area,
            start_date_and_time,
            end_date_and_time,
            ENTSOE_SPLITS,
        )

    except NoMatchingDataError:
        # If the data is not available, skip to the next country.
        logging.warning(
            f"No data available for {iso_alpha_3_code} between "
            f"{start_date_and_time.date()} and {end_date_and_time.date()}."
        )

        return pd.Series()

    except requests.exceptions.RequestException as error:
        # The message of the error has the URL of the request, with the
        # API key, so the error is raised again without it, and without
        # the original error, which would show it in the logs.
        raise type(error)(
            str(error).replace(api_key, "***"), response=error.response
        ) from None

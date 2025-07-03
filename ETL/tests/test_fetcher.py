# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains tests for the fetcher module.
"""

import email.message
import urllib.error
from unittest.mock import patch

import pandas
import pytest
import requests
import utils.fetcher
from entsoe.exceptions import NoMatchingDataError


def test_fetch_data_csv():
    """
    Test fetching CSV data.

    This test mocks the pandas read_csv function to return a DataFrame.
    It checks that the fetch_data function returns a DataFrame when
    fetching CSV data.
    """
    with patch("pandas.read_csv"):
        pandas.read_csv.return_value = pandas.DataFrame({"a": [1]})
        dataset = utils.fetcher.fetch_data(
            "http://example.com/file.csv", "csv"
        )
        assert isinstance(dataset, pandas.DataFrame)


def test_fetch_data_excel():
    """
    Test fetching Excel data.

    This test mocks the pandas read_excel function to return a
    DataFrame. It checks that the fetch_data function returns a
    DataFrame when fetching Excel data.
    """
    with patch("pandas.read_excel"):
        pandas.read_excel.return_value = pandas.DataFrame({"a": [1]})
        dataset = utils.fetcher.fetch_data(
            "http://example.com/file.xlsx", "excel"
        )
        assert isinstance(dataset, pandas.DataFrame)


def test_fetch_data_html_urllib():
    """
    Test fetching HTML data using urllib.

    This test mocks the urllib.request.urlopen function to return a
    response with HTML content. It checks that the fetch_data function
    returns a string containing the HTML content.
    """
    with patch("urllib.request.urlopen"):
        urllib.request.urlopen.return_value.read.return_value = (
            b"<html>Content</html>"
        )
        html_text = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="urllib.request",
            header_params={"User-Agent": "test"},
        )
        assert isinstance(html_text, str) and "<html>" in html_text


def test_fetch_data_html_requests_get():
    """
    Test fetching HTML data using requests.get to read various format.

    This test mocks the requests.get function to read various formats
    of HTML data, including CSV, text, and plain response.
    """
    with patch("requests.get"):
        # Test reading of HTML content with tabular data.
        requests.get.return_value.text = "col1,col2\n1,2"
        dataset = utils.fetcher.fetch_data("http://example.com", "html")
        assert isinstance(dataset, pandas.DataFrame)

        # Test reading HTML content with text.
        requests.get.return_value.text = "text content"
        html_text = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="text"
        )
        assert isinstance(html_text, str) and html_text == "text content"

        # Test reading HTML content with plain format.
        requests.get.return_value = requests.Response()
        requests.get.return_value.status_code = 200
        response = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="plain"
        )
        assert isinstance(response, requests.Response)


def test_fetch_data_html_requests_post_json():
    """
    Test fetching HTML data using requests.post with JSON response.

    This test mocks the requests.post function to return a JSON response
    containing a list of dictionaries. It checks that the fetch_data
    function returns a DataFrame.
    """
    with patch("requests.post"):
        requests.post.return_value.json = lambda: {"data": [{"a": 1}]}
        dataset = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.post",
            read_as="json",
            json_keys=["data"],
        )
        assert isinstance(dataset, pandas.DataFrame)


def test_fetch_data_html_requests_post_aspx():
    """
    Test fetching HTML data from an ASPX page using requests.post.

    This test mocks the requests.get and requests.post functions to
    simulate fetching data from an ASPX page. It checks that the
    fetch_data function correctly retrieves the viewstate and
    eventvalidation values, and returns a DataFrame.
    """
    with (
        patch("requests.get"),
        patch("requests.post"),
    ):
        requests.get.return_value.text = """
            <input id="__VIEWSTATE" value="VS" />
            <input id="__EVENTVALIDATION" value="EV" />
        """
        requests.post.return_value.text = "col1,col2\n1,2"
        dataset = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.post",
            query_aspx_webpage=True,
        )
        assert isinstance(dataset, pandas.DataFrame)


def test_fetch_data_invalid_arguments():
    """
    Test fetch_data with invalid arguments.

    This test checks that the fetch_data function raises ValueError
    when provided with unsupported formats or read methods.
    """
    with pytest.raises(ValueError):
        utils.fetcher.fetch_data("http://example.com", "unsupported")
    with pytest.raises(ValueError):
        utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="unknown"
        )
    with pytest.raises(ValueError):
        utils.fetcher.fetch_data(
            "http://example.com", "html", read_with="unknown_lib"
        )


def test_fetch_entsoe_demand():
    """
    Test fetching demand data from ENTSOE.

    This test mocks the EntsoePandasClient to return a pandas.Series
    with a time series of demand data.
    """
    # Define a mock series to simulate demand data.
    mock_series = pandas.Series(
        [1, 2], index=pandas.date_range("2023-01-01", periods=2, freq="h")
    )

    # Patch the EntsoePandasClient to return the mock series.
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.return_value = pandas.DataFrame(
            {"Actual Load": mock_series}
        )
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "FR",
            pandas.Timestamp("2023-01-01"),
            pandas.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pandas.Series)


def test_fetch_entsoe_demand_errors():
    """
    Test fetching demand data from ENTSOE with errors.

    This test mocks the EntsoePandasClient to raise ConnectionError
    and NoMatchingDataError, and checks that the fetch_entsoe_demand
    function handles these errors correctly.
    """
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        # Test the EntsoePandasClient to raise ConnectionError.
        mock_client.return_value.query_load.side_effect = ConnectionError(
            "Connection failed"
        )
        with pytest.raises(ConnectionError):
            utils.fetcher.fetch_entsoe_demand(
                "dummy",
                "FR",
                pandas.Timestamp("2023-01-01"),
                pandas.Timestamp("2023-01-02"),
                retries=2,
                retry_delay=0,
            )

        # Test the EntsoePandasClient to raise NoMatchingDataError.
        mock_client.return_value.query_load.side_effect = NoMatchingDataError(
            "No data"
        )
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "FR",
            pandas.Timestamp("2023-01-01"),
            pandas.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pandas.Series) and result.empty


def test_fetch_data_requests_get_errors():
    """
    Test fetch_data with different errors.

    This test mocks the requests.get function to raise various
    exceptions, including ConnectionError, Timeout, HTTPError,
    RequestException, and SSLError. It checks that the fetch_data
    function handles these errors correctly.
    """
    # Define the erors to test.
    errors = [
        requests.exceptions.SSLError(),  # Subclass of ConnectionError
        requests.exceptions.ConnectionError(),  # Subclass of RequestException
        requests.exceptions.Timeout(),  # Subclass of RequestException
        requests.exceptions.HTTPError(),  # Subclass of RequestException
        requests.exceptions.RequestException(),
    ]

    # Iterate through the errors and test each one.
    for error in errors:
        with patch("requests.get"):
            requests.get.side_effect = error
            with pytest.raises(Exception):
                utils.fetcher.fetch_data(
                    "http://example.com", "html", retries=1, retry_delay=0
                )


def test_fetch_data_urlopen_errors():
    """
    Test fetch_data with different errors.

    This test mocks the urllib.request.urlopen function to raise
    various exceptions, including HTTPError and URLError. It checks
    that the fetch_data function handles these errors correctly.
    """
    # Define the erors to test.
    errors = [
        urllib.error.HTTPError(
            url="", code=0, msg="", hdrs=email.message.Message(), fp=None
        ),
        urllib.error.URLError(reason=""),
    ]

    # Iterate through the errors and test each one.
    for error in errors:
        with patch("urllib.request.urlopen"):
            urllib.request.urlopen.side_effect = error
            with pytest.raises(Exception):
                utils.fetcher.fetch_data(
                    "http://example.com",
                    "html",
                    retries=1,
                    retry_delay=0,
                    read_with="urllib.request",
                )

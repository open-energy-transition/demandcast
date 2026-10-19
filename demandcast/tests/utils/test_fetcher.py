"""
License: AGPL-3.0.

Description:

    This module contains tests for the fetcher module.
"""

import email.message
import re
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pandas as pd
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
    with patch("pandas.read_csv") as mock_read_csv:
        mock_read_csv.return_value = pd.DataFrame({"a": [1]})
        dataset = utils.fetcher.fetch_data(
            "http://example.com/file.csv", "csv"
        )
        assert isinstance(dataset, pd.DataFrame)


def test_fetch_data_excel():
    """
    Test fetching Excel data.

    This test mocks the pandas read_excel function to return a
    DataFrame. It checks that the fetch_data function returns a
    DataFrame when fetching Excel data.
    """
    with patch("pandas.read_excel") as mock_read_excel:
        mock_read_excel.return_value = pd.DataFrame({"a": [1]})
        dataset = utils.fetcher.fetch_data(
            "http://example.com/file.xlsx", "excel"
        )
        assert isinstance(dataset, pd.DataFrame)


def test_fetch_data_html_urllib():
    """
    Test fetching HTML data using urllib.

    This test mocks the urllib.request.urlopen function to return a
    response with HTML content. It checks that the fetch_data function
    returns a string containing the HTML content.
    """
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.read.return_value = b"<html>Content</html>"
        html_text = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="urllib.request",
            header_params={"User-Agent": "test"},
        )
        assert isinstance(html_text, str)
        assert "<html>" in html_text


def test_fetch_data_html_requests_get():
    """
    Test fetching HTML data using requests.get to read various format.

    This test mocks the requests.get function to read various formats
    of HTML data, including CSV, text, and plain response.
    """
    with patch("requests.get") as mock_get:
        # Test reading of HTML content with tabular data in CSV format.
        mock_get.return_value.text = "col1,col2\n1,2"
        dataset = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="csv_table"
        )
        assert isinstance(dataset, pd.DataFrame)

        # Prepare a mock Excel binary.
        df_original = pd.DataFrame({"a": [10, 20], "b": [30, 40]})
        excel_binary = BytesIO()
        with pd.ExcelWriter(excel_binary) as writer:
            df_original.to_excel(writer, index=False)
        excel_binary.seek(0)

        # Test reading of HTML content with tabular data in Excel
        # format.
        mock_get.return_value.content = excel_binary.getvalue()
        dataset = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="excel_table"
        )
        assert isinstance(dataset, pd.DataFrame)

        # Test reading of HTML content with tabular data as Excel file.
        mock_get.return_value.content = excel_binary.getvalue()
        dataset = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="excel_file"
        )
        assert isinstance(dataset, pd.ExcelFile)

        # Test reading HTML content with text.
        mock_get.return_value.text = "text content"
        html_text = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="text", encoding_type="utf-8"
        )
        assert isinstance(html_text, str)
        assert html_text == "text content"

        # Test reading HTML content with plain format.
        mock_get.return_value = requests.Response()
        mock_get.return_value.status_code = 200
        response = utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="plain"
        )
        assert isinstance(response, requests.Response)


def test_fetch_data_html_requests_get_with_cookies():
    """
    Test fetching HTML data using requests.get with cookies.

    This test mocks the requests.get and requests.Session functions to
    simulate fetching data with cookies. It checks that the fetch_data
    function returns a DataFrame.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.Session") as mock_session,
    ):
        mock_get.return_value.text = "col1,col2\n1,2"
        mock_session.return_value.cookies.get_dict.return_value = {
            "sessionid": "12345"
        }
        dataset = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.get",
            get_cookies=True,
        )
        assert isinstance(dataset, pd.DataFrame)


def test_fetch_data_default_header_params_not_reused():
    """
    Test that default header parameters are not reused across calls.

    This test validates that a first call with cookies enabled does not
    leak a Cookie header into a later call that relies on defaults.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.Session") as mock_session,
    ):
        mock_get.return_value.text = "col1,col2\n1,2"
        mock_session.return_value.cookies.get_dict.return_value = {
            "sessionid": "12345"
        }

        utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.get",
            get_cookies=True,
        )
        utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.get",
            get_cookies=False,
        )

        first_headers = mock_get.call_args_list[0].kwargs["headers"]
        second_headers = mock_get.call_args_list[1].kwargs["headers"]
        assert first_headers == {"Cookie": "sessionid=12345"}
        assert second_headers == {}


def test_fetch_data_html_requests_post_json():
    """
    Test fetching HTML data using requests.post with JSON response.

    This test mocks the requests.post function to return a JSON response
    containing a list of dictionaries. It checks that the fetch_data
    function returns a DataFrame.
    """
    with patch("requests.post") as mock_post:
        mock_post.return_value.json = lambda: {"data": [{"a": 1}]}
        dataset = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.post",
            read_as="json",
            json_keys=["data"],
        )
        assert isinstance(dataset, pd.DataFrame)


def test_fetch_data_html_requests_post_with_a_json_body():
    """Test that a JSON body is sent instead of the data."""
    with patch("requests.post") as mock_post:
        mock_post.return_value.json = lambda: {"items": [{"a": 1}]}
        utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.post",
            read_as="json",
            post_json={"startDate": "2024-01-01T00:00:00+03:00"},
            json_keys=["items"],
        )
    assert mock_post.call_args.kwargs["json"] == {
        "startDate": "2024-01-01T00:00:00+03:00"
    }


def test_redact_hides_the_passwords(monkeypatch):
    """Test that the values of the passwords are hidden too."""
    monkeypatch.setenv("EPIAS_PASSWORD", "password-value")

    assert utils.fetcher.redact("Failed with password-value.") == (
        "Failed with ***."
    )


def test_redact_hides_the_encoded_passwords(monkeypatch):
    """Test that the passwords are hidden also when encoded."""
    monkeypatch.setenv("EPIAS_PASSWORD", "pass word&1")

    assert utils.fetcher.redact(
        "username=user&password=pass+word%261 or pass%20word%261"
    ) == ("username=user&password=*** or ***")


def test_fetch_data_html_requests_post_aspx():
    """
    Test fetching HTML data from an ASPX page using requests.post.

    This test mocks the requests.get and requests.post functions to
    simulate fetching data from an ASPX page. It checks that the
    fetch_data function correctly retrieves the viewstate and
    eventvalidation values, and returns a DataFrame.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
    ):
        mock_get.return_value.text = """
            <input id="__VIEWSTATE" value="VS" />
            <input id="__EVENTVALIDATION" value="EV" />
        """
        mock_post.return_value.text = "col1,col2\n1,2"
        dataset = utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            read_with="requests.post",
            query_aspx_webpage=True,
        )
        assert isinstance(dataset, pd.DataFrame)


def test_fetch_data_invalid_arguments():
    """
    Test fetch_data with invalid arguments.

    This test checks that the fetch_data function raises ValueError
    when provided with unsupported formats or read methods.
    """
    with pytest.raises(
        ValueError, match="The content type unsupported is not supported"
    ):
        utils.fetcher.fetch_data("http://example.com", "unsupported")
    with (
        patch("utils.fetcher.requests.Session"),
        patch("utils.fetcher.requests.get"),
        pytest.raises(
            ValueError, match="The read_as parameter unknown is not supported"
        ),
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="unknown"
        )
    with pytest.raises(
        ValueError, match="Library unknown_lib is not supported"
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", read_with="unknown_lib"
        )


def test_fetch_dataframe():
    """Test that a table is fetched with the arguments of fetch_data."""
    table = pd.DataFrame({"Load": [1000.5]})
    with patch("utils.fetcher.fetch_data", return_value=table) as fetch_data:
        result = utils.fetcher.fetch_dataframe(
            "https://example.com/data.csv", "csv", csv_kwargs={"sep": ";"}
        )

    assert result is table
    fetch_data.assert_called_once_with(
        "https://example.com/data.csv", "csv", csv_kwargs={"sep": ";"}
    )


def test_fetch_dataframe_of_another_type():
    """Test that data that is not a table is an error."""
    with (
        patch("utils.fetcher.fetch_data", return_value="<html></html>"),
        pytest.raises(TypeError, match="expected a pandas DataFrame"),
    ):
        utils.fetcher.fetch_dataframe("https://example.com", "html")


def test_read_manual_files(tmp_folders, tmp_path):
    """Test that the files with the prefix are read and joined."""
    folder = tmp_path / "manual"
    folder.mkdir()
    tmp_folders["manually_downloaded_electricity_demand_folder"] = str(folder)
    (folder / "ABC_2.csv").write_text("load\n2\n")
    (folder / "ABC_1.csv").write_text("load\n1\n")
    (folder / "XYZ.csv").write_text("load\n9\n")

    dataset = utils.fetcher.read_manual_files(
        data_source_name="ABC",
        url="https://example.org",
        prefix="ABC",
        read_file=pd.read_csv,
    )

    assert dataset["load"].tolist() == [1, 2]


def test_read_manual_files_without_files(tmp_folders, tmp_path):
    """Test that the error says where and how to download the files."""
    tmp_folders["manually_downloaded_electricity_demand_folder"] = str(
        tmp_path
    )

    with pytest.raises(
        FileNotFoundError,
        match=re.escape(
            "manually from https://example.org after registering on the "
            "website. The data files must be named starting with 'ABC'."
        ),
    ):
        utils.fetcher.read_manual_files(
            data_source_name="ABC",
            url="https://example.org",
            prefix="ABC",
            read_file=pd.read_csv,
            access=" after registering on the website",
        )


def test_fetch_entsoe_demand():
    """
    Test fetching demand data from ENTSOE.

    This test mocks the EntsoePandasClient to return a pandas.Series
    with a time series of demand data.
    """
    # Define a mock series to simulate demand data.
    mock_series = pd.Series(
        [1, 2], index=pd.date_range("2023-01-01", periods=2, freq="h")
    )

    # Patch the EntsoePandasClient to return the mock series.
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.return_value = pd.DataFrame(
            {"Actual Load": mock_series}
        )

        # Test fetching demand data for a valid country code.
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "FRA",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)

        # Test with a country code that is added manually.
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "XKX",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)

        # Test with an area of ENTSO-E in place of the country.
        utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "GBR_NIR",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
            area="GB_NIR",
        )
        assert mock_client.return_value.query_load.call_args.args[0] == (
            "GB_NIR"
        )


def test_fetch_entsoe_demand_errors():
    """
    Test fetching demand data from ENTSOE with errors.

    This test mocks the EntsoePandasClient to raise a connection error
    and NoMatchingDataError, and checks that the fetch_entsoe_demand
    function lets the client retry the first and skips the second.
    """
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        # Test the EntsoePandasClient to raise a connection error after
        # its retries.
        mock_client.return_value.query_load.side_effect = (
            requests.exceptions.ConnectionError("Connection failed")
        )
        with pytest.raises(requests.exceptions.ConnectionError):
            utils.fetcher.fetch_entsoe_demand(
                "dummy",
                "FRA",
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
                retries=2,
                retry_delay=0,
            )
        mock_client.assert_called_once_with(
            api_key="dummy", retry_count=2, retry_delay=0
        )

        # Test the EntsoePandasClient to raise NoMatchingDataError.
        mock_client.return_value.query_load.side_effect = NoMatchingDataError(
            "No data"
        )
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "FRA",
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2023-01-02"),
        )
        assert isinstance(result, pd.Series)
        assert result.empty


def _http_error(status_code: int) -> requests.exceptions.HTTPError:
    """
    Make the HTTP error that requests raises for a status code.

    Parameters
    ----------
    status_code : int
        The HTTP status code.

    Returns
    -------
    requests.exceptions.HTTPError
        The HTTP error, with its response.
    """
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


@pytest.mark.parametrize(
    "error",
    [
        requests.exceptions.SSLError(),
        requests.exceptions.ConnectionError(),
        requests.exceptions.Timeout(),
        requests.exceptions.HTTPError(),
        _http_error(429),
        _http_error(503),
    ],
)
def test_fetch_data_retries_temporary_errors(error, caplog):
    """Test that the errors that can be temporary are retried."""
    with (
        patch("requests.get", side_effect=error) as mock_get,
        pytest.raises(ConnectionError, match="after 2 attempts"),
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", retries=2, retry_delay=0
        )

    assert mock_get.call_count == 2
    assert "Attempt 1/2" in caplog.text
    assert "Attempt 2/2" in caplog.text


@pytest.mark.parametrize("status_code", [404, 410])
def test_fetch_data_without_the_data(status_code):
    """Test that data that does not exist is an error at once."""
    with (
        patch("requests.get", side_effect=_http_error(status_code)) as get,
        pytest.raises(
            utils.fetcher.DataNotFoundError,
            match=f"HTTP error {status_code} while fetching "
            "http://example.com",
        ),
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", retries=3, retry_delay=0
        )

    assert get.call_count == 1


def test_fetch_data_with_a_client_error():
    """Test that a client error is an error at once, with its code."""
    with (
        patch("requests.get", side_effect=_http_error(403)) as mock_get,
        pytest.raises(ConnectionError, match="HTTP error 403") as error,
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", retries=3, retry_delay=0
        )

    assert not isinstance(error.value, utils.fetcher.DataNotFoundError)
    assert mock_get.call_count == 1


def test_fetch_data_with_other_errors():
    """Test that the errors of the request or the data are raised."""
    with (
        patch(
            "requests.get", side_effect=requests.exceptions.InvalidURL()
        ) as mock_get,
        pytest.raises(requests.exceptions.InvalidURL),
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", retries=3, retry_delay=0
        )
    assert mock_get.call_count == 1

    # A response that is not JSON.
    response = requests.Response()
    response.status_code = 200
    response._content = b"<html></html>"
    with (
        patch("requests.get", return_value=response),
        pytest.raises(requests.exceptions.JSONDecodeError),
    ):
        utils.fetcher.fetch_data(
            "http://example.com", "html", read_as="json", retry_delay=0
        )


def test_fetch_data_hides_the_api_keys(monkeypatch, caplog):
    """Test that the API keys are not in the errors and the logs."""
    monkeypatch.setenv("EIA_API_KEY", "secret-value")
    url = "http://example.com/?api_key=secret-value"

    with (
        patch(
            "requests.get",
            side_effect=requests.exceptions.ConnectionError(f"Failed: {url}"),
        ),
        pytest.raises(ConnectionError) as error,
    ):
        utils.fetcher.fetch_data(url, "html", retries=1, retry_delay=0)
    assert "secret-value" not in str(error.value)
    assert "api_key=***" in str(error.value)

    with (
        patch("requests.get", side_effect=_http_error(404)),
        pytest.raises(utils.fetcher.DataNotFoundError) as error,
    ):
        utils.fetcher.fetch_data(url, "html", retry_delay=0)
    assert "secret-value" not in str(error.value)

    assert "secret-value" not in caplog.text


@pytest.mark.parametrize(
    ("error", "expected_error", "expected_calls"),
    [
        (
            urllib.error.HTTPError(
                url="", code=404, msg="", hdrs=email.message.Message(), fp=None
            ),
            utils.fetcher.DataNotFoundError,
            1,
        ),
        (
            urllib.error.HTTPError(
                url="", code=503, msg="", hdrs=email.message.Message(), fp=None
            ),
            ConnectionError,
            2,
        ),
        (urllib.error.URLError(reason="DNS"), ConnectionError, 2),
        (TimeoutError(), ConnectionError, 2),
    ],
)
def test_fetch_data_urlopen_errors(error, expected_error, expected_calls):
    """Test that the errors of urllib are handled like the others."""
    with (
        patch("urllib.request.urlopen", side_effect=error) as mock_urlopen,
        pytest.raises(expected_error),
    ):
        utils.fetcher.fetch_data(
            "http://example.com",
            "html",
            retries=2,
            retry_delay=0,
            read_with="urllib.request",
        )

    assert mock_urlopen.call_count == expected_calls


def test_fetch_data_csv_with_a_connection_error():
    """Test that a CSV file read from a URL is retried as well."""
    with (
        patch(
            "pandas.read_csv", side_effect=urllib.error.URLError(reason="DNS")
        ) as mock_read_csv,
        pytest.raises(ConnectionError, match="after 3 attempts"),
    ):
        utils.fetcher.fetch_data(
            "http://example.com/data.csv", "csv", retry_delay=0, retries=3
        )

    assert mock_read_csv.call_count == 3

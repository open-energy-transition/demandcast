"""
License: AGPL-3.0.

Description:

    This module contains tests for the fetcher module.
"""

import email.message
import os
import pathlib
import re
import traceback
import urllib.error
import zoneinfo
from io import BytesIO
from unittest.mock import patch

import pandas as pd
import pytest
import requests
import utils.fetcher
import utils.paths
from entsoe.exceptions import NoMatchingDataError
from entsoe.mappings import Area


@pytest.mark.parametrize(
    ("content_type", "reader"), [("csv", "read_csv"), ("excel", "read_excel")]
)
def test_fetch_dataframe_of_a_file(content_type, reader):
    """Test that a CSV or Excel file is read from its URL by pandas."""
    table = pd.DataFrame({"a": [1]})
    with patch(f"pandas.{reader}", return_value=table) as mock_read:
        dataset = utils.fetcher.fetch_dataframe(
            "http://example.com/file", content_type, csv_kwargs={"sep": ";"}
        )

    assert dataset is table
    assert mock_read.call_args.args == ("http://example.com/file",)


def test_fetch_of_each_type():
    """Test the table, Excel file, text and response of a request."""
    excel_binary = BytesIO()
    with pd.ExcelWriter(excel_binary) as writer:
        pd.DataFrame({"a": [10, 20], "b": [30, 40]}).to_excel(
            writer, index=False
        )

    with patch("requests.get") as mock_get:
        mock_get.return_value.text = "col1,col2\n1,2"
        assert utils.fetcher.fetch_dataframe(
            "http://example.com", "html"
        ).columns.tolist() == ["col1", "col2"]

        mock_get.return_value.content = excel_binary.getvalue()
        assert utils.fetcher.fetch_dataframe(
            "http://example.com", "html", read_as="excel_table"
        )["b"].tolist() == [30, 40]
        assert isinstance(
            utils.fetcher.fetch_excel_file("http://example.com"), pd.ExcelFile
        )

        mock_get.return_value.text = "text content"
        assert (
            utils.fetcher.fetch_text(
                "http://example.com", encoding_type="utf-8"
            )
            == "text content"
        )
        assert mock_get.return_value.encoding == "utf-8"

        mock_get.return_value = requests.Response()
        mock_get.return_value.status_code = 200
        assert isinstance(
            utils.fetcher.fetch_response("http://example.com"),
            requests.Response,
        )


def test_fetch_with_cookies():
    """
    Test that the cookies of the page are sent with the request.

    The headers of a call do not leak into a later call.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.Session") as mock_session,
    ):
        mock_get.return_value.text = "col1,col2\n1,2"
        mock_session.return_value.cookies.get_dict.return_value = {
            "sessionid": "12345"
        }

        utils.fetcher.fetch_dataframe(
            "http://example.com", "html", get_cookies=True
        )
        utils.fetcher.fetch_text("http://example.com")

    first_headers = mock_get.call_args_list[0].kwargs["headers"]
    second_headers = mock_get.call_args_list[1].kwargs["headers"]
    assert first_headers == {"Cookie": "sessionid=12345"}
    assert second_headers == {}


def test_fetch_json_with_a_post_request():
    """Test a table of a JSON response to a POST request with a body."""
    with patch("requests.post") as mock_post:
        mock_post.return_value.json = lambda: {"data": [{"a": 1}]}
        dataset = utils.fetcher.fetch_dataframe(
            "http://example.com",
            "html",
            read_with="requests.post",
            read_as="json",
            post_json={"startDate": "2024-01-01T00:00:00+03:00"},
            json_keys=["data"],
        )

    assert dataset["a"].tolist() == [1]
    assert mock_post.call_args.kwargs["json"] == {
        "startDate": "2024-01-01T00:00:00+03:00"
    }


def test_fetch_text_with_a_post_request():
    """Test that the data of a POST request is sent."""
    with patch("requests.post") as mock_post:
        mock_post.return_value.text = "ticket"
        text = utils.fetcher.fetch_text(
            "http://example.com", "POST", post_data_params={"user": "a"}
        )

    assert text == "ticket"
    assert mock_post.call_args.kwargs["data"] == {"user": "a"}


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


def test_fetch_from_an_aspx_page():
    """
    Test that the form parameters of an ASPX page are sent.

    The view state and the event validation of the page are read with a
    GET request and sent with the POST request.
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
        dataset = utils.fetcher.fetch_dataframe(
            "http://example.com",
            "html",
            read_with="requests.post",
            query_aspx_webpage=True,
        )

    assert dataset.columns.tolist() == ["col1", "col2"]
    assert mock_post.call_args.kwargs["data"]["__VIEWSTATE"] == "VS"


def test_fetch_dataframe_with_invalid_arguments():
    """Test that the options that are not supported are errors."""
    with pytest.raises(
        ValueError, match="The content type unsupported is not supported"
    ):
        utils.fetcher.fetch_dataframe(
            "http://example.com",
            "unsupported",  # type: ignore[arg-type]
        )
    with pytest.raises(
        ValueError, match="The read_as parameter unknown is not supported"
    ):
        utils.fetcher.fetch_dataframe(
            "http://example.com",
            "html",
            read_as="unknown",  # type: ignore[arg-type]
        )
    with pytest.raises(
        ValueError, match="Library unknown_lib is not supported"
    ):
        utils.fetcher.fetch_dataframe(
            "http://example.com",
            "html",
            read_with="unknown_lib",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError, match="Unknown options of the request"):
        utils.fetcher.fetch_dataframe(
            "http://example.com", "html", read_as="json", jsonkeys=["a"]
        )


def test_read_manual_files():
    """Test that the files with the prefix are read and joined."""
    folder = pathlib.Path(
        utils.paths.get_electricity_demand_folder("manual_downloads")
    )
    folder.mkdir(parents=True)
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


@pytest.mark.parametrize("exists", [True, False])
def test_read_manual_files_without_files(exists):
    """Test that the error says where and how to download the files."""
    if exists:
        os.makedirs(
            utils.paths.get_electricity_demand_folder("manual_downloads")
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
def test_fetch_retries_temporary_errors(error, caplog):
    """Test that the errors that can be temporary are retried."""
    with (
        patch("requests.get", side_effect=error) as mock_get,
        pytest.raises(ConnectionError, match="after 2 attempts"),
    ):
        utils.fetcher.fetch_response(
            "http://example.com", retries=2, retry_delay=0
        )

    assert mock_get.call_count == 2
    assert "Attempt 1/2" in caplog.text
    assert "Attempt 2/2" in caplog.text


@pytest.mark.parametrize("status_code", [404, 410])
def test_fetch_without_the_data(status_code):
    """Test that data that does not exist is an error at once."""
    with (
        patch("requests.get", side_effect=_http_error(status_code)) as get,
        pytest.raises(
            utils.fetcher.DataNotFoundError,
            match=f"HTTP error {status_code} while fetching "
            "http://example.com",
        ),
    ):
        utils.fetcher.fetch_response(
            "http://example.com", retries=3, retry_delay=0
        )

    assert get.call_count == 1


def test_fetch_with_a_client_error():
    """Test that a client error is an error at once, with its code."""
    with (
        patch("requests.get", side_effect=_http_error(403)) as mock_get,
        pytest.raises(ConnectionError, match="HTTP error 403") as error,
    ):
        utils.fetcher.fetch_response(
            "http://example.com", retries=3, retry_delay=0
        )

    assert not isinstance(error.value, utils.fetcher.DataNotFoundError)
    assert mock_get.call_count == 1


def test_fetch_with_other_errors():
    """Test that the errors of the request or the data are raised."""
    with (
        patch(
            "requests.get", side_effect=requests.exceptions.InvalidURL()
        ) as mock_get,
        pytest.raises(requests.exceptions.InvalidURL),
    ):
        utils.fetcher.fetch_response(
            "http://example.com", retries=3, retry_delay=0
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
        utils.fetcher.fetch_dataframe(
            "http://example.com", "html", read_as="json", retry_delay=0
        )


def test_fetch_hides_the_api_keys(monkeypatch, caplog):
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
        utils.fetcher.fetch_response(url, retries=1, retry_delay=0)
    assert "secret-value" not in str(error.value)
    assert "api_key=***" in str(error.value)
    # Nor in the traceback, which shows the errors that caused it.
    assert "secret-value" not in "".join(
        traceback.format_exception(error.value)
    )

    not_found = _http_error(404)
    not_found.args = (f"404 Client Error: Not Found for url: {url}",)
    with (
        patch("requests.get", side_effect=not_found),
        pytest.raises(utils.fetcher.DataNotFoundError) as error,
    ):
        utils.fetcher.fetch_response(url, retry_delay=0)
    assert "secret-value" not in str(error.value)
    assert "secret-value" not in "".join(
        traceback.format_exception(error.value)
    )

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
def test_fetch_urllib_errors(error, expected_error, expected_calls):
    """Test that the errors of urllib, raised by pandas, are handled."""
    with (
        patch("pandas.read_csv", side_effect=error) as mock_read_csv,
        pytest.raises(expected_error),
    ):
        utils.fetcher.fetch_dataframe(
            "http://example.com/data.csv", "csv", retries=2, retry_delay=0
        )

    assert mock_read_csv.call_count == expected_calls


def test_fetch_csv_with_a_connection_error():
    """Test that a CSV file read from a URL is retried as well."""
    with (
        patch(
            "pandas.read_csv", side_effect=urllib.error.URLError(reason="DNS")
        ) as mock_read_csv,
        pytest.raises(ConnectionError, match="after 3 attempts"),
    ):
        utils.fetcher.fetch_dataframe(
            "http://example.com/data.csv", "csv", retry_delay=0, retries=3
        )

    assert mock_read_csv.call_count == 3


def _query_load_failing(status_code: int):
    """
    Make a query of the load that fails on 2025-10-09 with an error.

    Returns
    -------
    Callable
        The query, which gives a load of 1 MW a day, and raises the
        error for the periods with 2025-10-09, and no data in December.
    """

    def query_load(_area, start, end):
        if start <= pd.Timestamp("2025-10-09", tz="UTC") < end:
            response = requests.Response()
            response.status_code = status_code
            raise requests.exceptions.HTTPError("Error", response=response)
        if start >= pd.Timestamp("2025-12-01", tz="UTC"):
            raise NoMatchingDataError
        times = pd.date_range(start, end, freq="D", inclusive="left")
        return pd.DataFrame({"Actual Load": 1.0}, index=times)

    return query_load


def test_fetch_entsoe_demand_with_failing_days(caplog):
    """Test that the days that ENTSO-E fails to give are left out."""
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            400
        )
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "CYP",
            pd.Timestamp("2025-09-01", tz="UTC"),
            pd.Timestamp("2026-01-01", tz="UTC"),
        )

    # The period is split into months, and October into days, so only
    # 2025-10-09 is left out, and December has no data.
    assert len(result) == 30 + 30 + 30
    assert pd.Timestamp("2025-10-09", tz="UTC") not in result.index
    assert "2025-10-09 00:00:00+00:00" in caplog.text
    assert "left out" in caplog.text

    # A period whose only day fails gives no data.
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            400
        )
        result = utils.fetcher.fetch_entsoe_demand(
            "dummy",
            "CYP",
            pd.Timestamp("2025-10-09", tz="UTC"),
            pd.Timestamp("2025-10-10", tz="UTC"),
        )
    assert result.empty


def test_fetch_entsoe_demand_with_other_errors():
    """Test that an error of ENTSO-E other than 400 is raised."""
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = _query_load_failing(
            500
        )
        with pytest.raises(requests.exceptions.HTTPError):
            utils.fetcher.fetch_entsoe_demand(
                "dummy",
                "CYP",
                pd.Timestamp("2025-09-01", tz="UTC"),
                pd.Timestamp("2025-11-01", tz="UTC"),
            )


def test_time_zones_of_entsoe_areas():
    """
    Test that the time zones of the areas of ENTSO-E can be read.

    The client of ENTSO-E gives old names, such as Europe/Kiev, which
    the time zones of some systems leave out, so they are read from the
    package tzdata.
    """
    unknown = []
    for area in Area:
        try:
            zoneinfo.ZoneInfo(area.tz)
        except zoneinfo.ZoneInfoNotFoundError:
            unknown.append(area.tz)

    assert unknown == []


def test_fetch_entsoe_demand_errors_without_api_key():
    """Test that the errors of ENTSO-E do not show the API key."""
    # The key is made when the test runs, since the tracebacks of recent
    # versions of Python show the source of the test.
    api_key = "-".join(["secret", "key"])
    with patch("utils.fetcher.EntsoePandasClient") as mock_client:
        mock_client.return_value.query_load.side_effect = (
            requests.exceptions.ConnectionError(
                f"Max retries exceeded with url: /api?securityToken={api_key}"
            )
        )
        with pytest.raises(requests.exceptions.ConnectionError) as error:
            utils.fetcher.fetch_entsoe_demand(
                api_key,
                "FRA",
                pd.Timestamp("2023-01-01"),
                pd.Timestamp("2023-01-02"),
            )

    # The error and its traceback do not have the API key.
    traceback_text = "".join(traceback.format_exception(error.value))
    assert api_key not in traceback_text
    assert "securityToken=***" in traceback_text

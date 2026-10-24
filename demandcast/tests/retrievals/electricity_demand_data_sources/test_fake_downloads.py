"""
License: AGPL-3.0.

Description:

    Tests of the fixture that serves synthetic files instead of
    downloads, through each way in which utils.fetcher downloads.
"""

import pandas as pd
import pytest

import utils.fetcher

URL = "https://example.com/data.csv"


@pytest.mark.parametrize(
    ("fetch_arguments", "methods"),
    [
        ({"content_type": "csv"}, ["GET"]),
        ({"content_type": "html", "read_with": "requests.get"}, ["GET"]),
        ({"content_type": "html", "read_with": "requests.post"}, ["POST"]),
        (
            {
                "content_type": "html",
                "read_with": "requests.get",
                "get_cookies": True,
            },
            ["GET", "GET"],
        ),
    ],
)
def test_fetch_table(fake_downloads, fetch_arguments, methods):
    """Test that fetch_dataframe reads the served file as a table."""
    fake_downloads.serve(URL, "aemo_nem.csv")
    fake_downloads.serve(URL, "aemo_nem.csv", method="POST")

    table = utils.fetcher.fetch_dataframe(URL, **fetch_arguments)

    assert table["TOTALDEMAND"].tolist() == [6000.5, 6010.25, 7000.0]
    assert [method for method, __, __ in fake_downloads.requests] == methods


def test_fetch_text(fake_downloads):
    """Test that fetch_text reads the served file."""
    fake_downloads.serve(URL, "aemo_nem.csv")

    text = utils.fetcher.fetch_text(URL)

    assert text.startswith("REGION,SETTLEMENTDATE,TOTALDEMAND")


def test_fetch_excel_with_the_options_of_the_request(fake_downloads, tmp_path):
    """Test that an Excel file is downloaded with the options given."""
    file_path = tmp_path / "data.xlsx"
    pd.DataFrame({"TOTALDEMAND": [6000.5]}).to_excel(file_path, index=False)
    fake_downloads.serve(URL, file_path)

    table = utils.fetcher.fetch_dataframe(
        URL,
        "excel",
        header_params={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )

    assert table["TOTALDEMAND"].tolist() == [6000.5]
    [(method, url, options)] = fake_downloads.requests
    assert (method, url) == ("GET", URL)
    assert options["headers"]["User-Agent"] == "Mozilla/5.0"
    assert options["timeout"] == 30


@pytest.mark.usefixtures("fake_downloads")
def test_unexpected_download():
    """Test that a download of a URL without a file fails at once."""
    with pytest.raises(AssertionError, match="Unexpected download: GET"):
        utils.fetcher.fetch_response(URL)

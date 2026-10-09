"""
License: AGPL-3.0.

Description:

    Tests of the fixture that serves synthetic files instead of
    downloads, through each way in which fetch_data downloads.
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
    """Test that fetch_data reads the served file as a table."""
    fake_downloads.serve(URL, "aemo_nem.csv")
    fake_downloads.serve(URL, "aemo_nem.csv", method="POST")

    table = utils.fetcher.fetch_data(URL, **fetch_arguments)

    assert isinstance(table, pd.DataFrame)
    assert table["TOTALDEMAND"].tolist() == [6000.5, 6010.25, 7000.0]
    assert [method for method, __, __ in fake_downloads.requests] == methods


def test_fetch_text_with_urllib(fake_downloads):
    """Test that fetch_data reads the served file with urllib."""
    fake_downloads.serve(URL, "aemo_nem.csv")

    text = utils.fetcher.fetch_data(URL, "html", read_with="urllib.request")

    assert isinstance(text, str)
    assert text.startswith("REGION,SETTLEMENTDATE,TOTALDEMAND")


def test_fetch_excel_with_storage_options(fake_downloads, tmp_path):
    """Test that the storage options of pandas are the headers."""
    file_path = tmp_path / "data.xlsx"
    pd.DataFrame({"TOTALDEMAND": [6000.5]}).to_excel(file_path, index=False)
    fake_downloads.serve(URL, file_path)

    table = utils.fetcher.fetch_data(
        URL,
        "excel",
        excel_kwargs={"storage_options": {"User-Agent": "Mozilla/5.0"}},
    )

    assert isinstance(table, pd.DataFrame)
    assert table["TOTALDEMAND"].tolist() == [6000.5]
    assert fake_downloads.requests == [
        ("GET", URL, {"headers": {"User-Agent": "Mozilla/5.0"}})
    ]


@pytest.mark.usefixtures("fake_downloads")
def test_unexpected_download():
    """Test that a download of a URL without a file fails at once."""
    with pytest.raises(AssertionError, match="Unexpected download: GET"):
        utils.fetcher.fetch_data(URL, "html")

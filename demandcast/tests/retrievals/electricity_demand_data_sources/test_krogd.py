"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of electricity demand data from KROGD.
"""

import datetime as dt
import logging

import pandas as pd
import pytest

from retrievals.electricity_demand_data_sources import krogd

PAGE_URL = "https://www.data.go.kr/data/15065266/fileData.do"
HISTORY_URL = "https://www.data.go.kr/tcs/dss/selectHistAndCsvData.do"
DETAILS_URL = "https://www.data.go.kr/tcs/dss/selectDpkDetailInfo.do"
CURRENT_FILE_URL = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
LIMIT_URL = "https://www.data.go.kr/cmm/cmm/check-limit.json"


def test_get_available_requests(fake_downloads):
    """
    Test that the requests are the latest version of each year.

    The file of the current version comes from the request of the
    download button of the page, with the identifier of the version.
    """
    fake_downloads.serve(PAGE_URL, "krogd_page.html")
    fake_downloads.serve(
        CURRENT_FILE_URL, "krogd_current_file.json", method="POST"
    )
    fake_downloads.serve(HISTORY_URL, "krogd_history.html", method="POST")
    # The fake downloads serve one file for a URL, so the details of the
    # versions are the same.
    fake_downloads.serve(
        DETAILS_URL, "krogd_details_20241231.html", method="POST"
    )

    requests = krogd.get_available_requests(
        "KOR", dt.date(2013, 1, 1), dt.date(2025, 12, 31)
    )

    # The version that ends in July 2024 is left out for the one that
    # ends in December, and the details are asked for each version.
    assert requests == [
        (
            pd.Timestamp("2013-01-01"),
            pd.Timestamp("2024-12-31"),
            "FILE_000000003092319",
        ),
        (
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2025-12-31"),
            "FILE_000000003601951",
        ),
    ]
    assert [
        request[2]["data"]["publicDataHistSn"]
        for request in fake_downloads.requests
        if request[1] == DETAILS_URL
    ] == ["2", "3"]
    assert [
        request[2]["data"]["publicDataDetailPk"]
        for request in fake_downloads.requests
        if request[1] == CURRENT_FILE_URL
    ] == ["uddi:6ade08d2-0014-4d22-b10c-c811e3273c70"]


def test_get_available_requests_without_current_file(fake_downloads):
    """Test that a current version without file stops the retrieval."""
    fake_downloads.serve(PAGE_URL, "krogd_page.html")
    fake_downloads.serve(
        CURRENT_FILE_URL, "krogd_no_current_file.json", method="POST"
    )

    with pytest.raises(ValueError, match="no file for the current version"):
        krogd.get_available_requests(
            "KOR", dt.date(2013, 1, 1), dt.date(2025, 12, 31)
        )


def test_download_and_extract_data_for_request(
    fake_downloads, assert_demand, caplog
):
    """
    Test that the hourly columns of the Korean files are read.

    The download limit of the portal is checked before the download.
    """
    fake_downloads.serve(LIMIT_URL, "krogd_limit.json", method="POST")
    fake_downloads.serve(
        krogd.get_url("FILE_000000003092319"), "krogd_2024.csv"
    )
    caplog.set_level(logging.INFO)

    time_series = krogd.download_and_extract_data_for_request(
        (
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-12-31"),
            "FILE_000000003092319",
        ),
        "KOR",
    )

    assert "from 2024-01-01 to 2024-12-31" in caplog.text
    # The times mark the end of each hour, and the empty rows at the end
    # of the file are left out.
    assert_demand(
        time_series,
        "Asia/Seoul",
        {
            "2023-12-31 16:00": 60000.5,
            "2023-12-31 17:00": 59000.25,
            "2024-01-01 15:00": 65000.75,
        },
    )


def test_download_past_the_limit(fake_downloads):
    """Test that a download stops when the portal asks for a CAPTCHA."""
    fake_downloads.serve(LIMIT_URL, "krogd_limit_captcha.json", method="POST")

    with pytest.raises(ConnectionError, match="CAPTCHA"):
        krogd.download_and_extract_data_for_request(
            (
                pd.Timestamp("2024-01-01"),
                pd.Timestamp("2024-12-31"),
                "FILE_000000003092319",
            ),
            "KOR",
        )

    # The file is not requested.
    assert [request[1] for request in fake_downloads.requests] == [LIMIT_URL]

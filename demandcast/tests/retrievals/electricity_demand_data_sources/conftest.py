"""
License: AGPL-3.0.

Description:

    Shared fixtures for the tests of the electricity demand data
    sources. They serve synthetic files instead of downloads, so that
    the modules parse them as they parse the files of the data sources,
    and check the electricity demand that the modules return.
"""

import io
import pathlib
import urllib.request
from typing import Any

import pandas as pd
import pytest
import requests

# The folder of the synthetic files that replace the downloads.
FIXTURES_FOLDER = pathlib.Path(__file__).parent / "fixtures"


class FakeDownloads:
    """
    Synthetic files served instead of downloads.

    Attributes
    ----------
    requests : list[tuple[str, str, dict[str, Any]]]
        The method, URL and keyword arguments of each download, in the
        order of the downloads.
    """

    def __init__(self) -> None:
        self._files: dict[tuple[str, str], pathlib.Path] = {}
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def serve(
        self, url: str, file_name: str | pathlib.Path, method: str = "GET"
    ) -> None:
        """
        Serve a file of the fixtures folder at a URL.

        Parameters
        ----------
        url : str
            The URL of the download.
        file_name : str | pathlib.Path
            The name of the file in the fixtures folder, or the path of
            a file that the test wrote.
        method : str, optional
            The HTTP method of the download, "GET" or "POST".
        """
        self._files[(method, url)] = FIXTURES_FOLDER / file_name

    def get_file(self, method: str, url: str, **kwargs: Any) -> pathlib.Path:
        """
        Record a download and get the file served at its URL.

        Parameters
        ----------
        method : str
            The HTTP method of the download.
        url : str
            The URL of the download.
        **kwargs : Any
            The other arguments of the download, such as its parameters.

        Returns
        -------
        pathlib.Path
            The file served at the URL.

        Raises
        ------
        AssertionError
            If no file is served at the URL.
        """
        self.requests.append((method, url, kwargs))
        if (method, url) not in self._files:
            raise AssertionError(f"Unexpected download: {method} {url}")
        return self._files[(method, url)]


@pytest.fixture
def manual_downloads_folder(tmp_folders):
    """
    Create the folder of the manually downloaded files, empty.

    Returns
    -------
    pathlib.Path
        The folder, in a temporary folder.
    """
    folder = pathlib.Path(
        tmp_folders["manually_downloaded_electricity_demand_folder"]
    )
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def fake_downloads(monkeypatch):
    """
    Replace the downloads with synthetic files.

    The downloads with requests, urllib and pandas get the files that
    the test serves, and fail for the other URLs.

    Returns
    -------
    FakeDownloads
        The files to serve and the downloads made.
    """
    downloads = FakeDownloads()

    def send(method: str):
        def request(url: str, **kwargs: Any) -> requests.Response:
            response = requests.Response()
            response.status_code = 200
            response.url = url
            response.raw = io.BytesIO(
                downloads.get_file(method, url, **kwargs).read_bytes()
            )
            return response

        return request

    class Session:
        """A session of requests that gets the served files."""

        def __init__(self) -> None:
            self.cookies = requests.cookies.RequestsCookieJar()
            self.get = send("GET")

    def urlopen(request: urllib.request.Request, **kwargs: Any) -> io.BytesIO:
        return io.BytesIO(
            downloads.get_file("GET", request.full_url, **kwargs).read_bytes()
        )

    def read_with(reader):
        def read(source: Any, *args: Any, **kwargs: Any) -> Any:
            if isinstance(source, str) and source.startswith("http"):
                source = downloads.get_file("GET", source)
            return reader(source, *args, **kwargs)

        return read

    monkeypatch.setattr(requests, "get", send("GET"))
    monkeypatch.setattr(requests, "post", send("POST"))
    monkeypatch.setattr(requests, "Session", Session)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(pd, "read_csv", read_with(pd.read_csv))
    monkeypatch.setattr(pd, "read_excel", read_with(pd.read_excel))

    return downloads


def _assert_demand(
    time_series: pd.Series,
    time_zone: str,
    expected: dict[str, float],
    dtype: str = "float64",
) -> None:
    """
    Check the electricity demand that a data source returns.

    Parameters
    ----------
    time_series : pandas.Series
        The electricity demand that the data source returns.
    time_zone : str
        The time zone of its index, such as "UTC" or "Europe/Paris".
    expected : dict[str, float]
        The expected electricity demand in MW, in its order, by time in
        UTC in the format "YYYY-MM-DD HH:MM". The names of the series
        and of its index are not checked.
    dtype : str, optional
        The expected data type of the values.
    """
    assert isinstance(time_series.index, pd.DatetimeIndex)
    assert str(time_series.index.tz) == time_zone
    pd.testing.assert_series_equal(
        pd.Series(
            time_series.to_numpy(),
            index=time_series.index.tz_convert("UTC").strftime(
                "%Y-%m-%d %H:%M"
            ),
        ),
        pd.Series(expected, dtype=dtype),
        check_names=False,
    )


@pytest.fixture
def assert_demand():
    """
    Get a function that checks the electricity demand of a data source.

    Returns
    -------
    Callable
        A function that takes the electricity demand that a data source
        returns, the time zone of its index, the expected values in MW
        by time in UTC and, optionally, their data type.
    """
    return _assert_demand

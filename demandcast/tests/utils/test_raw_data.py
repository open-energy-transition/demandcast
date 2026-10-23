"""
License: AGPL-3.0.

Description:

    Tests for the raw data of electricity demand: the requests encoded
    as JSON, the responses recorded and replayed, and their versions.
"""

import datetime
import os
import pathlib
import urllib.request

import pandas as pd
import pytest
import requests

import utils.fetcher
import utils.paths
import utils.raw_data


@pytest.fixture
def server(monkeypatch):
    """
    Serve the responses of a fake website to requests.

    Returns
    -------
    dict[str, bytes]
        The content of the responses, by URL, which the test can change.
    """
    contents: dict[str, bytes] = {}

    def send(_adapter, request, **_kwargs):
        response = requests.Response()
        response.status_code = 200
        response._content = contents[request.url]
        response.headers["Content-Type"] = "text/csv"
        response.url = request.url
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return contents


@pytest.mark.parametrize(
    "request_",
    [
        None,
        2024,
        "FILE_123",
        (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"), "FILE_1"),
        (2025, None),
        [datetime.date(2024, 1, 1), 1.5],
    ],
)
def test_encode_and_decode_request(request_):
    """Test that a request is the same after its encoding as JSON."""
    encoded = utils.raw_data.encode_request(request_)

    assert utils.raw_data.decode_request(encoded) == request_


def test_encode_unknown_request():
    """Test that a request of another type is rejected."""
    with pytest.raises(TypeError, match="Cannot save a request"):
        utils.raw_data.encode_request({1, 2})


def test_record_and_replay(server, monkeypatch):
    """Test that the responses are kept without secrets and replayed."""
    monkeypatch.setenv("TEST_API_KEY", "key123")
    monkeypatch.setenv("TEST_PASSWORD", "pass word&1")
    server["https://example.org/data?api_key=key123"] = b"time,value\n"
    server["https://example.org/ticket"] = b"secret-ticket"

    with utils.raw_data.recording("test") as responses:
        data = requests.get(
            "https://example.org/data",
            params={"api_key": "key123"},
            timeout=10,
        )
        ticket = requests.post(
            "https://example.org/ticket",
            data={"password": "pass word&1"},
            timeout=10,
        )
    assert data.content == b"time,value\n"
    assert ticket.text == "secret-ticket"

    # The API key is hidden, and the response to the request that sends
    # the password is not saved.
    assert responses[0]["key"][1] == "https://example.org/data?api_key=***"
    assert responses[0]["file"] is not None
    assert responses[1]["file"] is None
    assert "key123" not in str(responses)

    # The saved responses are replayed without the network, and the
    # request that sends the password gets an empty response.
    server.clear()
    with utils.raw_data.replaying("test", responses):
        data = requests.get(
            "https://example.org/data",
            params={"api_key": "key123"},
            timeout=10,
        )
        ticket = requests.post(
            "https://example.org/ticket",
            data={"password": "pass word&1"},
            timeout=10,
        )
        with pytest.raises(utils.raw_data.RawDataNotFoundError):
            requests.get("https://example.org/other", timeout=10)
    assert data.content == b"time,value\n"
    assert data.headers["Content-Type"] == "text/csv"
    assert ticket.text == ""


def test_record_and_replay_urllib(tmp_path):
    """Test that the responses of urllib are saved and replayed."""
    file_path = tmp_path / "data.csv"
    file_path.write_bytes(b"time,value\n")
    url = file_path.as_uri()

    with (
        utils.raw_data.recording("test") as responses,
        urllib.request.urlopen(url) as response,  # noqa: S310
    ):
        assert response.read() == b"time,value\n"
    os.remove(file_path)

    with (
        utils.raw_data.replaying("test", responses),
        urllib.request.urlopen(url) as response,  # noqa: S310
    ):
        assert response.read() == b"time,value\n"


def test_record_and_replay_manual_files():
    """Test that the files downloaded manually are kept and replayed."""
    folder = pathlib.Path(
        utils.paths.get_electricity_demand_folder("manual_downloads")
    )
    folder.mkdir(parents=True)
    (folder / "ABC_1.csv").write_text("load\n1\n")

    def read():
        return utils.fetcher.read_manual_files(
            data_source_name="ABC",
            url="https://example.org",
            prefix="ABC",
            read_file=pd.read_csv,
        )["load"].tolist()

    with utils.raw_data.recording("test") as responses:
        assert read() == [1]
        # A file found again is recorded once.
        assert read() == [1]
    assert [response["key"] for response in responses] == [
        ["FILE", "ABC_1.csv", None]
    ]

    # The saved file is replayed, also after the file changes or is
    # removed, and only with its prefix.
    (folder / "ABC_1.csv").unlink()
    with utils.raw_data.replaying("test", responses):
        assert read() == [1]
        assert read() == [1]
        with pytest.raises(utils.raw_data.RawDataNotFoundError):
            utils.fetcher.find_manual_files("XYZ")
    assert utils.fetcher.find_manual_files("ABC") == []


def test_save_versions(server):
    """Test that a version is added only when the responses change."""
    server["https://example.org/data"] = b"1"
    request = (pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"))

    def retrieve(retrieved):
        with utils.raw_data.recording("test") as responses:
            requests.get("https://example.org/data", timeout=10)
        utils.raw_data.save_versions(
            "test", "FRA", [(request, responses, None)], retrieved
        )

    retrieve("2026-01-01T00:00:00Z")
    retrieve("2026-01-02T00:00:00Z")
    server["https://example.org/data"] = b"2"
    retrieve("2026-01-03T00:00:00Z")

    (entry,) = utils.raw_data.read_manifest("test")["requests"]
    assert entry["code"] == "FRA"
    assert utils.raw_data.decode_request(entry["request"]) == request
    assert [
        (version["first_retrieved"], version["last_retrieved"])
        for version in entry["versions"]
    ] == [
        ("2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"),
        ("2026-01-03T00:00:00Z", "2026-01-03T00:00:00Z"),
    ]

"""
License: AGPL-3.0.

Description:

    Tests for the upload of files to Google Cloud Storage, with the
    client mocked, and to Zenodo, with a fake Zenodo server that
    records the sequence of the requests.
"""

import json
import logging
import re
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests
import utils.paths
import utils.uploader
from google.cloud.exceptions import GoogleCloudError

# The address of the depositions of the sandbox of Zenodo.
SANDBOX = "https://sandbox.zenodo.org/api/deposit/depositions"

# The title of the dataset of actual data.
ACTUAL_TITLE = (
    "Global Dataset of Hourly or Sub-Hourly Historical Electricity Demand"
)


def test_upload_to_gcs():
    """
    Test the upload_to_gcs function by mocking GCS interactions.

    This test checks if the function correctly uploads a file to a
    Google Cloud Storage (GCS) bucket. It uses mocking to simulate the
    GCS interactions, ensuring that the function behaves as expected
    without requiring actual GCS access. It also tests the error
    handling for OSError and GoogleCloudError.
    """
    # Define a mock for the GCS bucket and blob.
    mock_bucket = Mock()
    mock_blob = Mock()

    with patch("google.cloud.storage.Client") as mock_storage_client:
        # Mock the bucket and blob.
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Call the function.
        utils.uploader.upload_to_gcs(
            "dummy/path.txt", "test-bucket", "dest/path.txt"
        )

        # Assert the file was uploaded.
        mock_blob.upload_from_filename.assert_called_once_with(
            "dummy/path.txt"
        )

        # Check if the OSError is handled correctly.
        mock_blob.upload_from_filename.side_effect = OSError("file not found")
        with pytest.raises(OSError, match="file not found"):
            utils.uploader.upload_to_gcs(
                "bad/path.txt", "test-bucket", "dest/path.txt"
            )

        # Check if the GoogleCloudError is handled correctly.
        mock_blob.upload_from_filename.side_effect = GoogleCloudError(
            "GCS failure"
        )
        with pytest.raises(GoogleCloudError):
            utils.uploader.upload_to_gcs(
                "bad/path.txt", "test-bucket", "dest/path.txt"
            )


class FakeZenodo:
    """
    A fake Zenodo server, which records the requests that it gets.

    Attributes
    ----------
    depositions : list[dict]
        The depositions that the server has.
    failing : str | None
        The request, "<method> <path>" with the path from the address of
        the depositions, that fails with a server error.
    requests : list[tuple[str, str, dict]]
        The method, path and keyword arguments of each request.
    """

    # The status of the answer to each request, by method and path,
    # with numbers for the identifiers.
    ROUTES = (
        ("GET", r"", 200),
        ("POST", r"", 201),
        ("PUT", r"/\d+", 200),
        ("POST", r"/\d+/actions/newversion", 201),
        ("GET", r"/\d+/files", 200),
        ("DELETE", r"/\d+/files/\w+", 204),
        ("POST", r"/\d+/files", 201),
        ("POST", r"/\d+/actions/publish", 202),
    )

    def __init__(self, depositions: list[dict], failing: str | None = None):
        self.depositions = depositions
        self.failing = failing
        self.requests: list[tuple[str, str, dict]] = []

    def handle(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Answer a request.

        Parameters
        ----------
        method : str
            The method of the request.
        url : str
            The URL of the request.
        **kwargs
            The keyword arguments of the request.

        Returns
        -------
        requests.Response
            The answer.
        """
        base = url.split("/api/deposit/depositions", maxsplit=1)[0]
        path = url.removeprefix(base + "/api/deposit/depositions")
        self.requests.append((method, path, kwargs))
        response = requests.Response()
        status = next(
            status
            for route_method, route, status in self.ROUTES
            if route_method == method and re.fullmatch(route, path)
        )
        if self.failing == f"{method} {path}":
            response.status_code = 500
            response._content = b"server error"
            return response
        response.status_code = status
        if method == "GET" and path == "":
            content: object = self.depositions
        elif method == "GET":
            content = [{"id": "f1", "filename": "old.parquet"}]
        elif path.endswith("newversion"):
            content = {"id": 101}
        else:
            content = {"id": 7}
        response._content = json.dumps(content).encode()
        return response


def _sender(server: FakeZenodo, method: str):
    """
    Get the function that sends the requests of a method to the server.

    Parameters
    ----------
    server : FakeZenodo
        The fake server.
    method : str
        The method, in lower case, as the name of its requests function.

    Returns
    -------
    Callable
        The function, with the arguments of the requests function.
    """
    return lambda url, **kwargs: server.handle(method.upper(), url, **kwargs)


@pytest.fixture
def zenodo(monkeypatch, tmp_path):
    """
    Serve the requests to Zenodo with a fake server.

    The API keys are in the environment, and the file to upload in a
    temporary folder.

    Returns
    -------
    Callable
        The function that sets up the server with its depositions and
        the failing request, and returns it.
    """
    monkeypatch.setattr(utils.paths, "ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setenv("SANDBOX_ZENODO_API_KEY", "sandbox-token")
    monkeypatch.setenv("ZENODO_API_KEY", "production-token")
    (tmp_path / "FRA_rte.parquet").write_bytes(b"data")

    def set_up(depositions=(), failing=None):
        server = FakeZenodo(list(depositions), failing)
        for method in ("get", "post", "put", "delete"):
            monkeypatch.setattr(requests, method, _sender(server, method))
        return server

    return set_up


def _upload(tmp_path, **kwargs) -> None:
    """
    Upload the test file to Zenodo.

    Parameters
    ----------
    tmp_path : pathlib.Path
        The folder of the file.
    **kwargs
        The options of utils.uploader.upload_to_zenodo.
    """
    options: dict[str, Any] = {
        "data_type": "actual",
        "made_by_oet": True,
        "publish": True,
    }
    options.update(kwargs)
    utils.uploader.upload_to_zenodo(
        str(tmp_path / "FRA_rte.parquet"), **options
    )


@pytest.mark.usefixtures("frozen_now")
def test_upload_to_a_new_deposition(zenodo, tmp_path):
    """
    Test the requests and the metadata of a new deposition.

    The deposition is created with the metadata of the actual data, the
    file uploaded with its name, and the deposition published.
    """
    server = zenodo(
        [{"id": 3, "submitted": True, "metadata": {"title": "Other"}}]
    )

    _upload(tmp_path)

    assert [(method, path) for method, path, _ in server.requests] == [
        ("GET", ""),
        ("POST", ""),
        ("POST", "/7/files"),
        ("POST", "/7/actions/publish"),
    ]
    for _, _, kwargs in server.requests:
        assert kwargs["params"] == {"access_token": "sandbox-token"}
    metadata = json.loads(server.requests[1][2]["data"])["metadata"]
    assert metadata["title"] == ACTUAL_TITLE
    assert metadata["license"] == "cc-by-nc-4.0"
    assert metadata["publication_date"] == "2026-01-02"
    assert metadata["creators"][0]["name"] == "Antonini, Enrico G. A."
    assert metadata["contributors"][0]["type"] == "HostingInstitution"
    assert server.requests[2][2]["data"] == {"name": "FRA_rte.parquet"}
    assert server.requests[2][2]["timeout"] == 600


def test_upload_to_a_draft(zenodo, tmp_path, caplog):
    """Test that a draft with the title gets the file, unpublished."""
    server = zenodo(
        [{"id": 5, "submitted": False, "metadata": {"title": ACTUAL_TITLE}}]
    )

    with caplog.at_level(logging.INFO):
        _upload(tmp_path, publish=False)

    assert [(method, path) for method, path, _ in server.requests] == [
        ("GET", ""),
        ("PUT", "/5"),
        ("POST", "/5/files"),
    ]
    assert "not published" in caplog.text


def test_upload_to_a_new_version(zenodo, tmp_path):
    """
    Test that a published deposition gets a new version.

    The files inherited from the previous version are deleted before
    the new file is uploaded.
    """
    server = zenodo(
        [{"id": 5, "submitted": True, "metadata": {"title": ACTUAL_TITLE}}]
    )

    _upload(tmp_path)

    assert [(method, path) for method, path, _ in server.requests] == [
        ("GET", ""),
        ("POST", "/5/actions/newversion"),
        ("PUT", "/101"),
        ("GET", "/101/files"),
        ("DELETE", "/101/files/f1"),
        ("POST", "/101/files"),
        ("POST", "/101/actions/publish"),
    ]


def test_upload_to_production(zenodo, tmp_path, monkeypatch):
    """Test the address and the key of Zenodo outside the sandbox."""
    server = zenodo()
    urls = []
    handle = server.handle

    def record_url(method, url, **kwargs):
        urls.append(url)
        return handle(method, url, **kwargs)

    monkeypatch.setattr(server, "handle", record_url)

    _upload(tmp_path, testing=False, data_type="synthetic")

    assert urls[0] == "https://zenodo.org/api/deposit/depositions"
    assert server.requests[0][2]["params"] == {
        "access_token": "production-token"
    }
    metadata = json.loads(server.requests[1][2]["data"])["metadata"]
    assert metadata["title"] == (
        "Global Dataset of Hourly Synthetic Electricity Demand"
    )
    assert metadata["license"] == "CC-BY-4.0"


def test_upload_by_external_contributors(zenodo, tmp_path, monkeypatch):
    """Test that the metadata of others is read from their file."""
    server = zenodo()
    (tmp_path / "zenodo_metadata.yaml").write_text(
        "creators:\n  - name: Doe, Jane\ncontributors: []\n"
    )
    monkeypatch.setattr(utils.paths, "CONFIG_FOLDER", str(tmp_path))

    _upload(tmp_path, made_by_oet=False)

    metadata = json.loads(server.requests[1][2]["data"])["metadata"]
    assert metadata["creators"] == [{"name": "Doe, Jane"}]


def test_upload_of_unknown_data(zenodo, tmp_path):
    """Test that the type of the data must be known."""
    server = zenodo()

    with pytest.raises(ValueError, match="Invalid data_type"):
        _upload(tmp_path, data_type="forecast")

    assert server.requests == []


@pytest.mark.parametrize(
    ("depositions", "failing", "message"),
    [
        ([], "GET ", "deposition retrieval failed"),
        ([], "POST ", "deposition creation failed"),
        ([], "POST /7/files", "upload of the file .*FRA_rte.parquet failed"),
        ([], "POST /7/actions/publish", "publication failed"),
        ("draft", "PUT /5", "metadata update failed"),
        ("published", "POST /5/actions/newversion", "new version creation"),
        ("published", "PUT /101", "metadata update failed"),
        ("published", "GET /101/files", "file retrieval failed"),
        ("published", "DELETE /101/files/f1", "file old.parquet failed"),
    ],
)
def test_zenodo_errors(zenodo, tmp_path, depositions, failing, message):
    """Test that a failing request stops with the answer of Zenodo."""
    if depositions:
        depositions = [
            {
                "id": 5,
                "submitted": depositions == "published",
                "metadata": {"title": ACTUAL_TITLE},
            }
        ]
    server = zenodo(depositions, failing)

    with pytest.raises(utils.uploader.ZenodoError, match=message) as error:
        _upload(tmp_path)

    assert "server error" in str(error.value)
    assert f"{server.requests[-1][0]} {server.requests[-1][1]}" == failing

"""
License: AGPL-3.0.

Description:

    Tests of the publication of a release on Zenodo, with a fake API
    that records the requests and answers as Zenodo does.
"""

import json
import os
from unittest.mock import patch

import pytest

from publishing import zenodo

API = "https://zenodo.org/api/deposit/depositions"
DRAFT = f"{API}/200"
BUCKET = "https://zenodo.org/api/files/bucket-200"


class _FakeResponse:
    """A response with a status and a JSON content."""

    def __init__(self, status_code: int, content: dict | None = None) -> None:
        self.status_code = status_code
        self.content = content or {}
        self.text = json.dumps(self.content)

    def json(self) -> dict:
        """
        Get the content.

        Returns
        -------
        dict
            The content.
        """
        return self.content


class _FakeZenodo:
    """The API of Zenodo for a record whose version 100 is published."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.metadata: dict = {}
        self.uploaded: dict[str, bytes] = {}

    def __call__(self, method, url, headers, **kwargs):
        """
        Answer a request.

        Returns
        -------
        _FakeResponse
            The response of Zenodo.
        """
        # The key is in the header, never in the address.
        assert headers["Authorization"] == "Bearer test-key"
        assert "params" not in kwargs
        self.requests.append((method, url.removeprefix(API)))
        draft = {
            "id": 200,
            "links": {
                "bucket": BUCKET,
                "html": "https://zenodo.org/deposit/200",
            },
            "metadata": {
                "title": "Forecasts",
                "version": "1.0.0",
                "doi": "10.5281/zenodo.100",
                "prereserve_doi": {"doi": "10.5281/zenodo.200"},
            },
            "files": [{"id": "f1", "filename": "old_model.json"}],
        }
        if (method, url) == ("POST", f"{API}/100/actions/newversion"):
            return _FakeResponse(201, {"links": {"latest_draft": DRAFT}})
        if (method, url) == ("GET", DRAFT):
            return _FakeResponse(200, draft)
        if (method, url) == ("DELETE", f"{DRAFT}/files/f1"):
            return _FakeResponse(204)
        if method in ("PUT", "POST") and url in (DRAFT, API):
            self.metadata = json.loads(kwargs["data"])["metadata"]
            return _FakeResponse(200 if method == "PUT" else 201, draft)
        if method == "PUT" and url.startswith(BUCKET):
            self.uploaded[url.removeprefix(BUCKET + "/")] = kwargs[
                "data"
            ].read()
            return _FakeResponse(201)
        return _FakeResponse(400, {"message": "unexpected request"})


@pytest.fixture
def fake_zenodo(monkeypatch):
    """
    Answer the requests to Zenodo with the fake API.

    Yields
    ------
    _FakeZenodo
        The fake API, with the requests it received.
    """
    monkeypatch.setenv("ZENODO_API_KEY", "test-key")
    fake = _FakeZenodo()
    with patch.object(zenodo.requests, "request", side_effect=fake):
        yield fake


@pytest.fixture
def release_files(tmp_path):
    """
    Make the files of a release.

    Returns
    -------
    list[str]
        The paths of the model and of the forecasts.
    """
    (tmp_path / "model.json").write_bytes(b"model")
    (tmp_path / "forecasts.parquet").write_bytes(b"forecasts")
    return [str(tmp_path / "model.json"), str(tmp_path / "forecasts.parquet")]


def test_publish_a_new_version(fake_zenodo, release_files):
    """Test that the release is a draft version with its files only."""
    draft_url = zenodo.publish_release(release_files, "1.1.0", 100)

    assert draft_url == "https://zenodo.org/deposit/200"
    assert fake_zenodo.requests == [
        ("POST", "/100/actions/newversion"),
        ("GET", "/200"),
        ("DELETE", "/200/files/f1"),
        ("PUT", "/200"),
        ("PUT", f"{BUCKET}/model.json"),
        ("PUT", f"{BUCKET}/forecasts.parquet"),
    ]
    # The metadata of the record is kept, with the new version, and the
    # draft is not published.
    assert fake_zenodo.metadata["title"] == "Forecasts"
    assert fake_zenodo.metadata["version"] == "1.1.0"
    assert "doi" not in fake_zenodo.metadata
    assert fake_zenodo.uploaded == {
        "model.json": b"model",
        "forecasts.parquet": b"forecasts",
    }
    assert not any("publish" in url for _, url in fake_zenodo.requests)


def test_publish_a_new_record(fake_zenodo, release_files):
    """Test that a new record has the metadata of the forecasts."""
    zenodo.publish_release(release_files, "1.0.0", None)

    assert fake_zenodo.requests[0] == ("POST", "")
    assert fake_zenodo.metadata["title"] == zenodo.TITLE
    assert fake_zenodo.metadata["license"] == "cc-by-4.0"
    assert fake_zenodo.metadata["creators"][0]["affiliation"] == (
        "Open Energy Transition"
    )
    assert set(fake_zenodo.uploaded) == {"model.json", "forecasts.parquet"}


def test_publish_with_wrong_files(fake_zenodo, tmp_path, release_files):
    """Test that missing files and repeated names stop the release."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        zenodo.publish_release([str(tmp_path / "missing.json")], "1.1.0", 100)

    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "model.json").write_bytes(b"other")
    with pytest.raises(ValueError, match="same names"):
        zenodo.publish_release(
            [*release_files, str(tmp_path / "other" / "model.json")],
            "1.1.0",
            100,
        )

    assert fake_zenodo.requests == []


@pytest.mark.usefixtures("fake_zenodo")
def test_failed_request(release_files):
    """Test that an error of Zenodo stops the release."""
    with pytest.raises(zenodo.ZenodoError, match="unexpected request"):
        zenodo.publish_release(release_files, "1.1.0", 999)


def test_failed_connection_hides_the_request(monkeypatch):
    """Test that a failed connection does not show the request."""
    monkeypatch.setenv("ZENODO_API_KEY", "test-key")
    error = zenodo.requests.ConnectionError(
        f"Failed to connect to {API}?access_token=test-key"
    )

    with (
        patch.object(zenodo.requests, "request", side_effect=error),
        pytest.raises(zenodo.ZenodoError) as raised,
    ):
        zenodo.ZenodoApi(sandbox=False).request("GET", "/1", 200, "check")

    assert "test-key" not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__


def test_key_is_sent_only_to_zenodo(monkeypatch):
    """Test that a full address outside Zenodo is refused."""
    monkeypatch.setenv("ZENODO_API_KEY", "test-key")

    with (
        patch.object(zenodo.requests, "request") as request,
        pytest.raises(zenodo.ZenodoError, match="not that of Zenodo"),
    ):
        zenodo.ZenodoApi(sandbox=False).request(
            "PUT", "https://example.org/files/a", 201, "upload"
        )

    request.assert_not_called()


def test_sandbox_needs_its_key(monkeypatch):
    """Test that the sandbox uses its own key and address."""
    monkeypatch.setenv("SANDBOX_ZENODO_API_KEY", "sandbox-key")
    monkeypatch.delenv("ZENODO_API_KEY", raising=False)

    api = zenodo.ZenodoApi(sandbox=True)

    assert api.url.startswith("https://sandbox.zenodo.org/")
    assert api.access_token == os.environ["SANDBOX_ZENODO_API_KEY"]

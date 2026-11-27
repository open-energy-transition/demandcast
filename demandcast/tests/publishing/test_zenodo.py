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
import yaml

from publishing import zenodo

API = "https://zenodo.org/api/deposit/depositions"
DRAFT = f"{API}/200"
BUCKET = "https://zenodo.org/api/files/bucket-200"


class _FakeResponse:
    """A response with a status and a JSON content."""

    def __init__(self, status_code: int, content: dict | None = None) -> None:
        """Set up the response, with its content as text."""
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
        """Set up the record without requests or uploads."""
        self.requests: list[tuple[str, str]] = []
        self.metadata: dict = {}
        self.uploaded: dict[str, bytes] = {}
        self.failing_uploads = False
        self.dates: list[dict[str, str]] = [
            {"type": "available"},
            {"type": "collected", "start": "2026-01-01"},
        ]

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
                "creators": [{"name": "Antonini, Enrico"}],
                "dates": self.dates,
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
            if self.failing_uploads:
                return _FakeResponse(500, {"message": "upload failed"})
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


def _write_release_metadata(folder, version, file_names):
    """
    Write the metadata of a release.

    Returns
    -------
    pathlib.Path
        The file of the metadata.
    """
    tag = (
        "https://github.com/open-energy-transition/demandcast/releases/"
        f"tag/v{version}"
    )
    files = "".join(f"<li><em>{name}</em></li>" for name in file_names)
    metadata_file = folder / "metadata.yaml"
    metadata_file.write_text(
        yaml.safe_dump(
            {
                "title": "Forecasts",
                "keywords": ["Electricity demand"],
                "related_identifiers": [
                    {"relation": "isCompiledBy", "identifier": tag}
                ],
                "description": (
                    f'<p>Made with <a href="{tag}">DemandCast {version}'
                    f"</a>.</p><ul>{files}</ul><p>Each file has a "
                    "manifest, <em>.manifest.json</em>.</p>"
                ),
            }
        )
    )
    return metadata_file


@pytest.fixture
def release_files(tmp_path, monkeypatch):
    """
    Make the files of a release, and its metadata.

    The metadata names version 1.1.0 and the two files.

    Returns
    -------
    list[str]
        The paths of the model and of the forecasts.
    """
    (tmp_path / "model.json").write_bytes(b"model")
    (tmp_path / "forecasts.parquet").write_bytes(b"forecasts")
    monkeypatch.setattr(
        zenodo,
        "RELEASE_METADATA_FILE",
        str(
            _write_release_metadata(
                tmp_path, "1.1.0", ["model.json", "forecasts.parquet"]
            )
        ),
    )
    return [str(tmp_path / "model.json"), str(tmp_path / "forecasts.parquet")]


def test_publish_a_new_version(fake_zenodo, release_files):
    """
    Test that the release is a draft version with its files only.

    The new version has the title and description of the release, keeps
    the creators of the record, and leaves out the date without a start
    or an end, which Zenodo rejects. The draft is not published.
    """
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
    release_metadata = zenodo.read_release_metadata()
    for key, value in release_metadata.items():
        assert fake_zenodo.metadata[key] == value
    assert fake_zenodo.metadata["creators"] == [{"name": "Antonini, Enrico"}]
    assert fake_zenodo.metadata["dates"] == [
        {"type": "collected", "start": "2026-01-01"}
    ]
    assert fake_zenodo.metadata["version"] == "1.1.0"
    assert "doi" not in fake_zenodo.metadata
    assert fake_zenodo.uploaded == {
        "model.json": b"model",
        "forecasts.parquet": b"forecasts",
    }
    assert not any("publish" in url for _, url in fake_zenodo.requests)


def test_new_version_without_dates(fake_zenodo, release_files):
    """Test that a record whose only date has no value gets no dates."""
    fake_zenodo.dates = [{"type": "available"}]

    zenodo.publish_release(release_files, "1.1.0", 100)

    assert "dates" not in fake_zenodo.metadata
    assert fake_zenodo.metadata["version"] == "1.1.0"


def test_publish_a_new_record(fake_zenodo, release_files):
    """Test that a new record has the metadata of the forecasts."""
    zenodo.publish_release(release_files, "1.1.0", None)

    assert fake_zenodo.requests[0] == ("POST", "")
    assert (
        fake_zenodo.metadata["title"]
        == (zenodo.read_release_metadata()["title"])
    )
    assert fake_zenodo.metadata["license"] == "cc-by-4.0"
    assert fake_zenodo.metadata["creators"][0]["affiliation"] == (
        "Open Energy Transition"
    )
    assert set(fake_zenodo.uploaded) == {"model.json", "forecasts.parquet"}


def test_release_metadata(tmp_path):
    """Test that the metadata of the release has its four keys only."""
    metadata = zenodo.read_release_metadata()
    assert metadata["title"].startswith("Global Dataset of Forecasted")
    assert "forecasts_on_historical_period.parquet" in metadata["description"]

    metadata_file = tmp_path / "metadata.yaml"
    metadata_file.write_text("title: Forecasts\nversion: 2.0.0\n")
    with pytest.raises(ValueError, match="must have title"):
        zenodo.read_release_metadata(str(metadata_file))


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


@pytest.mark.parametrize(
    ("version", "files", "messages"),
    [
        (
            "1.2.0",
            ["model.json", "forecasts.parquet"],
            [
                "does not name the version 1.2.0",
                "names other versions: 1.1.0",
            ],
        ),
        (
            "1.1.0",
            ["model.json"],
            ["names files that are not uploaded: forecasts.parquet"],
        ),
    ],
)
def test_publish_with_wrong_metadata(
    fake_zenodo, release_files, version, files, messages
):
    """
    Test that metadata of another release stops it before any request.

    The metadata names version 1.1.0, the model and the forecasts.
    """
    file_paths = [
        path for path in release_files if os.path.basename(path) in files
    ]

    with pytest.raises(ValueError, match="does not match it") as error:
        zenodo.publish_release(file_paths, version, 100)

    for message in messages:
        assert message in str(error.value)
    assert fake_zenodo.requests == []


def test_names_in_the_metadata(tmp_path):
    """
    Test that only the names of the files and versions are checked.

    The links to other files, the extension of the manifests alone and
    other mentions of versions are not names of the release.
    """
    metadata = zenodo.read_release_metadata(
        str(_write_release_metadata(tmp_path, "2.0.0", ["model.json"]))
    )
    metadata["description"] += (
        "<p>Changes from version 1.0.0, the version of "
        '<a href="https://example.org/data/old_model.json">the paper</a> '
        "on https://open-energy-transition.github.io/demandcast/ and "
        "https://github.com/x/y/blob/main/README.md.</p>"
    )

    zenodo.check_release_metadata(metadata, "v2.0.0", ["model.json"])
    with pytest.raises(ValueError, match=r"not uploaded: model\.json"):
        zenodo.check_release_metadata(metadata, "2.0.0", ["model.zip"])


def test_metadata_of_the_current_release():
    """
    Test that the metadata of the current release names one version.

    Its files are the forecasts, their inputs, the model, the archives
    of the validations and the README, without the manifests.
    """
    metadata = zenodo.read_release_metadata()
    texts = [
        metadata["title"],
        metadata["description"],
        *(link["identifier"] for link in metadata["related_identifiers"]),
    ]
    versions = {
        version
        for pattern in zenodo.VERSION_PATTERNS
        for text in texts
        for version in pattern.findall(text)
    }
    names = {
        name
        for text in texts
        for name in zenodo.FILE_NAME_PATTERN.findall(text)
    }

    assert len(versions) == 1
    assert {
        "forecasts_on_historical_period.parquet",
        "validation.zip",
        "cross_validation.zip",
        "README.md",
    } <= names
    assert not any("manifest" in name for name in names)
    zenodo.check_release_metadata(metadata, versions.pop(), sorted(names))


def test_draft_is_logged_before_the_uploads(
    fake_zenodo, release_files, caplog
):
    """Test that the address of the draft is logged before an upload."""
    fake_zenodo.failing_uploads = True

    with (
        caplog.at_level("INFO"),
        pytest.raises(zenodo.ZenodoError, match="upload failed"),
    ):
        zenodo.publish_release(release_files, "1.1.0", 100)

    assert "The draft 200 of the release 1.1.0 is at " in caplog.text
    assert "https://zenodo.org/deposit/200" in caplog.text


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


def test_missing_sandbox_key(monkeypatch):
    """Test that a missing key of the sandbox is named in the error."""
    monkeypatch.setenv("SANDBOX_ZENODO_API_KEY", "")

    with pytest.raises(
        ValueError, match=r"^The Zenodo sandbox API key is not set\."
    ):
        zenodo.ZenodoApi(sandbox=True)

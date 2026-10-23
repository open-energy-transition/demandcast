"""
License: AGPL-3.0.

Description:

    Tests of the copy of the data folder to and from a bucket of Google
    Cloud Storage, with a fake bucket that, like Cloud Storage, writes
    an object only if it does not exist when asked so.
"""

import base64

import google_crc32c
import pytest
from google.api_core.exceptions import PreconditionFailed
from publishing import gcs


class _FakeBlob:
    """An object of the fake bucket."""

    def __init__(self, bucket: "_FakeBucket", name: str) -> None:
        self.bucket = bucket
        self.name = name

    @property
    def size(self) -> int:
        """The size of the content."""
        return len(self.bucket.objects[self.name])

    @property
    def crc32c(self) -> str:
        """The checksum of the content, in base 64."""
        return _checksum(self.bucket.objects[self.name])

    def upload_from_filename(self, file_path, if_generation_match=None):
        """
        Write the object, unless it exists and that is forbidden.

        Raises
        ------
        PreconditionFailed
            If the object exists and if_generation_match is 0.
        """
        if if_generation_match == 0 and self.name in self.bucket.objects:
            raise PreconditionFailed("The object exists.")
        with open(file_path, "rb") as file:
            self.bucket.objects[self.name] = file.read()

    def download_to_file(self, file):
        """Write the content to an open file."""
        file.write(self.bucket.objects[self.name])


class _FakeBucket:
    """A bucket with its objects in a dictionary."""

    def __init__(
        self, objects: dict[str, bytes], hidden: frozenset[str] = frozenset()
    ) -> None:
        self.objects = dict(objects)
        # The objects written by another copy after the listing.
        self.hidden = hidden

    def blob(self, name: str) -> _FakeBlob:
        """
        Get an object, which may not exist.

        Returns
        -------
        _FakeBlob
            The object.
        """
        return _FakeBlob(self, name)

    def list_blobs(self) -> list[_FakeBlob]:
        """
        List the objects, but the hidden ones.

        Returns
        -------
        list[_FakeBlob]
            The objects.
        """
        return [
            _FakeBlob(self, name)
            for name in sorted(self.objects)
            if name not in self.hidden
        ]


class _FakeClient:
    """A client with a single bucket."""

    def __init__(self, bucket: _FakeBucket) -> None:
        self._bucket = bucket

    def bucket(self, _name: str) -> _FakeBucket:
        """
        Get the bucket.

        Returns
        -------
        _FakeBucket
            The bucket.
        """
        return self._bucket


def _checksum(content: bytes) -> str:
    """
    Get the CRC32C checksum of a content, in base 64.

    Returns
    -------
    str
        The checksum.
    """
    return base64.b64encode(google_crc32c.Checksum(content).digest()).decode()


@pytest.fixture
def data_folder(tmp_path):
    """
    Make a data folder with a file in a stage, a log and a manual file.

    Returns
    -------
    pathlib.Path
        The data folder.
    """
    folder = tmp_path / "data"
    (folder / "electricity_demand" / "cleaned").mkdir(parents=True)
    (
        folder / "electricity_demand" / "cleaned" / "FRA_entsoe.parquet"
    ).write_bytes(b"cleaned")
    (
        folder / "electricity_demand" / "cleaned" / "DEU_entsoe.parquet"
    ).write_bytes(b"local version")
    (folder / "logs").mkdir()
    (folder / "logs" / "retrieval.log").write_bytes(b"log")
    (folder / "same.csv").write_bytes(b"same")
    return folder


def test_get_checksum(tmp_path):
    """Test that the checksum is that of Cloud Storage."""
    file_path = tmp_path / "file.csv"
    file_path.write_bytes(b"x" * 3_000_000)

    assert gcs.get_checksum(str(file_path)) == _checksum(b"x" * 3_000_000)


def test_upload(data_folder):
    """Test that only the missing files are uploaded."""
    bucket = _FakeBucket(
        {
            "same.csv": b"same",
            "electricity_demand/cleaned/DEU_entsoe.parquet": b"cloud version",
            "only_in_the_bucket.csv": b"kept",
        }
    )

    report = gcs.sync(
        "bucket", "upload", str(data_folder), client=_FakeClient(bucket)
    )

    assert report.copied == ["electricity_demand/cleaned/FRA_entsoe.parquet"]
    assert report.identical == ["same.csv"]
    assert report.different == [
        "electricity_demand/cleaned/DEU_entsoe.parquet"
    ]
    # Nothing is overwritten or deleted, and the logs stay local.
    assert bucket.objects == {
        "same.csv": b"same",
        "electricity_demand/cleaned/DEU_entsoe.parquet": b"cloud version",
        "electricity_demand/cleaned/FRA_entsoe.parquet": b"cleaned",
        "only_in_the_bucket.csv": b"kept",
    }


def test_download(data_folder):
    """Test that only the missing files are downloaded."""
    bucket = _FakeBucket(
        {
            "electricity_demand/cleaned/DEU_entsoe.parquet": b"cloud version",
            "electricity_demand/raw/manual_downloads/ESK.csv": b"eskom",
            "gridded_weather/raw/": b"",
            "logs/old.log": b"old log",
        }
    )

    report = gcs.sync(
        "bucket", "download", str(data_folder), client=_FakeClient(bucket)
    )

    assert report.copied == ["electricity_demand/raw/manual_downloads/ESK.csv"]
    assert report.different == [
        "electricity_demand/cleaned/DEU_entsoe.parquet"
    ]
    assert (
        data_folder
        / "electricity_demand"
        / "raw"
        / "manual_downloads"
        / "ESK.csv"
    ).read_bytes() == b"eskom"
    assert (
        data_folder / "electricity_demand" / "cleaned" / "DEU_entsoe.parquet"
    ).read_bytes() == b"local version"
    assert not (data_folder / "logs" / "old.log").exists()
    assert not (data_folder / "gridded_weather").exists()


def test_dry_run(data_folder):
    """Test that a dry run lists the files to copy without copying."""
    bucket = _FakeBucket({})

    report = gcs.sync(
        "bucket",
        "upload",
        str(data_folder),
        dry_run=True,
        client=_FakeClient(bucket),
    )

    assert report.copied == [
        "electricity_demand/cleaned/DEU_entsoe.parquet",
        "electricity_demand/cleaned/FRA_entsoe.parquet",
        "same.csv",
    ]
    assert bucket.objects == {}


def test_files_written_in_the_meantime(tmp_path):
    """Test that a file written by another copy is not overwritten."""
    bucket = _FakeBucket({"a.csv": b"other copy"})
    file_path = tmp_path / "a.csv"
    file_path.write_bytes(b"this copy")

    assert not gcs._upload(bucket.blob("a.csv"), str(file_path))
    assert bucket.objects["a.csv"] == b"other copy"

    assert not gcs._download(bucket.blob("a.csv"), str(file_path))
    assert file_path.read_bytes() == b"this copy"


def test_failed_download_leaves_no_file(tmp_path):
    """Test that a download that fails removes its partial file."""
    bucket = _FakeBucket({})
    file_path = tmp_path / "folder" / "a.csv"

    with pytest.raises(KeyError):
        gcs._download(bucket.blob("a.csv"), str(file_path))

    assert not file_path.exists()


def test_report_of_different_files(data_folder, caplog):
    """Test that the files that differ are named in the log."""
    bucket = _FakeBucket(
        {"electricity_demand/cleaned/DEU_entsoe.parquet": b"cloud version"}
    )

    with caplog.at_level("WARNING"):
        gcs.sync(
            "bucket", "upload", str(data_folder), client=_FakeClient(bucket)
        )

    assert "1 files differ" in caplog.text
    assert "electricity_demand/cleaned/DEU_entsoe.parquet" in caplog.text


def test_sync_of_files_written_in_the_meantime(data_folder, monkeypatch):
    """Test that the files written during a copy are reported."""
    # The bucket lists no object, but another copy writes one.
    bucket = _FakeBucket(
        {"same.csv": b"other copy"}, hidden=frozenset({"same.csv"})
    )

    report = gcs.sync(
        "bucket", "upload", str(data_folder), client=_FakeClient(bucket)
    )

    assert "same.csv" in report.different
    assert bucket.objects["same.csv"] == b"other copy"

    # The data folder lists no file, but another copy writes one.
    bucket = _FakeBucket({"same.csv": b"cloud"})
    monkeypatch.setattr(gcs, "list_local_files", lambda *_args: {})

    report = gcs.sync(
        "bucket", "download", str(data_folder), client=_FakeClient(bucket)
    )

    assert report.different == ["same.csv"]
    assert (data_folder / "same.csv").read_bytes() == b"same"

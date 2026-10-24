"""
License: AGPL-3.0.

Description:

    Tests of the manifests of the files that the scripts produce.
"""

import json

import pytest

import utils.manifest


def test_write_and_read_manifest(tmp_path):
    """Test that a manifest tells the file, its checksum and version."""
    file_path = tmp_path / "data.parquet"
    file_path.write_bytes(b"content")

    manifest_path = utils.manifest.write_manifest(
        str(file_path), "dataset", {"purpose": "training"}
    )

    assert manifest_path == str(tmp_path / "data.manifest.json")
    manifest = utils.manifest.read_manifest(str(file_path))
    assert manifest is not None
    assert manifest["kind"] == "dataset"
    assert manifest["file"] == "data.parquet"
    assert manifest["purpose"] == "training"
    assert manifest["manifest_version"] == utils.manifest.MANIFEST_VERSION
    assert manifest["sha256"] == (
        "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"
    )
    assert set(manifest["code"]) == {"commit", "lockfile"}


def test_file_without_manifest(tmp_path):
    """Test that a file made before the manifests has none."""
    assert utils.manifest.read_manifest(str(tmp_path / "model.json")) is None


def test_manifest_of_a_newer_version(tmp_path):
    """Test that a manifest that this code cannot read is an error."""
    (tmp_path / "model.manifest.json").write_text(
        json.dumps({"manifest_version": utils.manifest.MANIFEST_VERSION + 1})
    )

    with pytest.raises(ValueError, match="newer than the version"):
        utils.manifest.read_manifest(str(tmp_path / "model.json"))


def test_code_version_without_git(monkeypatch):
    """Test that the code version is unknown without git."""

    def run(*_args, **_kwargs):
        raise OSError("git is not installed")

    monkeypatch.setattr(utils.manifest.subprocess, "run", run)

    assert utils.manifest.get_code_version()["commit"] is None


def test_code_version_when_git_fails(monkeypatch):
    """Test that the commit is unknown if git fails after it."""
    calls = []

    def run(command, **_kwargs):
        calls.append(command)
        if command[1] == "status":
            raise utils.manifest.subprocess.CalledProcessError(128, command)
        return utils.manifest.subprocess.CompletedProcess(
            command, 0, stdout="abc\n"
        )

    monkeypatch.setattr(utils.manifest.subprocess, "run", run)

    assert utils.manifest.get_code_version()["commit"] is None
    assert len(calls) == 2

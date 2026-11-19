"""
License: AGPL-3.0.

Description:

    Tests for the atomic writes of files, in utils/files.py.
"""

import os

import pytest

import utils.files


def test_writing_replaces_the_file_once_written(tmp_path):
    """Test that the file gets the content of the temporary one."""
    file_path = tmp_path / "data.csv"
    file_path.write_text("old")

    with utils.files.writing(str(file_path)) as temporary_path:
        assert temporary_path.endswith(".part")
        with open(temporary_path, "w", encoding="utf-8") as file:
            file.write("new")
        assert file_path.read_text() == "old"

    assert file_path.read_text() == "new"
    assert os.listdir(tmp_path) == ["data.csv"]


def _write_and_fail(file_path: str) -> None:
    """
    Write a file partly, and fail before its end.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Raises
    ------
    OSError
        Always, as when the disk is full.
    """
    with (
        utils.files.writing(file_path) as temporary_path,
        open(temporary_path, "w", encoding="utf-8") as file,
    ):
        file.write("partial")
        raise OSError("disk full")


def test_writing_that_fails_leaves_the_file(tmp_path):
    """
    Test that a write that fails changes nothing.

    The file keeps its content, and the temporary file is removed.
    """
    file_path = tmp_path / "data.csv"
    file_path.write_text("old")

    with pytest.raises(OSError, match="disk full"):
        _write_and_fail(str(file_path))

    assert file_path.read_text() == "old"
    assert os.listdir(tmp_path) == ["data.csv"]

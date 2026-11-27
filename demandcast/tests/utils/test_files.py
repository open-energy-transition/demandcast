"""
License: AGPL-3.0.

Description:

    Tests for the atomic writes, the reading of text files and the time
    in the names of files, in utils/files.py.
"""

import os

import pandas as pd
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


def test_read_with_unix_line_endings(tmp_path):
    """Test that the line endings of Windows are read as Unix ones."""
    file_path = tmp_path / "rules.py"
    file_path.write_bytes(b"A = 1\r\nB = 2\n")

    assert utils.files.read_with_unix_line_endings(str(file_path)) == (
        b"A = 1\nB = 2\n"
    )


def test_time_for_name_is_in_utc(monkeypatch):
    """
    Test that the time in the names of files is in UTC.

    The clock of the computer is in Tokyo, nine hours ahead of UTC.
    """
    utc_now = pd.Timestamp("2026-01-02 03:04:05", tz="UTC")

    def now(tz=None):
        """
        Give the frozen time, in the time zone of the computer.

        Returns
        -------
        pandas.Timestamp
            The time, in the time zone, or in that of the computer
            without one, as pandas gives it.
        """
        if tz is None:
            return utc_now.tz_convert("Asia/Tokyo").tz_localize(None)
        return utc_now.tz_convert(tz)

    monkeypatch.setattr(pd.Timestamp, "now", now)

    assert utils.files.get_time_for_name() == "20260102_030405"

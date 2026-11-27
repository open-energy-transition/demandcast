"""
License: AGPL-3.0.

Description:

    This module writes files atomically: a file is written under a
    temporary name next to its path, and renamed to it once complete,
    so that a write that stops, such as that of a killed retrieval,
    never leaves a partial file under its name. The steps that keep the
    files that exist, such as the grids and the downloads, would take a
    partial file as complete. It also reads text files with the line
    endings of Unix, for the checksums of the code of the rules of the
    cleaning and of the combination. It gives the time in the names of
    the files, by which the scripts find the latest file.
"""

import contextlib
import os
import uuid
from collections.abc import Iterator

import pandas as pd


@contextlib.contextmanager
def writing(file_path: str) -> Iterator[str]:
    """
    Write a file under a temporary name, and then give it its name.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Yields
    ------
    str
        The temporary path to write the file to, next to its path: the
        path, a random hexadecimal number and ".part", which
        publishing.gcs does not copy if it is left behind.

    Notes
    -----
    The temporary file replaces the file, if any, when the block ends
    without an error, and is removed when the block raises one.
    """
    temporary_path = f"{file_path}.{uuid.uuid4().hex}.part"
    try:
        yield temporary_path
        os.replace(temporary_path, file_path)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def read_with_unix_line_endings(file_path: str) -> bytes:
    """
    Read a text file with the line endings of Unix.

    Parameters
    ----------
    file_path : str
        The path of the file.

    Returns
    -------
    bytes
        The content of the file, with each CRLF replaced by LF.

    Notes
    -----
    Git can check the files out with CRLF on Windows, which must not
    change a checksum of the code made elsewhere, such as that of a
    file copied from a bucket.
    """
    with open(file_path, "rb") as file:
        return file.read().replace(b"\r\n", b"\n")


def get_time_for_name() -> str:
    """
    Get the current time in UTC, as it is written in names of files.

    Returns
    -------
    str
        The time, in the format YYYYMMDD_HHMMSS.

    Notes
    -----
    The scripts take the file with the latest time in its name for the
    latest, such as the latest model. In UTC, the times of the files of
    computers in different time zones, which share a data folder through
    a bucket, compare in the order in which the files were written.
    """
    return pd.Timestamp.now(tz="UTC").strftime("%Y%m%d_%H%M%S")

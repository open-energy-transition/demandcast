"""
License: AGPL-3.0.

Description:

    This module writes files atomically: a file is written under a
    temporary name next to its path, and renamed to it once complete,
    so that a write that stops, such as that of a killed retrieval,
    never leaves a partial file under its name. The steps that keep the
    files that exist, such as the grids and the downloads, would take a
    partial file as complete.
"""

import contextlib
import os
import uuid
from collections.abc import Iterator


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

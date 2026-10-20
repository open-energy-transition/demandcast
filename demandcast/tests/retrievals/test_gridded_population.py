"""
License: AGPL-3.0.

Description:

    Tests for the download of the future gridded population from
    Figshare, with a small archive in place of the real one.
"""

import io
import os
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from retrievals import gridded_population


def _archive(folder: str) -> bytes:
    """
    Make a zip archive with a single file in a folder.

    Parameters
    ----------
    folder : str
        The folder of the file in the archive.

    Returns
    -------
    bytes
        The content of the archive.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"{folder}/population.tif", b"data")
    return buffer.getvalue()


def _response(content: bytes) -> MagicMock:
    """
    Make a streamed response that returns the content in chunks.

    Parameters
    ----------
    content : bytes
        The content of the response.

    Returns
    -------
    unittest.mock.MagicMock
        The response, usable as a context manager.
    """
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [content[:10], content[10:]]
    return response


def test_download_future_gridded_population(tmp_path):
    """
    Test the download of the population of a scenario.

    The archive is downloaded from the download server of Figshare and
    extracted, its folder is renamed to the scenario, and the archive
    is removed.
    """
    with patch(
        "requests.get", return_value=_response(_archive("SPP1"))
    ) as get:
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP1"
        )

    url = get.call_args.args[0]
    assert url.startswith("https://ndownloader.figshare.com/files/")
    assert os.path.exists(tmp_path / "SSP1" / "population.tif")
    assert not os.path.exists(tmp_path / "SSP1.zip")


def test_download_future_gridded_population_not_a_zip(tmp_path):
    """
    Test that a response that is not an archive raises an error.

    The partial file is removed, so that the next run downloads again.
    """
    with (
        patch("requests.get", return_value=_response(b"<html></html>")),
        pytest.raises(zipfile.BadZipFile),
    ):
        gridded_population._download_future_gridded_population(
            str(tmp_path), "SSP3"
        )

    assert not os.path.exists(tmp_path / "SSP3.zip")

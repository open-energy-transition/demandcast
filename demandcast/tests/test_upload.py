"""
License: AGPL-3.0.

Description:

    Tests for the upload script.
"""

from unittest.mock import patch

import pytest
import upload
import utils.paths


def _write_files(folder, names):
    """
    Write empty files of electricity demand.

    Parameters
    ----------
    folder : pathlib.Path
        The folder of the files.
    names : list[str]
        The names of the files.
    """
    for name in names:
        (folder / name).write_bytes(b"")


def test_upload_to_gcs(tmp_path, frozen_now):
    """Test that the parquet files are uploaded to the bucket."""
    _write_files(tmp_path, ["FRA_entsoe.parquet", "notes.txt"])
    config = upload.ConfigModel(
        target_platform="gcs",
        data_directory=str(tmp_path),
        gcs_bucket_name="bucket",
    )

    with patch("utils.uploader.upload_to_gcs") as mock_upload_to_gcs:
        upload.main(config)

    mock_upload_to_gcs.assert_called_once_with(
        str(tmp_path / "FRA_entsoe.parquet"),
        "bucket",
        f"upload_{frozen_now:%Y-%m-%d}/FRA_entsoe.parquet",
    )


def test_upload_to_zenodo(tmp_path):
    """Test that only the redistributable data goes to Zenodo."""
    _write_files(tmp_path, ["CHL_cen.parquet", "MEX_cenace.parquet"])
    config = upload.ConfigModel(
        target_platform="zenodo",
        data_directory=str(tmp_path),
        made_by_oet=True,
        publish_to_zenodo=False,
    )

    with patch("utils.uploader.upload_to_zenodo") as mock_upload_to_zenodo:
        upload.main(config)

    mock_upload_to_zenodo.assert_called_once_with(
        str(tmp_path / "CHL_cen.parquet"),
        data_type="actual",
        made_by_oet=True,
        publish=False,
        testing=True,
    )


def test_upload_to_zenodo_needs_metadata(monkeypatch, tmp_path):
    """Test that data not made by OET needs its Zenodo metadata."""
    _write_files(tmp_path, ["CHL_cen.parquet"])
    monkeypatch.setattr(utils.paths, "CONFIG_FOLDER", str(tmp_path))
    config = upload.ConfigModel(
        target_platform="zenodo",
        data_directory=str(tmp_path),
        made_by_oet=False,
        publish_to_zenodo=False,
    )

    with pytest.raises(FileNotFoundError, match="zenodo_metadata"):
        upload.main(config)


@pytest.mark.parametrize(
    ("file_name", "data_source"),
    [
        ("CHL_cen.parquet", "cen"),
        ("MEX_BCS_cenace.parquet", "cenace"),
        ("AUS_QLD_aemo_nem.parquet", "aemo_nem"),
        ("NGA_oluwole_et_al.parquet", "oluwole_et_al"),
    ],
)
def test_get_data_source(file_name, data_source):
    """Test that the data source is the one that ends the file name."""
    assert upload._get_data_source(file_name) == data_source


def test_get_data_source_with_overlapping_names():
    """Test that the longest data source name ending the file wins."""
    with patch(
        "utils.data_sources.read_data_sources",
        return_value=["nem", "aemo_nem"],
    ):
        assert (
            upload._get_data_source("AUS_QLD_aemo_nem.parquet") == "aemo_nem"
        )


def test_get_data_source_errors():
    """Test that an unknown data source raises an error."""
    with pytest.raises(ValueError, match="No data source found"):
        upload._get_data_source("FRA_unknown.parquet")

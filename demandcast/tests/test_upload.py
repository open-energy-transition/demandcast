"""
License: AGPL-3.0.

Description:

    Tests for the upload script.
"""

from unittest.mock import patch

import pytest
import upload


def test_read_and_check_configuration():
    """Test that the script reads its own configuration file."""
    with patch(
        "utils.config.read_configuration",
        return_value={"target_platform": "gcs", "data_directory": "data"},
    ) as mock_read_configuration:
        config = upload._read_and_check_configuration()

    assert mock_read_configuration.call_args.args[0] == "upload"
    assert config.target_platform == "gcs"


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
        "utils.entities.read_data_sources", return_value=["nem", "aemo_nem"]
    ):
        assert (
            upload._get_data_source("AUS_QLD_aemo_nem.parquet") == "aemo_nem"
        )


def test_get_data_source_errors():
    """Test that an unknown data source raises an error."""
    with pytest.raises(ValueError, match="No data source found"):
        upload._get_data_source("FRA_unknown.parquet")

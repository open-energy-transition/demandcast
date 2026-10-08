"""
License: AGPL-3.0.

Description:

    Tests for the upload script.
"""

from unittest.mock import patch

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

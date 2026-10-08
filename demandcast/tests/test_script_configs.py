"""
License: AGPL-3.0.

Description:

    Tests that the scripts read and validate their default
    configuration files.
"""

import importlib
import os
import sys

import pytest
import utils.config


@pytest.mark.parametrize(
    "script",
    [
        "assemble",
        "check",
        "cross_validate",
        "forecast",
        "plot",
        "retrieve",
        "train",
        "upload",
        "validate",
    ],
)
def test_default_configuration_is_valid(script, monkeypatch):
    """Test that the script reads its default configuration."""
    config_file_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        f"{script}_config.yaml",
    )
    monkeypatch.setattr(
        sys, "argv", [f"{script}.py", "--config", config_file_path]
    )

    importlib.import_module(script)._read_and_check_configuration()

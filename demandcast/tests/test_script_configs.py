"""
License: AGPL-3.0.

Description:

    Tests that the default configuration files of the scripts are
    valid.
"""

import importlib
import os

import pytest
import utils.config
import yaml


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
def test_default_configuration_is_valid(script):
    """Test that the default configuration of the script is valid."""
    config_file_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        f"{script}_config.yaml",
    )
    with open(config_file_path, encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)

    importlib.import_module(script).ConfigModel(**raw_config)

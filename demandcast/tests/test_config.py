# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the directories module in the ETL
    utility package.
"""

import logging
import os
import sys
import textwrap

import pytest
import utils.config


def test_load_paths():
    """
    Test if the folders structure is read correctly.

    This test checks if the keys and values in the yaml file are read
    correctly and if the absolute paths are constructed as expected.
    """
    # Read the folders structure from the sample yaml file.
    structure = utils.config.read_folders_structure()

    # Get the root path of DemandCast.
    absolute_path = os.path.abspath(
        os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
    )

    # Check if the folders are read correctly.
    assert structure["config_folder"] == os.path.join(absolute_path, "config")
    assert structure["log_files_folder"] == os.path.join(absolute_path, "logs")
    assert structure["figures_folder"] == os.path.join(
        absolute_path, "figures"
    )
    assert structure["shapes_folder"] == os.path.join(absolute_path, "shapes")
    assert structure["checks_folder"] == os.path.join(absolute_path, "checks")
    assert structure["retrievals_folder"] == os.path.join(
        absolute_path, "retrievals"
    )
    assert structure["electricity_demand_data_sources_folder"] == os.path.join(
        absolute_path, "retrievals", "electricity_demand_data_sources"
    )
    assert structure["data_folder"] == os.path.join(absolute_path, "data")
    assert structure[
        "manually_downloaded_electricity_demand_folder"
    ] == os.path.join(
        absolute_path, "data", "electricity_demand", "manual_downloads"
    )
    assert structure["electricity_demand_folder"] == os.path.join(
        absolute_path, "data", "electricity_demand"
    )
    assert structure[
        "annual_electricity_demand_per_capita_folder"
    ] == os.path.join(
        absolute_path, "data", "annual_electricity_demand_per_capita"
    )
    assert structure["population_folder"] == os.path.join(
        absolute_path, "data", "population"
    )
    assert structure["gridded_population_folder"] == os.path.join(
        absolute_path, "data", "gridded_population"
    )
    assert structure["gdp_ppp_per_capita_folder"] == os.path.join(
        absolute_path, "data", "gdp_ppp_per_capita"
    )
    assert structure["gridded_gdp_ppp_folder"] == os.path.join(
        absolute_path, "data", "gridded_gdp_ppp"
    )
    assert structure["gridded_weather_folder"] == os.path.join(
        absolute_path, "data", "gridded_weather"
    )
    assert structure["temperature_folder"] == os.path.join(
        absolute_path, "data", "temperature"
    )
    assert structure["ml_models_folder"] == os.path.join(
        absolute_path, "ml_models"
    )
    assert structure["trained_ml_models_folder"] == os.path.join(
        absolute_path, "ml_models", "trained"
    )
    assert structure["ml_validation_folder"] == os.path.join(
        absolute_path, "ml_models", "results", "validation"
    )
    assert structure["ml_cross_validation_folder"] == os.path.join(
        absolute_path, "ml_models", "results", "cross_validation"
    )
    assert structure["ml_forecasts_folder"] == os.path.join(
        absolute_path, "ml_models", "results", "forecasts"
    )


def test_read_configuration_with_existing_file(tmp_path, monkeypatch):
    """
    Test reading a configuration file.

    This test creates a temporary configuration file, reads it using
    the utility function, and checks if the content is read correctly.
    It also tests the behavior when the configuration file does not
    exist.
    """
    # Create a temporary configuration file.
    config_content = textwrap.dedent(
        """
        foo: 1
        bar: true
        baz: "hello"
        """
    )
    config_file = tmp_path / "my_script_config.yaml"
    config_file.write_text(config_content, encoding="utf-8")

    # Make argparse see the temporary config file path.
    monkeypatch.setattr(
        sys,
        "argv",
        ["pytest", "--config", str(config_file)],
    )

    # Read the configuration using the utility function.
    config = utils.config.read_configuration("my_script", "Test script")

    # Check if the configuration is read correctly.
    assert config == {"foo": 1, "bar": True, "baz": "hello"}

    # Create a non-existing configuration file path.
    missing_file = tmp_path / "non_existing_config.yaml"
    monkeypatch.setattr(
        sys,
        "argv",
        ["pytest", "--config", str(missing_file)],
    )

    # Attempt to read the non-existing configuration file and expect
    # a FileNotFoundError.
    with pytest.raises(FileNotFoundError):
        utils.config.read_configuration("my_script", "Test script")


def test_set_up_logging(tmp_path, monkeypatch):
    """
    Test the set_up_logging function.

    This test verifies that the logging configuration is set up
    correctly and that log files are created in the expected location.
    """
    # Clear any existing logging handlers to avoid conflicts.
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Mock the read_folders_structure to return a temporary log folder.
    mock_structure = {"log_files_folder": str(tmp_path / "logs")}

    def mock_read_folders_structure():
        return mock_structure

    monkeypatch.setattr(
        utils.config, "read_folders_structure", mock_read_folders_structure
    )

    # Call the set_up_logging function.
    utils.config.set_up_logging("test_process")

    # Check if the log directory was created.
    log_dir = tmp_path / "logs"
    assert log_dir.exists()

    # Check if a log file was created.
    log_files = list(log_dir.glob("test_process_*.log"))
    assert len(log_files) == 1

    # Test that logging actually works by writing a message.
    logging.info("Test log message")

    # Flush and close all handlers to ensure the log is written.
    for handler in logging.root.handlers:
        handler.flush()

    # Read the log file and verify the message was written.
    log_content = log_files[0].read_text()
    assert "Test log message" in log_content
    assert "INFO" in log_content

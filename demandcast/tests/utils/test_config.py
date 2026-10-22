"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the config module.
"""

import logging
import os
import re
import sys
import textwrap

import pytest
import utils.config
import utils.paths


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

    # Write the logs in the temporary data folder.
    monkeypatch.setenv(
        utils.paths.DATA_FOLDER_VARIABLE, str(tmp_path / "data")
    )

    # Call the set_up_logging function.
    utils.config.set_up_logging("test_process")

    # Check if the log directory was created.
    log_dir = tmp_path / "data" / "logs"
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


def test_read_api_key(tmp_path, monkeypatch):
    """Test that a key is read from the .env file of the root folder."""
    monkeypatch.setattr(
        utils.paths, "ENV_FILE", os.path.join(str(tmp_path), ".env")
    )
    (tmp_path / ".env").write_text("TEST_SERVICE_API_KEY=secret-value\n")
    # Remove the key that the .env file sets at the end of the test.
    monkeypatch.setenv("TEST_SERVICE_API_KEY", "")
    monkeypatch.delenv("TEST_SERVICE_API_KEY")

    api_key = utils.config.read_api_key("TEST_SERVICE_API_KEY", "Test")

    assert api_key == "secret-value"


@pytest.mark.parametrize("api_key", [None, ""])
def test_read_api_key_without_the_key(tmp_path, monkeypatch, api_key):
    """Test that the error says how to set a missing or empty key."""
    monkeypatch.setattr(
        utils.paths, "ENV_FILE", os.path.join(str(tmp_path), ".env")
    )
    monkeypatch.setenv("TEST_SERVICE_API_KEY", "")
    if api_key is None:
        monkeypatch.delenv("TEST_SERVICE_API_KEY")

    with pytest.raises(
        ValueError,
        match=re.escape(
            "The Test API key is not set. Please set the TEST_SERVICE_API_KEY"
        ),
    ):
        utils.config.read_api_key("TEST_SERVICE_API_KEY", "Test")

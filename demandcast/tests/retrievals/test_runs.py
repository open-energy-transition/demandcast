"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of each country or subdivision, which goes
    on after those that fail.
"""

import logging

import pytest

import retrievals.runs


def test_retrieval_goes_on_after_a_code_that_fails(monkeypatch, caplog):
    """
    Test that the codes after one that fails are retrieved.

    The error of the code is logged without the API key in its message,
    and an error at the end lists the codes that failed.
    """
    monkeypatch.setenv("TEST_API_KEY", "secret")
    retrieved = []

    def retrieve(code):
        """
        Retrieve a code, and fail for Germany.

        Raises
        ------
        ValueError
            For Germany, with the API key in its message.
        """
        if code == "DEU":
            raise ValueError("HTTP 500 for https://example.org?key=secret")
        retrieved.append(code)

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(RuntimeError, match="failed for 1 of 3 codes: DEU"),
    ):
        retrievals.runs.run_for_each_code(
            ["DEU", "FRA", "ITA"], retrieve, "electricity demand of test"
        )

    assert retrieved == ["FRA", "ITA"]
    assert (
        "ValueError: HTTP 500 for https://example.org?key=***" in caplog.text
    )
    assert "secret" not in caplog.text


def test_single_code_raises_its_own_error():
    """Test that a single code raises its own error."""

    def retrieve(_code):
        """
        Fail.

        Raises
        ------
        ValueError
            Always.
        """
        raise ValueError("The format changed")

    with pytest.raises(ValueError, match="The format changed"):
        retrievals.runs.run_for_each_code(["FRA"], retrieve, "test")


def test_retrieval_of_all_codes():
    """Test that all the codes are retrieved, in order."""
    retrieved: list[str] = []

    retrievals.runs.run_for_each_code(
        ["DEU", "FRA"], retrieved.append, "test", leave=False
    )

    assert retrieved == ["DEU", "FRA"]

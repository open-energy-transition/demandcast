"""
License: AGPL-3.0.

Description:

    Tests of the related countries and subdivisions.
"""

import pandas as pd
import pytest

import utils.data_sources
import utils.paths
import utils.relations


@pytest.fixture
def shares_and_exceptions(tmp_path, monkeypatch):
    """
    Write shares of people and exceptions in temporary folders.

    Returns
    -------
    pathlib.Path
        The file of the exceptions, to rewrite.
    """
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))
    monkeypatch.setattr(utils.paths, "CONFIG_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        utils.data_sources,
        "read_all_codes",
        lambda: ["USA", "USA_CAISO", "USA_CAL", "USA_NV"],
    )
    pd.DataFrame(
        {
            "Entity code": ["USA", "USA_CAL", "USA_CAL"],
            "Other code": ["USA_CAL", "USA_CAISO", "USA_NV"],
            "Share of entity": [0.12, 1.0, 0.002],
            "Share of other": [1.0, 0.9, 0.05],
            "Related": [True, True, False],
        }
    ).to_csv(tmp_path / "related_entities.csv", index=False)
    exceptions = tmp_path / "related_entities.yaml"
    exceptions.write_text("related: []\nunrelated: []\n")
    return exceptions


@pytest.mark.usefixtures("shares_and_exceptions")
def test_read_related_entities():
    """
    Test that entities are related by the larger share of their people.

    A pair related through a code that is not asked for is left out.
    """
    related = utils.relations.read_related_entities(
        ["USA", "USA_CAL", "USA_NV"]
    )

    assert related == {
        "USA": {"USA_CAL"},
        "USA_CAL": {"USA"},
        "USA_NV": set(),
    }


def test_exceptions_to_the_shares(shares_and_exceptions):
    """Test that the exceptions relate or separate entities."""
    shares_and_exceptions.write_text(
        "related:\n  - [USA_CAL, USA_NV]\nunrelated:\n  - [USA, USA_CAL]\n"
    )

    related = utils.relations.read_related_entities(
        ["USA", "USA_CAL", "USA_NV"]
    )

    assert related == {
        "USA": set(),
        "USA_CAL": {"USA_NV"},
        "USA_NV": {"USA_CAL"},
    }


def test_exceptions_with_an_unknown_code(shares_and_exceptions):
    """Test that a code of the exceptions without data is rejected."""
    shares_and_exceptions.write_text("related:\n  - [USA_CAL, USA_NVV]\n")

    with pytest.raises(ValueError, match=r"\['USA_NVV'\] of .* are not"):
        utils.relations.read_related_entities(["USA_CAL"])


def test_exceptions_of_the_configuration_are_codes_with_data():
    """Test that the exceptions of the configuration are valid."""
    assert utils.relations.read_related_entities([]) == {}


def test_superseded_entities():
    """Test that an entity followed by a related one is superseded."""
    first_times = pd.Series(
        pd.to_datetime(["2000-01-01", "2013-01-01", "2000-01-01"]),
        index=["BRA_N-2000", "BRA_N-2013", "BRA_NE"],
    )
    last_times = pd.Series(
        pd.to_datetime(["2012-12-31", "2014-12-31", "2014-12-31"]),
        index=first_times.index,
    )
    related = {
        "BRA_N-2000": {"BRA_N-2013"},
        "BRA_N-2013": {"BRA_N-2000"},
        "BRA_NE": set(),
    }

    assert utils.relations.get_superseded_entities(
        first_times, last_times, related
    ) == {"BRA_N-2000"}


def test_read_checked_codes(tmp_path, monkeypatch):
    """Test that the checked codes are read, and none before a check."""
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))
    assert utils.relations.read_checked_codes() == []

    (tmp_path / "related_entities_codes.txt").write_text("USA\nUSA_CAL\n\n")

    assert utils.relations.read_checked_codes() == ["USA", "USA_CAL"]


def test_all_codes_were_checked():
    """
    Test that the related entities were computed for all the codes.

    Notes
    -----
    A code of a data source that the check never considered has no
    shares, so the cross-validation would not keep it apart from the
    entities that share its people.
    """
    unchecked = sorted(
        set(utils.data_sources.read_all_codes())
        - set(utils.relations.read_checked_codes())
    )

    assert not unchecked, (
        f"The related entities were not computed for {unchecked}: run "
        "`python check.py` with `check: related_entities`, which "
        f"updates {utils.relations.get_shares_file()} and "
        f"{utils.relations.get_codes_file()}."
    )

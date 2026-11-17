"""
License: AGPL-3.0.

Description:

    Tests of the related countries and subdivisions.
"""

import pandas as pd
import pytest

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

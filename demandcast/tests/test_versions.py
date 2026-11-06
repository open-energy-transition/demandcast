"""
License: AGPL-3.0.

Description:

    Tests that the version of DemandCast in demandcast/pyproject.toml is
    the one in CITATION.cff, which GitHub shows to cite the repository.
    The release tag must match both, which the Docker workflow checks on
    version tags.
"""

import pathlib
import tomllib

import yaml

# The root of the repository.
REPOSITORY = pathlib.Path(__file__).resolve().parents[2]


def test_versions_match():
    """Test that pyproject.toml and CITATION.cff have one version."""
    with open(REPOSITORY / "demandcast" / "pyproject.toml", "rb") as file:
        version = tomllib.load(file)["project"]["version"]
    with open(REPOSITORY / "CITATION.cff", encoding="utf-8") as file:
        citation = yaml.safe_load(file)

    assert str(citation["version"]) == version

"""
License: AGPL-3.0.

Description:

    Tests of the shares of the people of the entities that overlap, with
    shapes and a gridded population made for the tests.
"""

import geopandas
import numpy as np
import pandas as pd
import pytest
import shapely
from shapely.geometry import box

import checks.related_entities
import utils.paths

# The shapes of the tests: a country and two of its subdivisions that
# share a strip, and another country.
SHAPES = {
    "XXX": box(0.25, 0.25, 3.75, 1.75),
    "XXX_A": box(0.25, 0.25, 1.75, 1.75),
    "XXX_B": box(1.25, 0.25, 3.75, 1.75),
    "XXX_C": box(0.25, 0.25, 0.75, 0.75),
    "YYY": box(1.25, 0.25, 3.75, 1.75),
}


@pytest.fixture(autouse=True)
def uniform_population(monkeypatch):
    """
    Give the shapes, and the same population to every grid cell.

    The cells are of 0.05 degrees, each with one person, and are counted
    in a shape by their centers.

    Returns
    -------
    list[float]
        The populations counted, in order.
    """
    x_grid, y_grid = np.meshgrid(
        np.arange(0.025, 4, 0.05), np.arange(0.025, 2, 0.05)
    )
    counted: list[float] = []

    def get_total_in_geometry(geometry, year, scenario):
        """
        Count the cells whose centers are in the shape.

        Returns
        -------
        float
            The number of cells.
        """
        assert (year, scenario) == (2020, None)
        counted.append(
            float(shapely.contains_xy(geometry, x_grid, y_grid).sum())
        )
        return counted[-1]

    monkeypatch.setattr(
        checks.related_entities.retrievals.gridded_population,
        "get_total_in_geometry",
        get_total_in_geometry,
    )
    monkeypatch.setattr(
        checks.related_entities.utils.shapes,
        "get_entity_shape",
        lambda code, **_: geopandas.GeoDataFrame(
            geometry=[SHAPES[code]], crs="EPSG:4326"
        ),
    )
    return counted


def test_get_shares():
    """
    Test the shares of the people of the entities of a country.

    With the same population everywhere, the shares are those of the
    areas: the subdivisions are 3/7 and 5/7 of the country, and share a
    strip with a third of the people of A and a fifth of those of B.
    The other country is not compared.
    """
    shares = checks.related_entities.get_shares(
        ["XXX", "XXX_A", "XXX_B", "YYY"]
    )

    assert shares[["Entity code", "Other code"]].to_numpy().tolist() == [
        ["XXX", "XXX_A"],
        ["XXX", "XXX_B"],
        ["XXX_A", "XXX_B"],
    ]
    expected = [[3 / 7, 1.0], [5 / 7, 1.0], [1 / 3, 1 / 5]]
    np.testing.assert_allclose(
        shares[["Share of entity", "Share of other"]].to_numpy(),
        expected,
        atol=0.01,
    )
    assert shares["Related"].all()


def test_run_check(tmp_path, monkeypatch, uniform_population):
    """
    Test that the shares and the codes are saved in the checks folder.

    The people of each entity are counted once, and those of each shared
    area once.
    """
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))
    monkeypatch.setattr(
        checks.related_entities.utils.data_sources,
        "read_all_codes",
        lambda: ["XXX_A", "XXX_B", "XXX_C"],
    )

    checks.related_entities.run_check()

    # C is in A, and apart from B.
    saved = pd.read_csv(tmp_path / "related_entities.csv")
    assert saved[["Entity code", "Other code"]].to_numpy().tolist() == [
        ["XXX_A", "XXX_B"],
        ["XXX_A", "XXX_C"],
    ]
    # The strip of A and B, A, B, the area that A and C share, and C.
    assert uniform_population == [10 * 30, 30 * 30, 50 * 30, 10 * 10, 10 * 10]
    assert (tmp_path / "related_entities_codes.txt").read_text() == (
        "XXX_A\nXXX_B\nXXX_C\n"
    )


@pytest.mark.parametrize(
    "other",
    [
        box(1.75, 0.25, 3.75, 1.75),
        box(2.0, 0.25, 3.75, 1.75),
        box(1.7495, 0.25, 3.75, 1.75),
    ],
    ids=["touching", "apart", "sliver"],
)
def test_entities_without_shared_area(other):
    """Test that touching, apart and sliver shapes share no people."""
    shapes = {
        name: geopandas.GeoDataFrame(geometry=[shape], crs="EPSG:4326")
        for name, shape in [("XXX_A", SHAPES["XXX_A"]), ("XXX_D", other)]
    }

    assert (
        checks.related_entities._get_shares("XXX_A", "XXX_D", shapes, {})
        is None
    )

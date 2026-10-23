"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the figures module.
"""

import tempfile
from pathlib import Path

import geopandas
from shapely import Point

import utils.figures
import utils.paths


def test_simple_plot(monkeypatch):
    """
    Test the simple_plot function from the figures module.

    This test checks if the function correctly creates a plot and saves
    it to the specified directory.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        A pytest fixture that allows us to modify the behavior of the
        folder of the figures to return a temporary directory.
    """
    # Create a temporary directory for figure output.
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the figures in the temporary directory.
        monkeypatch.setattr(
            utils.paths,
            "get_results_folder",
            lambda _kind: tmpdir,
        )

        # Create a simple GeoDataFrame.
        gdf = geopandas.GeoDataFrame(
            {"value": [1, 2], "geometry": [Point(0, 0), Point(1, 1)]},
            crs="EPSG:4326",
        )

        # Define figure name.
        figure_name = "test_plot"

        # Run the plotting function.
        utils.figures.simple_plot(gdf, figure_name)

        # Assert that the figure was created.
        expected_path = Path(tmpdir) / f"{figure_name}.png"
        assert expected_path.exists()
        assert expected_path.stat().st_size > 0

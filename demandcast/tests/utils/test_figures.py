"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the figures module.
"""

import tempfile
from pathlib import Path

import geopandas
import matplotlib.pyplot as plt
from shapely import Point

import utils.figures
import utils.paths


def test_simple_plot(monkeypatch):
    """
    Test the simple_plot function from the figures module.

    The figure is saved in the folder of the results.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Save the figures in the temporary directory.
        monkeypatch.setattr(
            utils.paths,
            "get_results_folder",
            lambda _kind: tmpdir,
        )

        gdf = geopandas.GeoDataFrame(
            {"value": [1, 2], "geometry": [Point(0, 0), Point(1, 1)]},
            crs="EPSG:4326",
        )

        figure_name = "test_plot"

        utils.figures.simple_plot(gdf, figure_name)

        expected_path = Path(tmpdir) / f"{figure_name}.png"
        assert expected_path.exists()
        assert expected_path.stat().st_size > 0


def test_save_figure(tmp_path):
    """Test that a figure is saved in the format of its extension."""
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    file_path = tmp_path / "figure.png"

    utils.figures.save_figure(fig, str(file_path), transparent=True)
    plt.close(fig)

    assert file_path.read_bytes().startswith(b"\x89PNG")
    assert [path.name for path in tmp_path.iterdir()] == ["figure.png"]

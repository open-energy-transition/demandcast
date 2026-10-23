"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of the gridded GDP PPP, with a small global
    grid in place of the downloaded ones.
"""

import os

import numpy as np
import pytest
import utils.paths
import xarray
from retrievals import gridded_gdp_ppp


# The netCDF4 library sets the shape of arrays, which NumPy 2.5
# deprecates.
@pytest.mark.filterwarnings(
    "ignore:Setting the shape on a NumPy array:DeprecationWarning"
)
def test_run_data_retrieval(monkeypatch):
    """
    Test that the grid of each entity is saved in the processed folder.

    The global grid of each year and scenario is read from the raw
    folder, and a grid that exists is not extracted again.
    """
    global_grid = xarray.DataArray(
        np.arange(16.0).reshape(4, 4),
        coords={"y": [0.5, 1.5, 2.5, 3.5], "x": [0.5, 1.5, 2.5, 3.5]},
        dims=["y", "x"],
    )
    downloads: list[str] = []
    read: list[tuple[str, str]] = []

    def read_gdp_ppp(folder, year_scenario):
        read.append((folder, year_scenario))
        return global_grid

    monkeypatch.setattr(
        gridded_gdp_ppp.utils.availability,
        "check_and_get_codes_with",
        lambda *_, **__: ["FRA", "DEU"],
    )
    monkeypatch.setattr(gridded_gdp_ppp, "_download_gdp_ppp", downloads.append)
    monkeypatch.setattr(gridded_gdp_ppp, "_read_gdp_ppp", read_gdp_ppp)
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_shape",
        lambda code, **_: code,
    )
    monkeypatch.setattr(
        gridded_gdp_ppp.utils.shapes,
        "get_entity_bounds",
        {"FRA": (0, 0, 2, 2), "DEU": (2, 2, 4, 4)}.get,
    )

    gridded_gdp_ppp.run_data_retrieval(None, None, 2020, None, None, None)
    gridded_gdp_ppp.run_data_retrieval(None, None, 2030, None, None, "SSP2")

    raw_folder = utils.paths.get_gridded_folder("gdp_ppp", "raw")
    processed_folder = utils.paths.get_gridded_folder("gdp_ppp", "processed")
    assert downloads == [raw_folder, raw_folder]
    assert read == [(raw_folder, "2020"), (raw_folder, "2030_SSP2")]
    assert sorted(os.listdir(processed_folder)) == [
        "DEU_0.25_deg_2020.nc",
        "DEU_0.25_deg_2030_SSP2.nc",
        "FRA_0.25_deg_2020.nc",
        "FRA_0.25_deg_2030_SSP2.nc",
    ]
    with xarray.open_dataarray(
        os.path.join(processed_folder, "DEU_0.25_deg_2020.nc")
    ) as germany:
        assert germany.values.tolist() == [[10.0, 11.0], [14.0, 15.0]]

    # A grid that exists is kept.
    path = os.path.join(processed_folder, "FRA_0.25_deg_2020.nc")
    os.utime(path, (0, 0))
    gridded_gdp_ppp.run_data_retrieval(None, None, 2020, None, None, None)

    assert os.path.getmtime(path) == 0

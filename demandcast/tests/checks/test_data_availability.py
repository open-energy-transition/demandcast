"""
License: AGPL-3.0.

Description:

    Tests for the check of the availability of data, with data made for
    the tests.
"""

import os

import geopandas
import pandas as pd
import shapely

import checks.data_availability
import utils.paths


def test_add_first_and_last_years_with_unsorted_years():
    """
    Test the first and last years when the years are not in order.

    The annual demand per capita has the years of Ember first and those
    of the World Bank after them, so the first and last years are the
    earliest and the latest, not the first and the last columns. The
    subdivisions and the countries without data have none.
    """
    data_source = pd.DataFrame(
        [[1.0, 2.0, 3.0, 4.0]],
        index=["FRA"],
        columns=[2000, 2024, 1990, 1999],
    )
    data_availability = pd.DataFrame(
        {
            "parent_iso_alpha_3_code": ["FRA", "FRA_X", "DEU"],
            "historical_electricity_demand_per_capita": [True, True, False],
        },
        index=["FRA", "FRA_X", "DEU"],
    )

    result = checks.data_availability._add_first_and_last_years(
        "historical_electricity_demand_per_capita",
        data_source,
        data_availability,
    )

    first = result["historical_electricity_demand_per_capita_first_year"]
    last = result["historical_electricity_demand_per_capita_last_year"]
    assert first["FRA"] == 1990
    assert last["FRA"] == 2024
    assert first[["FRA_X", "DEU"]].isna().all()
    assert last[["FRA_X", "DEU"]].isna().all()


def test_get_data_availability(monkeypatch, tmp_path):
    """
    Test the availability of each kind of data of each code.

    The subdivisions have no national population, and the area of a
    shape of a degree by a degree is greater than 500 km², unlike that
    of a hundredth of a degree.
    """
    years = pd.DataFrame(
        {2020: [1.0, 2.0], 2021: [1.0, None]}, index=["FRA", "DEU"]
    )
    module = checks.data_availability
    monkeypatch.setattr(
        module.utils.shapes,
        "get_all_codes_with_shapes",
        lambda: ["FRA", "FRA_X", "DEU", "LUX"],
    )
    monkeypatch.setattr(module.world_bank, "download", lambda _: years)
    for retrieval in (
        module.retrievals.annual_electricity_demand_per_capita,
        module.retrievals.gdp_ppp_per_capita,
    ):
        monkeypatch.setattr(retrieval, "get_historical_data", lambda: years)
    monkeypatch.setattr(
        module.iiasa, "read", lambda _: pd.DataFrame(index=["FRA"])
    )
    monkeypatch.setattr(
        module.utils.shapes,
        "get_entity_shape",
        lambda code, **_: geopandas.GeoDataFrame(
            geometry=[
                shapely.box(0, 45, 0.01, 45.01)
                if code == "LUX"
                else shapely.box(0, 45, 1, 46)
            ]
        ),
    )

    availability = module.get_data_availability()

    assert availability.index.tolist() == ["FRA", "FRA_X", "DEU", "LUX"]
    assert availability["entity_name"].tolist() == [
        "France",
        "Subdivision of France",
        "Germany",
        "Luxembourg",
    ]
    assert availability["historical_population"].tolist() == [
        True,
        False,
        True,
        False,
    ]
    assert availability["future_population"].tolist() == [
        True,
        False,
        False,
        False,
    ]
    assert availability["future_gdp_ppp_per_capita"].tolist() == [
        True,
        True,
        False,
        False,
    ]
    assert availability["historical_gdp_ppp_per_capita_last_year"]["DEU"] == (
        2020
    )
    assert availability["area_greater_than_500_km2"].tolist() == [
        True,
        True,
        True,
        False,
    ]

    # The summary is saved in the folder of the checks of the code.
    monkeypatch.setattr(utils.paths, "CHECKS_FOLDER", str(tmp_path))
    module.run_check()

    saved = pd.read_csv(
        os.path.join(tmp_path, "data_availability_summary.csv"), index_col=0
    )
    assert saved.index.tolist() == ["FRA", "FRA_X", "DEU", "LUX"]

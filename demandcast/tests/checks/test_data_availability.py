"""
License: AGPL-3.0.

Description:

    Tests for the check of the availability of data, with data made for
    the tests.
"""

import checks.data_availability
import pandas as pd


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

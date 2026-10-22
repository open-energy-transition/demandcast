"""
License: AGPL-3.0.

Description:

    Characterisation tests of the retrievals of the indicators: the
    population, the GDP PPP per capita and the annual electricity
    demand per capita. Each runs on synthetic national and gridded
    data, for a country and a subdivision, in historical years and two
    scenarios, and the names and values of the files that it writes
    are compared with those that it wrote before the retrievals shared
    their code.
"""

import json
import os
from typing import cast
from unittest.mock import patch

import pandas as pd
import pytest
import retrievals.annual_electricity_demand_per_capita as annual_demand
import utils.entities
import utils.paths
from retrievals import gdp_ppp_per_capita, population

pytestmark = pytest.mark.usefixtures("frozen_now")

# The values of each file, by local year, of each retrieval.
SNAPSHOTS_FILE = os.path.join(
    os.path.dirname(__file__), "indicator_snapshots.json"
)


def _national(base: float, growth: float) -> pd.DataFrame:
    """
    Make national data of India and France from 2015 to 2024.

    Parameters
    ----------
    base : float
        The value of India in 2015, which France has twice.
    growth : float
        The growth of each year.

    Returns
    -------
    pandas.DataFrame
        The values, with the countries as index and the years as
        columns.
    """
    return pd.DataFrame(
        {
            year: [base * growth ** (year - 2015), 2 * base]
            for year in range(2015, 2025)
        },
        index=["IND", "FRA"],
    )


def _future(_data, code, scenario, *_args) -> pd.Series:
    """
    Give the projections of a country from 2025 to 2100.

    Returns
    -------
    pandas.Series
        The values of each year, which grow with the pathway.
    """
    step = int(scenario[3]) * (2 if code == "FRA" else 1)
    return pd.Series(
        {year: 1000.0 + step * (year - 2024) for year in range(2025, 2101)}
    )


def _gridded(variable, _code, selected_years, *_args) -> pd.Series:
    """
    Give the total of a gridded variable of a subdivision.

    Returns
    -------
    pandas.Series
        The total of each selected year.
    """
    base = {"population": 30e6, "gdp_ppp": 9e11}[variable]
    return pd.Series(
        {year: base * (1 + 0.01 * (year - 2000)) for year in selected_years}
    )


def _run(retrieval: str, code: str) -> None:
    """
    Run a retrieval of a code in 2019 to 2021 and in 2030 and 2050.

    Parameters
    ----------
    retrieval : str
        The retrieval: "population", "gdp_ppp_per_capita" or
        "annual_electricity_demand_per_capita".
    code : str
        The code of the country or subdivision.
    """
    module = {
        "population": population,
        "gdp_ppp_per_capita": gdp_ppp_per_capita,
        "annual_electricity_demand_per_capita": annual_demand,
    }[retrieval]
    scenarios = (
        ["SSP2-45", "SSP5-Baseline"]
        if retrieval == "annual_electricity_demand_per_capita"
        else ["SSP2", "SSP5"]
    )
    patches = [
        patch.object(
            module.iiasa, "read", return_value=pd.DataFrame(index=["IND"])
        ),
        patch.object(
            module.iiasa, "extract_and_interpolate", side_effect=_future
        ),
        patch.object(
            module.iiasa,
            "extrapolate",
            side_effect=lambda _data, code, scenario, value, _year, years: (
                _future(None, code, scenario).reindex(years, method="ffill")
                + value
                - 1000.0
            ),
        ),
        patch(
            "retrievals.gridded_totals.get_total_value_from_gridded_data",
            side_effect=_gridded,
        ),
    ]
    if retrieval == "population":
        patches.append(
            patch.object(
                module.world_bank,
                "download",
                return_value=_national(1.3e9, 1.01),
            )
        )
    else:
        patches.append(
            patch.object(
                module,
                "get_historical_data",
                return_value=_national(
                    5000.0 if retrieval == "gdp_ppp_per_capita" else 900.0,
                    1.05,
                ),
            )
        )
    for active_patch in patches:
        active_patch.start()
    try:
        module.run_data_retrieval(code, None, None, 2019, 2021, None)
        for scenario in scenarios:
            module.run_data_retrieval(code, None, 2030, None, None, scenario)
            module.run_data_retrieval(code, None, 2050, None, None, scenario)
    finally:
        for active_patch in patches:
            active_patch.stop()


def _snapshot(retrieval: str, code: str) -> dict[str, dict[str, float]]:
    """
    Read the files that a retrieval wrote, by local year.

    Parameters
    ----------
    retrieval : str
        The retrieval.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    dict[str, dict[str, float]]
        The median value of each local year, rounded, of each file.
    """
    folder = utils.paths.get_indicator_folder(
        cast(utils.paths.Indicator, retrieval)
    )
    time_zone = utils.entities.get_time_zone(code)
    snapshot = {}
    for file_name in sorted(os.listdir(folder)):
        if not file_name.endswith(".parquet"):
            assert file_name.endswith(".csv")
            continue
        values = pd.read_parquet(os.path.join(folder, file_name)).iloc[:, 0]
        local_years = (
            pd.DatetimeIndex(values.index)
            .tz_localize("UTC")
            .tz_convert(time_zone)
            .year
        )
        yearly = values.groupby(local_years).median()
        snapshot[file_name] = {
            str(year): round(float(value), 6) for year, value in yearly.items()
        }
    return snapshot


@pytest.mark.parametrize(
    "retrieval",
    [
        "population",
        "gdp_ppp_per_capita",
        "annual_electricity_demand_per_capita",
    ],
)
@pytest.mark.parametrize("code", ["IND", "FRA", "IND_KL"])
def test_retrieval_of_indicator(retrieval, code):
    """Test that the files of a retrieval are those it wrote before."""
    _run(retrieval, code)

    with open(SNAPSHOTS_FILE, encoding="utf-8") as file:
        expected = json.load(file)[f"{retrieval}/{code}"]
    assert _snapshot(retrieval, code) == expected

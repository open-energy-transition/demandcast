"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of the population, with synthetic national
    data of the World Bank and gridded data of the subdivisions.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

import utils.paths
from retrievals import population

pytestmark = pytest.mark.usefixtures("frozen_now")


def _gridded_population(_variable, _code, selected_years, _available_years):
    """
    Give a gridded population of 30 million plus 1 million a year.

    Returns
    -------
    pandas.Series
        The population of each selected year.
    """
    return pd.Series(
        {year: 30e6 + 1e6 * (year - 2000) for year in selected_years}
    )


def _retrieve(code: str, start_year: int = 2019) -> pd.Series:
    """
    Retrieve the population from a year to 2025 and read it by year.

    Returns
    -------
    pandas.Series
        The population of each year.
    """
    # The World Bank gives India from 1990 until 2024, 2% more a year.
    national = pd.DataFrame(
        {year: [1300e6 * 1.02 ** (year - 2018)] for year in range(1990, 2025)},
        index=["IND"],
    )
    with (
        patch.object(population.world_bank, "download", return_value=national),
        patch.object(population.iiasa, "read"),
        patch.object(
            population.retrievals.gridded_totals,
            "get_total_value_from_gridded_data",
            side_effect=_gridded_population,
        ),
    ):
        population.run_data_retrieval(
            code=code,
            file=None,
            year=None,
            start_year=start_year,
            end_year=2025,
            scenario=None,
        )

    values = pd.read_parquet(
        os.path.join(
            utils.paths.get_indicator_folder("population"), f"{code}.parquet"
        )
    )["Population"]
    local_years = (
        pd.DatetimeIndex(values.index)
        .tz_localize("UTC")
        .tz_convert("Asia/Kolkata")
        .year
    )
    return values.groupby(local_years).median()


def test_population_of_country():
    """Test that a country has the population of the World Bank."""
    yearly = _retrieve("IND")

    # 2025, after the last year of the World Bank, has that of 2024.
    assert yearly[2019] == pytest.approx(1300e6 * 1.02)
    assert yearly[2024] == pytest.approx(1300e6 * 1.02**6)
    assert yearly[2025] == pytest.approx(1300e6 * 1.02**6)


def test_population_of_subdivision():
    """Test that a subdivision has the population of gridded data."""
    yearly = _retrieve("IND_KL")

    # The gridded data ends in 2020, after which the subdivision grows
    # as its country, 2% a year, until 2024, the last year of the
    # country.
    assert yearly[2019] == pytest.approx(49e6)
    assert yearly[2020] == pytest.approx(50e6)
    assert yearly[2023] == pytest.approx(50e6 * 1.02**3)
    assert yearly[2025] == pytest.approx(50e6 * 1.02**4)


def test_population_of_subdivision_before_the_gridded_data():
    """
    Test that a subdivision follows its country before the gridded data.

    The gridded data starts in 2000, before which the subdivision has
    its population of 2000 times the change of its country since then,
    until 1990, the first year of the country.
    """
    yearly = _retrieve("IND_KL", start_year=1985)

    assert yearly.index.min() == 1990
    assert yearly[1999] == pytest.approx(30e6 / 1.02)
    assert yearly[1990] == pytest.approx(30e6 / 1.02**10)
    assert yearly[2000] == pytest.approx(30e6)
    assert yearly[2001] == pytest.approx(31e6)

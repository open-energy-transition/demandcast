"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of the population, with synthetic national
    data of the World Bank and of IIASA, and gridded data of a
    subdivision and of its country, whose grids are flat, as those of
    Australia from 2000 to 2020.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

import utils.paths
from retrievals import population

pytestmark = pytest.mark.usefixtures("frozen_now")


@pytest.fixture(autouse=True)
def _clear_gridded_population():
    """Forget the gridded population that a test computed."""
    yield
    population._get_gridded_population.cache_clear()


def _gridded_population(_variable, code, selected_years, *_):
    """
    Give the gridded population of a subdivision or of its country.

    The subdivision has 30 million plus 1 million a year, and its
    country a flat 1 billion.

    Returns
    -------
    pandas.Series
        The population of each selected year.
    """
    return pd.Series(
        {
            year: 1e9 if "_" not in code else 30e6 + 1e6 * (year - 2000)
            for year in selected_years
        }
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
    """
    Test that a subdivision has its share of its country.

    Its share is that of its gridded population in that of its country,
    times the population of its country from the World Bank. The
    gridded data ends in 2020, after which the share is that of 2020,
    until 2024, the last year of the country.
    """
    yearly = _retrieve("IND_KL")

    assert yearly[2019] == pytest.approx(0.049 * 1300e6 * 1.02)
    assert yearly[2020] == pytest.approx(0.050 * 1300e6 * 1.02**2)
    assert yearly[2023] == pytest.approx(0.050 * 1300e6 * 1.02**5)
    assert yearly[2025] == pytest.approx(0.050 * 1300e6 * 1.02**6)


def test_population_of_subdivision_before_the_gridded_data():
    """
    Test that a subdivision has its share of 2000 before 2000.

    The gridded data starts in 2000, and the country in 1990.
    """
    yearly = _retrieve("IND_KL", start_year=1985)

    assert yearly.index.min() == 1990
    assert yearly[1990] == pytest.approx(0.030 * 1300e6 * 1.02**-28)
    assert yearly[1999] == pytest.approx(0.030 * 1300e6 * 1.02**-19)
    assert yearly[2001] == pytest.approx(0.031 * 1300e6 * 1.02**-17)


def test_future_population_of_subdivision():
    """
    Test that a subdivision has its share of its country's scenario.

    The share is that of the gridded population of the scenario.
    """
    iiasa_population = pd.DataFrame(index=["IND"])
    national = pd.Series({2030: 1500e6, 2031: 1510e6})
    with (
        patch.object(
            population.iiasa, "extract_and_interpolate", return_value=national
        ) as extract,
        patch.object(
            population.retrievals.gridded_totals,
            "get_total_value_from_gridded_data",
            side_effect=_gridded_population,
        ),
    ):
        future = population._extract_future_population(
            "IND_KL", iiasa_population, [2030, 2031], [2030], [2020], "SSP2"
        )

    assert extract.call_args.args[1:] == ("IND", "SSP2")
    assert future.to_dict() == pytest.approx(
        {2030: 0.060 * 1500e6, 2031: 0.061 * 1510e6}
    )


def test_population_of_subdivision_of_country_without_data():
    """Test the gridded population of a country without data."""
    with patch.object(
        population.retrievals.gridded_totals,
        "get_total_value_from_gridded_data",
        side_effect=_gridded_population,
    ):
        historical = population._extract_historical_population(
            "XKX_A", pd.DataFrame(index=["IND"]), [2001], [2001], [2000]
        )
        future = population._extract_future_population(
            "XKX_A",
            pd.DataFrame(index=["IND"]),
            [2030],
            [2030],
            [2020],
            "SSP2",
        )

    assert historical.to_dict() == {2001: 31e6}
    assert future.to_dict() == {2030: 60e6}

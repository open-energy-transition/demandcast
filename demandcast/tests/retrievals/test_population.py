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


def _retrieve(code: str, tmp_folders) -> pd.Series:
    """
    Retrieve the population of 2019 to 2025 and read it by year.

    Returns
    -------
    pandas.Series
        The population of each year.
    """
    # The World Bank gives India until 2024, 2% more a year from 2018.
    national = pd.DataFrame(
        {year: [1300e6 * 1.02 ** (year - 2018)] for year in range(2018, 2025)},
        index=["IND"],
    )
    with (
        patch.object(population.world_bank, "download", return_value=national),
        patch.object(population.iiasa, "read"),
        patch.object(
            population.utils.geospatial,
            "get_total_value_from_gridded_data",
            side_effect=_gridded_population,
        ),
    ):
        population.run_data_retrieval(
            code=code,
            file=None,
            year=None,
            start_year=2019,
            end_year=2025,
            scenario=None,
        )

    values = pd.read_parquet(
        os.path.join(tmp_folders["population_folder"], f"{code}.parquet")
    )["Population"]
    local_years = (
        pd.DatetimeIndex(values.index)
        .tz_localize("UTC")
        .tz_convert("Asia/Kolkata")
        .year
    )
    return values.groupby(local_years).median()


def test_population_of_country(tmp_folders):
    """Test that a country has the population of the World Bank."""
    yearly = _retrieve("IND", tmp_folders)

    # 2025, after the last year of the World Bank, has that of 2024.
    assert yearly[2019] == pytest.approx(1300e6 * 1.02)
    assert yearly[2024] == pytest.approx(1300e6 * 1.02**6)
    assert yearly[2025] == pytest.approx(1300e6 * 1.02**6)


def test_population_of_subdivision(tmp_folders):
    """Test that a subdivision has the population of gridded data."""
    yearly = _retrieve("IND_KL", tmp_folders)

    # The gridded data ends in 2020, whose population the years after it
    # have.
    assert yearly[2019] == pytest.approx(49e6)
    assert yearly[2020] == pytest.approx(50e6)
    assert yearly[2023] == pytest.approx(50e6)
    assert yearly[2025] == pytest.approx(50e6)

"""
License: AGPL-3.0.

Description:

    Tests for the historical GDP PPP per capita, the mean of the World
    Bank and the IMF, with synthetic tables of both by country code and
    year.
"""

import numpy as np
import pandas as pd

from retrievals import gdp_ppp_per_capita


def _table(values: dict[str, dict[int, float]]) -> pd.DataFrame:
    """
    Make a table of values by country code and year.

    Parameters
    ----------
    values : dict[str, dict[int, float]]
        The values of each country code, by year.

    Returns
    -------
    pandas.DataFrame
        The values, by country code (rows) and year (columns), as the
        World Bank and the IMF give them.
    """
    table = pd.DataFrame.from_dict(values, orient="index").sort_index(axis=1)
    table.index.name = "Country Code"
    table.columns.name = "Year"
    return table.astype(float)


def test_get_historical_data(monkeypatch):
    """Test that the historical data averages the two sources."""
    year = pd.Timestamp.now().year
    world_bank_data = _table(
        {
            "FRA": {year - 3: 100.0, year - 2: 110.0, year: 999.0},
            "DEU": {year - 3: 200.0, year - 2: np.nan},
            "ITA": {year - 3: 300.0},
        }
    )
    imf_data = _table(
        {
            "FRA": {
                year - 3: 120.0,
                year - 2: 130.0,
                year - 1: 140.0,
                year: 999.0,
            },
            "DEU": {year - 3: 220.0, year - 2: 230.0},
            "ESP": {year - 2: 400.0},
        }
    )
    variables = []

    def download(variable: str) -> pd.DataFrame:
        """
        Record the variable of the World Bank and give its data.

        Returns
        -------
        pandas.DataFrame
            The data of the World Bank.
        """
        variables.append(variable)
        return world_bank_data

    monkeypatch.setattr(gdp_ppp_per_capita.world_bank, "download", download)
    monkeypatch.setattr(
        gdp_ppp_per_capita.imf, "download_gdp_ppp_per_capita", lambda: imf_data
    )

    data = gdp_ppp_per_capita.get_historical_data()

    assert variables == ["gdp_ppp_per_capita"]
    # The years with both sources are their mean, the others take the
    # source that has them, and the current year is left out.
    pd.testing.assert_frame_equal(
        data,
        _table(
            {
                "DEU": {year - 3: 210.0, year - 2: 230.0, year - 1: np.nan},
                "ESP": {year - 3: np.nan, year - 2: 400.0, year - 1: np.nan},
                "FRA": {year - 3: 110.0, year - 2: 120.0, year - 1: 140.0},
                "ITA": {year - 3: 300.0, year - 2: np.nan, year - 1: np.nan},
            }
        ),
    )

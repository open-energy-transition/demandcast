"""
License: AGPL-3.0.

Description:

    Tests for the figure of the availability of the data, with
    synthetic codes, date ranges and annual data.
"""

import os

import numpy as np
import pandas as pd
import pytest

from figures import data_availability

# The continent of each code of the synthetic data.
CONTINENTS = {
    "NGA": "AF",
    "PER": "SA",
    "NPL": "AS",
    "CAN": "NA",
    "CAN_ON": "NA",
    "NOR": "EU",
    "LUX": "EU",
    "FRA": "EU",
    "IND": "AS",
    "AUS": "OC",
}


@pytest.fixture(autouse=True)
def synthetic_data(monkeypatch):
    """
    Give each code a date range and each country random annual data.

    Canada has data from 2018 to 2022, and Ontario from 2015 to 2023.

    Returns
    -------
    pandas.DataFrame
        The GDP PPP per capita of each country and year.
    """
    codes = list(CONTINENTS)
    monkeypatch.setattr(
        data_availability.utils.data_sources,
        "read_all_codes_with_electricity_demand_data",
        lambda: codes,
    )
    monkeypatch.setattr(
        data_availability.utils.codes,
        "get_continent_code",
        CONTINENTS.get,
    )
    monkeypatch.setattr(
        data_availability.utils.data_sources,
        "read_all_date_ranges",
        lambda: {
            code: (
                pd.Timestamp(f"{2015 + number % 4}-03-01"),
                pd.Timestamp(f"{2022 + number % 3}-10-31"),
            )
            for number, code in enumerate(codes)
        },
    )
    countries = sorted({code.split("_")[0] for code in codes})
    years = list(range(2010, 2026))
    rng = np.random.default_rng(0)
    gdp = pd.DataFrame(
        rng.uniform(2000, 120000, (len(countries), len(years))),
        index=countries,
        columns=years,
    )
    demand = pd.DataFrame(
        rng.uniform(100, 25000, (len(countries), len(years))),
        index=countries,
        columns=years,
    )
    monkeypatch.setattr(
        data_availability.retrievals.gdp_ppp_per_capita,
        "get_historical_data",
        lambda: gdp,
    )
    monkeypatch.setattr(
        data_availability.retrievals.annual_electricity_demand_per_capita,
        "get_historical_data",
        lambda: demand,
    )
    return gdp


def test_get_data(synthetic_data):
    """
    Test the counts of years and the first and last points.

    Each code counts its own years, with the data of its country, and
    the points of a country are those of the first and last years of its
    own data or of that of its subdivisions.
    """
    data = data_availability.get_data()

    assert list(data.gdp_points) == [
        "NGA",
        "PER",
        "NPL",
        "CAN",
        "NOR",
        "LUX",
        "FRA",
        "IND",
        "AUS",
    ]
    assert data.gdp_points["CAN"].index.tolist() == [2015, 2023]
    assert data.gdp_points["CAN"].tolist() == (
        synthetic_data.loc["CAN", [2015, 2023]].tolist()
    )
    assert data.continents["CAN"] == "NA"
    # The years of Canada and those of Ontario both count in North
    # America.
    fractions = data_availability._get_year_fractions(
        {"CAN": ["CAN"], "CAN_ON": ["CAN_ON"]}
    )
    assert list(fractions["CAN_ON"]) == list(range(2015, 2024))
    assert fractions["CAN_ON"][2016] == 1.0
    years = sum(fractions["CAN"].values()) + sum(fractions["CAN_ON"].values())
    assert sum(data.gdp_occurrence["NA"].values()) == pytest.approx(years)
    assert sum(
        data.electricity_demand_occurrence["NA"].values()
    ) == pytest.approx(years)


def test_plot(tmp_path):
    """Test that the figure is saved."""
    data_availability.plot(str(tmp_path))

    assert os.listdir(tmp_path) == [
        "data_availability_by_gpd_ppp_and_electricity_demand.png"
    ]


def test_get_height_of_bar_charts():
    """Test that the tallest stack of either chart sets the height."""
    gdp = {
        "EU": {"low": 100.0, "high": 300.0},
        "AS": {"low": 50.0, "high": 0.0},
    }
    demand = {
        "EU": {"low": 200.0, "high": 0.0},
        "AS": {"low": 300.0, "high": 0.0},
    }

    assert data_availability._get_height_of_bar_charts(
        gdp, demand
    ) == pytest.approx(525.0)

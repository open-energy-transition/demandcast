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
    "PAK": "AS",
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

    Canada has data from 2016, and Ontario from 2015.

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

    A country with a subdivision has the points of the code with the
    most years, and the counts add the fractions of the years of all
    the codes.
    """
    data = data_availability.get_data()

    assert list(data.gdp_points) == [
        "NGA",
        "PER",
        "PAK",
        "CAN",
        "NOR",
        "LUX",
        "FRA",
        "IND",
        "AUS",
    ]
    # Ontario has data from 2015, Canada from 2016.
    assert data.gdp_points["CAN"].index.tolist() == [2015, 2023]
    assert data.gdp_points["CAN"].tolist() == (
        synthetic_data.loc["CAN", [2015, 2023]].tolist()
    )
    assert data.continents["CAN"] == "NA"
    gdp_years = sum(
        sum(levels.values()) for levels in data.gdp_occurrence.values()
    )
    demand_years = sum(
        sum(levels.values())
        for levels in data.electricity_demand_occurrence.values()
    )
    fractions = data_availability._get_year_fractions(list(CONTINENTS))
    assert gdp_years == pytest.approx(
        sum(sum(years.values()) for years in fractions.values())
    )
    assert demand_years == pytest.approx(gdp_years)


def test_plot(tmp_path):
    """Test that the figure is saved."""
    data_availability.plot(str(tmp_path))

    assert os.listdir(tmp_path) == [
        "data_availability_by_gpd_ppp_and_electricity_demand.png"
    ]

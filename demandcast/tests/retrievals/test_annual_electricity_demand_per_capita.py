"""
License: AGPL-3.0.

Description:

    Tests for the retrieval of the annual electricity demand per capita,
    from Ember and the World Bank, with synthetic data.
"""

import io
import os
import zipfile
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import retrievals.annual_electricity_demand_per_capita as annual_demand
from retrievals.socio_economic_data_sources import ember, world_bank


def test_run_data_retrieval_of_future_scenario(tmp_folders):
    """Test that future data is saved where assemble.py reads it."""
    historical_data = pd.DataFrame(
        {2020: [7000.0], 2021: [7100.0]}, index=["FRA"]
    )

    with (
        patch.object(
            annual_demand, "get_historical_data", return_value=historical_data
        ),
        patch.object(annual_demand.iiasa, "read"),
        patch.object(
            annual_demand.iiasa,
            "extrapolate",
            side_effect=[pd.Series({2022: 7200.0}), pd.Series({2022: 7300.0})],
        ),
    ):
        # The second run replaces the year with its revised value.
        for __ in range(2):
            annual_demand.run_data_retrieval(
                code="FRA",
                file=None,
                year=2022,
                start_year=None,
                end_year=None,
                scenario="SSP2-45",
            )

    assert sorted(
        os.listdir(tmp_folders["annual_electricity_demand_per_capita_folder"])
    ) == [
        "FRA_SSP2_45.csv",
        "FRA_SSP2_45.parquet",
    ]
    saved = pd.read_parquet(
        os.path.join(
            tmp_folders["annual_electricity_demand_per_capita_folder"],
            "FRA_SSP2_45.parquet",
        )
    )["Annual electricity demand per capita (kWh)"]
    assert set(saved) == {7300.0}
    assert len(saved) == 8760


def test_download_of_ember(monkeypatch):
    """Test that the demand per capita of Ember is read in kWh."""
    long_format = pd.DataFrame(
        {
            "ISO 3 code": ["FRA", "FRA", "FRA", "DEU"],
            "Year": [2020, 2021, 2021, 2021],
            "Variable": [
                "Demand per capita",
                "Demand per capita",
                "Demand",
                "Demand per capita",
            ],
            "Value": [7.0, 7.1, 460.0, 6.7],
        }
    )
    monkeypatch.setattr(ember.pd, "read_csv", lambda _url: long_format)

    demand = ember.download_electricity_demand_per_capita()

    # The values in MWh become kWh, by country code and year.
    assert demand.loc["FRA"].to_dict() == {2020: 7000.0, 2021: 7100.0}
    assert demand.loc["DEU", 2021] == 6700.0
    assert pd.isna(demand.loc["DEU", 2020])


def test_download_of_world_bank(monkeypatch):
    """Test that the data of the World Bank is read from its archive."""
    csv = (
        '"Data Source","World Development Indicators",\n'
        "\n"
        '"Last Updated Date","2026-07-01",\n'
        "\n"
        '"Country Name","Country Code","Indicator Name","Indicator Code",'
        '"2020","2021",\n'
        '"France","FRA","Electric power consumption","EG.USE.ELEC.KH.PC",'
        '"6400","6500",\n'
        '"Kosovo","XK","Electric power consumption","EG.USE.ELEC.KH.PC",'
        '"3000","3100",\n'
        '"Nowhere","NWH","Electric power consumption","EG.USE.ELEC.KH.PC",'
        '"","",\n'
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as files:
        files.writestr("Metadata_Country_API.csv", "metadata")
        files.writestr("API_EG.USE.ELEC.KH.PC.csv", csv)

    class Response:
        content = archive.getvalue()

    monkeypatch.setattr(
        world_bank.requests, "get", lambda _url, **_kwargs: Response()
    )

    demand = world_bank.download("electricity_demand_per_capita")

    # The codes of three letters with data are kept.
    assert demand.index.tolist() == ["FRA"]
    assert demand.loc["FRA"].to_dict() == {2020: 6400.0, 2021: 6500.0}


def test_download_of_unknown_variable():
    """Test that an unknown variable of the World Bank is an error."""
    with pytest.raises(ValueError, match="variable must be"):
        world_bank.download("temperature")


def test_get_historical_data():
    """Test that Ember is completed by the World Bank scaled to it."""
    # Ember is 10% above the World Bank in France, 20% in Spain, and has
    # no data of Germany, and 2 years of Italy.
    ember_data = pd.DataFrame(
        {
            2019: [7700.0, 6000.0, np.nan, np.nan],
            2020: [7920.0, 6120.0, np.nan, 5000.0],
            2021: [np.nan, 6240.0, np.nan, 5100.0],
            2022: [8360.0, np.nan, np.nan, np.nan],
        },
        index=["FRA", "ESP", "DEU", "ITA"],
    )
    world_bank_data = pd.DataFrame(
        {
            2019: [7000.0, 5000.0, 6000.0, 4000.0],
            2020: [7200.0, 5100.0, 6100.0, 4500.0],
            2021: [7400.0, 5200.0, 6200.0, 4600.0],
            2022: [7600.0, 5300.0, 6300.0, 4700.0],
        },
        index=["FRA", "ESP", "DEU", "ITA"],
    )

    with (
        patch.object(
            annual_demand.ember,
            "download_electricity_demand_per_capita",
            return_value=ember_data,
        ),
        patch.object(
            annual_demand.world_bank, "download", return_value=world_bank_data
        ),
    ):
        demand = annual_demand.get_historical_data()

    # Ember gives the value, and the World Bank fills the years that it
    # does not have, times the ratio of the country (1.1 in France, 1.2
    # in Spain), or the median of the countries (1.15) for Germany and
    # for Italy, which has too few years of both.
    assert demand.loc["FRA"].round(2).to_dict() == {
        2019: 7700.0,
        2020: 7920.0,
        2021: 8140.0,
        2022: 8360.0,
    }
    assert demand.loc["ESP", 2022] == pytest.approx(6360.0)
    assert demand.loc["DEU"].round(2).to_dict() == {
        2019: 6900.0,
        2020: 7015.0,
        2021: 7130.0,
        2022: 7245.0,
    }
    assert demand.loc["ITA"].round(2).to_dict() == {
        2019: 4600.0,
        2020: 5000.0,
        2021: 5100.0,
        2022: 5405.0,
    }


@pytest.mark.parametrize("code", ["FRA", "IND_KL"])
def test_run_data_retrieval_of_historical_years(tmp_folders, code):
    """Test that the historical data is saved hourly in local years."""
    historical_data = pd.DataFrame(
        {2020: [7000.0, 1100.0], 2021: [7100.0, 1200.0]}, index=["FRA", "IND"]
    )

    with (
        patch.object(
            annual_demand, "get_historical_data", return_value=historical_data
        ),
        patch.object(annual_demand.iiasa, "read"),
    ):
        annual_demand.run_data_retrieval(
            code=code,
            file=None,
            year=None,
            start_year=2020,
            end_year=2021,
            scenario=None,
        )

    saved = pd.read_parquet(
        os.path.join(
            tmp_folders["annual_electricity_demand_per_capita_folder"],
            f"{code}.parquet",
        )
    )["Annual electricity demand per capita (kWh)"]
    # A subdivision has the demand per capita of its country, and each
    # value covers the hours of its year in local time, at their ends:
    # the last hour of 2020 ends at midnight on 2021-01-01.
    values = {"FRA": (7000.0, 7100.0), "IND_KL": (1100.0, 1200.0)}[code]
    last_hour_of_2020 = {
        "FRA": "2020-12-31 23:00",
        "IND_KL": "2020-12-31 18:30",
    }[code]
    assert saved[last_hour_of_2020] == values[0]
    assert (
        saved[pd.Timestamp(last_hour_of_2020) + pd.Timedelta(hours=1)]
        == (values[1])
    )

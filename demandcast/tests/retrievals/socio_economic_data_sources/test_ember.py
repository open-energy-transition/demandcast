"""
License: AGPL-3.0.

Description:

    Tests for the download of the electricity demand per capita of
    Ember, with a synthetic answer of its API: one record per country
    and year, with the year as text.
"""

import json

import pandas as pd
import pytest

from retrievals.socio_economic_data_sources import ember


def test_download_electricity_demand_per_capita(
    fake_downloads, tmp_path, monkeypatch
):
    """
    Test that the demand per capita of Ember is read from its API.

    The request has the key of EMBER_API_KEY and asks for the countries
    only, and the values in kWh are by country code and year, without
    the countries that have none.
    """
    records = [
        ("FRA", "2020", 7000.0),
        ("FRA", "2021", 7100.5),
        ("DEU", "2021", 6700.0),
        ("XYZ", "2020", None),
        ("XYZ", "2021", None),
    ]
    file_path = tmp_path / "ember.json"
    file_path.write_text(
        json.dumps(
            {
                "data": [
                    {
                        "entity_code": code,
                        "date": year,
                        "demand_kwh_per_capita": value,
                    }
                    for code, year, value in records
                ]
            }
        ),
        encoding="utf-8",
    )
    fake_downloads.serve(ember.API_URL, file_path)
    monkeypatch.setenv("EMBER_API_KEY", "test-key")

    demand = ember.download_electricity_demand_per_capita()

    assert [
        (method, url, kwargs["params"])
        for method, url, kwargs in fake_downloads.requests
    ] == [
        (
            "GET",
            ember.API_URL,
            {"is_aggregate_entity": "false", "api_key": "test-key"},
        )
    ]
    assert demand.index.name == "Country Code"
    assert demand.columns.name == "Year"
    assert sorted(demand.index) == ["DEU", "FRA"]
    assert demand.columns.tolist() == [2020, 2021]
    assert (demand.dtypes == "float64").all()
    assert demand.loc["FRA"].to_dict() == {2020: 7000.0, 2021: 7100.5}
    assert demand.loc["DEU", 2021] == 6700.0
    assert pd.isna(demand.loc["DEU", 2020])


def test_download_without_a_key(fake_downloads, monkeypatch):
    """Test that Ember asks for its API key if it is not set."""
    monkeypatch.setattr(ember.utils.config, "load_dotenv", lambda **_: None)
    monkeypatch.delenv("EMBER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="EMBER_API_KEY"):
        ember.download_electricity_demand_per_capita()

    assert fake_downloads.requests == []

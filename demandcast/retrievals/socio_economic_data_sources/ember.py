"""
License: AGPL-3.0.

Description:

    This module is used to download historical electricity demand per
    capita data from Ember, in kWh, from the yearly electricity demand
    of its API, which needs a free API key in EMBER_API_KEY.

    Source: https://ember-energy.org/data/yearly-electricity-data/
    API: https://api.ember-energy.org/v1/docs
"""

import logging

import pandas as pd

import utils.config
import utils.fetcher

# The yearly electricity demand of the API of Ember.
API_URL = "https://api.ember-energy.org/v1/electricity-demand/yearly"


def download_electricity_demand_per_capita() -> pd.DataFrame:
    """
    Download historical electricity demand per capita from Ember.

    Returns
    -------
    electricity_demand_per_capita : pandas.DataFrame
        The electricity demand per capita in kWh, by country code (rows)
        and year (columns).
    """
    logging.info("Downloading electricity demand per capita data from Ember.")

    # Download the yearly demand of the countries, without the regions
    # that aggregate them.
    response = utils.fetcher.fetch_response(
        API_URL,
        timeout=120,
        request_params={
            "is_aggregate_entity": "false",
            "api_key": utils.config.read_api_key("EMBER_API_KEY", "Ember"),
        },
    )
    records = pd.DataFrame(response.json()["data"])

    # Pivot the table to have years as columns and country codes as
    # index.
    electricity_demand_per_capita = records.pivot_table(
        index="entity_code", columns="date", values="demand_kwh_per_capita"
    )
    electricity_demand_per_capita.columns = (
        electricity_demand_per_capita.columns.astype(int)
    )
    electricity_demand_per_capita.index = (
        electricity_demand_per_capita.index.astype(str)
    )
    electricity_demand_per_capita = electricity_demand_per_capita.astype(float)
    electricity_demand_per_capita.index.name = "Country Code"
    electricity_demand_per_capita.columns.name = "Year"

    # Remove rows with all NaN values.
    electricity_demand_per_capita = electricity_demand_per_capita.dropna(
        how="all"
    )

    logging.info(
        "Electricity demand per capita data from Ember has been downloaded "
        "successfully."
    )

    return electricity_demand_per_capita

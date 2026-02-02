# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module is used to download historical electricity demand per
    capita data from Ember. The unit is MWh and it is converted to kWh.

    Source: https://ember-energy.org/data/yearly-electricity-data/
"""

import logging

import pandas


def download_electricity_demand_per_capita() -> pandas.DataFrame:
    """
    Download historical electricity demand per capita from Ember.

    Returns
    -------
    electricity_demand_per_capita : pandas.DataFrame
        The electricity demand per capita data from Ember.
    """
    logging.info("Downloading electricity demand per capita data from Ember.")

    # Download the electricity demand dataset from Ember.
    electricity_dataset = pandas.read_csv(
        "https://storage.googleapis.com/emb-prod-bkt-publicdata/public-downloads/yearly_full_release_long_format.csv"  # noqa: W505
    )

    # Extract the electricity demand per capita data.
    electricity_demand_per_capita = electricity_dataset[
        electricity_dataset["Variable"] == "Demand per capita"
    ]

    # Pivot the table to have years as columns and country codes as
    # index.
    electricity_demand_per_capita = electricity_demand_per_capita.pivot_table(
        index=["ISO 3 code"], columns="Year", values="Value"
    )

    # Convert to the correct data types.
    electricity_demand_per_capita.columns = (
        electricity_demand_per_capita.columns.astype(int)
    )
    electricity_demand_per_capita.index = (
        electricity_demand_per_capita.index.astype(str)
    )
    electricity_demand_per_capita = electricity_demand_per_capita.astype(float)

    # Rename the index and columns.
    electricity_demand_per_capita.index.name = "Country Code"
    electricity_demand_per_capita.columns.name = "Year"

    # Remove rows with all NaN values.
    electricity_demand_per_capita = electricity_demand_per_capita.dropna(
        how="all"
    )

    # Convert MWh to kWh.
    electricity_demand_per_capita = electricity_demand_per_capita * 1000

    logging.info(
        "Electricity demand per capita data from Ember has been downloaded "
        "successfully."
    )

    return electricity_demand_per_capita

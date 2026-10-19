"""
License: AGPL-3.0.

Description:

    This module cleans the processed electricity demand of a data source
    for a country or subdivision, and saves it in the folder of cleaned
    electricity demand. The processed data is in MW, at the ends of the
    intervals of the data source in UTC, without missing or zero values
    or duplicated times, at the resolution of the data source.

    For now, the cleaning only resamples the data to hourly values: the
    average of the values in each hour, at its end. The removal of
    spikes and of duplicated or unreasonable values will come before it.
"""

import logging
import os

import pandas as pd
import utils.config


def clean_data(code: str, data_source: str) -> pd.Series:
    """
    Clean and save the processed electricity demand of a data source.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.

    Returns
    -------
    pandas.Series
        The hourly electricity demand in MW, at the ends of the hours in
        UTC.
    """
    processed = pd.read_parquet(
        utils.config.get_electricity_demand_file_path(
            "processed", code, data_source
        )
    )["Load (MW)"]

    # Average the values of each hour, at its end.
    cleaned = (
        processed.resample("1h", label="right", closed="right").mean().dropna()
    )
    cleaned.index.name = processed.index.name
    cleaned.name = processed.name

    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, data_source
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    cleaned.to_frame().to_parquet(file_path)
    logging.info(f"Saved the cleaned electricity demand to {file_path}.")

    return cleaned

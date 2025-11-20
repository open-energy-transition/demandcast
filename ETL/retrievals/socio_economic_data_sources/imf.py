# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module is used to download historical GDP PPP per capita data
    from the International Monetary Fund (IMF). The unit is 2021
    international dollars.

    Source: https://data.imf.org/en/Data-Explorer?datasetUrn=IMF.RES:WEO(6.0.0)&INDICATOR=NGDPRPPPPC
"""  # noqa: W505

import logging

import pandas
import sdmx


def download_gdp_ppp_per_capita() -> pandas.DataFrame:
    """
    Download historical GDP PPP per capita data from the IMF.

    Returns
    -------
    pandas.DataFrame
        The historical GDP PPP per capita data from the IMF.
    """
    logging.info("Downloading GDP PPP per capita data from the IMF.")

    # Initialize the IMF SDMX client.
    imf_client = sdmx.Client("IMF_DATA")

    # Download the GDP PPP per capita data from the IMF.
    imf_gdp_ppp_per_capita = imf_client.data("WEO", key="*.NGDPRPPPPC.A")

    # Convert the data to a pandas DataFrame.
    imf_gdp_ppp_per_capita = sdmx.to_pandas(imf_gdp_ppp_per_capita)

    # Reshape the DataFrame, drop NaN values, and set the index to
    # the country code.
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.reset_index(
        name="value"
    ).pivot_table(
        index="COUNTRY",
        columns="TIME_PERIOD",
        values="value",
    )

    # Convert to the correct data types.
    imf_gdp_ppp_per_capita.columns = imf_gdp_ppp_per_capita.columns.astype(int)
    imf_gdp_ppp_per_capita.index = imf_gdp_ppp_per_capita.index.astype(str)
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.astype(float)

    # Rename the index and columns.
    imf_gdp_ppp_per_capita.index.name = "Country Code"
    imf_gdp_ppp_per_capita.columns.name = "Year"

    # Remove rows with all NaN values.
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.dropna(how="all")

    # Remove rows with country codes that are not three letters long.
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita[
        imf_gdp_ppp_per_capita.index.str.len() == 3
    ]

    logging.info(
        "GDP PPP per capita data from the IMF has been downloaded "
        "successfully."
    )

    return imf_gdp_ppp_per_capita

"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    GDP PPP per capita data from the World Bank and the International
    Monetary Fund (IMF), as well as to calculate future GDP PPP per
    capita based on growth rates from the IAMC scenarios. The data is
    extracted for specified countries and subdivisions and saved into
    CSV and Parquet files.
"""

from typing import cast

import cpi
import pandas as pd
import utils.catalogue
import utils.scenarios

import retrievals.gridded_totals
import retrievals.indicators
from retrievals.socio_economic_data_sources import iiasa, imf, world_bank


def get_historical_data() -> pd.DataFrame:
    """
    Get the historical GDP PPP per capita data.

    This function downloads the historical GDP PPP per capita data
    from the World Bank and the IMF, merges them, and returns the
    combined DataFrame.

    Returns
    -------
    pandas.DataFrame
        The historical GDP PPP per capita data.
    """
    # Download the historical GDP PPP per capita from the World Bank.
    world_bank_gdp_ppp_per_capita = world_bank.download("gdp_ppp_per_capita")

    # Download the historical GDP PPP per capita from the IMF.
    imf_gdp_ppp_per_capita = imf.download_gdp_ppp_per_capita()

    # Merge the two datasets by averaging them.
    gdp_ppp_per_capita = (
        world_bank_gdp_ppp_per_capita + imf_gdp_ppp_per_capita
    ) / 2

    # Limit the data up to the year before the current year.
    gdp_ppp_per_capita = gdp_ppp_per_capita.loc[
        :, : pd.Timestamp.now().year - 1
    ]

    # Where the combined DataFrame is NaN because one of the datasets is
    # missing, use the other dataset.
    return gdp_ppp_per_capita.fillna(world_bank_gdp_ppp_per_capita).fillna(
        imf_gdp_ppp_per_capita
    )


def _get_gdp_ppp_per_capita_from_gridded_data(
    code: str,
    selected_years: list[int],
    available_years_of_gridded_data: list[int],
    last_available_historical_years_of_gridded_data: int | None = None,
    scenario: str | None = None,
) -> pd.Series:
    """
    Get the GDP PPP per capita by aggregating gridded data.

    This function calculates the GDP PPP per capita for a given country
    or subdivision by aggregating gridded GDP PPP and population data.
    The GDP PPP per capita is calculated as the total GDP PPP divided
    by the total population for the specified years.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    selected_years : list[int]
        The years for which the GDP PPP per capita is to be calculated.
    available_years_of_gridded_data : list[int]
        The years for which gridded GDP PPP and population data are
        available.
    last_available_historical_years_of_gridded_data :
        int | None, optional
        The last available historical year for gridded data.
    scenario : str | None, optional
        The scenario for which the GDP PPP per capita is to be
        calculated. If None, historical data is used.

    Returns
    -------
    pandas.Series
        The GDP PPP per capita for the specified years.
    """
    # Get the total GDP PPP from gridded data.
    gdp_ppp = retrievals.gridded_totals.get_total_value_from_gridded_data(
        "gdp_ppp",
        code,
        selected_years,
        available_years_of_gridded_data,
        last_available_historical_years_of_gridded_data,
        scenario,
    )

    # Convert GDP PPP, which is in constant 2005 international $, to
    # constant 2021 international $, which is the unit used by the World
    # Bank and the IMF.
    gdp_ppp = gdp_ppp.apply(lambda x: cpi.inflate(x, 2005, to=2021))

    # Get the total population from gridded data.
    population = retrievals.gridded_totals.get_total_value_from_gridded_data(
        "population",
        code,
        selected_years,
        available_years_of_gridded_data,
        last_available_historical_years_of_gridded_data,
        scenario,
    )

    # Calculate the GDP PPP per capita.
    return gdp_ppp / population


def _extract_historical_gdp_ppp_per_capita(
    code: str,
    iso_alpha_3_code: str,
    global_historical_gdp_ppp_per_capita: pd.DataFrame,
    requested_historical_years: list[int],
    used_historical_years: list[int],
    available_historical_years_of_gridded_data: list[int],
) -> pd.Series:
    """
    Extract the historical GDP PPP per capita for a country.

    This function extracts the historical GDP PPP per capita for a
    given country from the global historical GDP PPP per capita data.
    If the country is not found in the global data, it calculates the
    GDP PPP per capita by aggregating gridded data.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country itself or the country to
        which the subdivision belongs.
    global_historical_gdp_ppp_per_capita : pandas.DataFrame
        The global historical GDP PPP per capita data.
    requested_historical_years : list[int]
        The historical years requested for the retrieval.
    used_historical_years : list[int]
        The available historical years whose data is used for the
        requested years.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.

    Returns
    -------
    pandas.Series
        The historical GDP PPP per capita for the country.
    """
    # Check if the ISO Alpha-3 code is in the historical
    # GDP PPP per capita data.
    if iso_alpha_3_code in global_historical_gdp_ppp_per_capita.index:
        # Get the historical GDP PPP per capita for the
        # country of interest.
        historical_gdp_ppp_per_capita = cast(
            pd.Series,
            global_historical_gdp_ppp_per_capita.loc[iso_alpha_3_code],
        ).dropna()
    else:
        # Interpolate the historical GDP PPP per capita from
        # gridded data.
        historical_gdp_ppp_per_capita = (
            _get_gdp_ppp_per_capita_from_gridded_data(
                code,
                used_historical_years,
                available_historical_years_of_gridded_data,
            )
        )

    # Map the requested historical years to the used (available)
    # historical years. This is used when the requested years are not
    # all available in the historical data.
    return (
        historical_gdp_ppp_per_capita.reindex(used_historical_years)
    ).set_axis(
        requested_historical_years,
    )


def _extract_future_gdp_ppp_per_capita(
    code: str,
    iso_alpha_3_code: str,
    global_future_gdp_ppp_per_capita: pd.DataFrame,
    future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    available_historical_years_of_gridded_data: list[int],
    scenario: str,
) -> pd.Series:
    """
    Extract the future GDP PPP per capita for a country.

    This function extracts the future GDP PPP per capita for a given
    country and scenario from the global future GDP PPP per capita data.
    If the country is not found in the global data, it calculates the
    GDP PPP per capita by aggregating gridded data.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country itself or the country to
        which the subdivision belongs.
    global_future_gdp_ppp_per_capita : pandas.DataFrame
        The global future GDP PPP per capita data.
    future_years : list[int]
        The future years of interest.
    available_future_years_of_gridded_data : list[int]
        The available future years for gridded data.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.
    scenario : str
        The scenario for which the GDP PPP per capita is to be
        extracted.

    Returns
    -------
    pandas.Series
        The future GDP PPP per capita for the country.
    """
    # Check if the ISO Alpha-3 code is in the future
    # GDP PPP per capita data.
    if iso_alpha_3_code in global_future_gdp_ppp_per_capita.index:
        # Get the future GDP PPP per capita for the country and scenario
        # of interest.
        future_gdp_ppp_per_capita = iiasa.extract_and_interpolate(
            global_future_gdp_ppp_per_capita,
            iso_alpha_3_code,
            scenario,
        )
    else:
        # Extract the future GDP PPP per capita by aggregating gridded
        # data.
        future_gdp_ppp_per_capita = _get_gdp_ppp_per_capita_from_gridded_data(
            code,
            future_years,
            available_future_years_of_gridded_data,
            available_historical_years_of_gridded_data[-1],
            scenario,
        )

    return future_gdp_ppp_per_capita


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract GDP PPP per capita data.

    This function downloads and extracts historical GDP PPP per capita
    data from the World Bank and calculates future GDP PPP per capita
    based on growth rates from the IAMC scenarios. The data is
    extracted for the countries and subdivisions of interest and saved
    into CSV and Parquet files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the GDP PPP per capita data to be retrieved.
    start_year : int | None
        The start year of the range of GDP PPP per capita data to be
        retrieved.
    end_year : int | None
        The end year of the range of GDP PPP per capita data to be
        retrieved.
    scenario : str | None
        The scenario of the GDP PPP per capita data to be retrieved.
    """
    # Get the historical GDP PPP per capita.
    global_historical_gdp_ppp_per_capita = get_historical_data()

    # Read the future GDP PPP per capita data.
    global_future_gdp_ppp_per_capita = iiasa.read("gdp_ppp_per_capita")

    # Define the available years for gridded GDP PPP and population
    # data.
    available_historical_years_of_gridded_data = list(
        utils.catalogue.GRIDDED_POPULATION_YEARS
    )
    available_future_years_of_gridded_data = list(
        utils.catalogue.PROJECTION_YEARS
    )

    def get_request(entity_code: str) -> retrievals.indicators.Request:
        """
        Get the years and scenarios of a country or subdivision.

        A subdivision has the data of its country, if there is one.

        Parameters
        ----------
        entity_code : str
            The code of the country or subdivision.

        Returns
        -------
        retrievals.indicators.Request
            The request.
        """
        # Get the ISO Alpha-3 code of the country itself or the country
        # to which the subdivision belongs.
        iso_alpha_3_code = entity_code.split("_", maxsplit=1)[0]
        (
            requested_historical_years,
            used_historical_years,
            future_years,
            scenarios,
        ) = utils.scenarios.get_years_and_scenarios(
            iso_alpha_3_code,
            year,
            start_year,
            end_year,
            scenario,
            list(utils.catalogue.SSP_SCENARIOS),
            global_historical_gdp_ppp_per_capita,
            available_historical_years_of_gridded_data,
        )
        return retrievals.indicators.Request(
            historical_years=requested_historical_years,
            future_years=future_years,
            scenarios=scenarios,
            get_historical_values=lambda: (
                _extract_historical_gdp_ppp_per_capita(
                    entity_code,
                    iso_alpha_3_code,
                    global_historical_gdp_ppp_per_capita,
                    requested_historical_years,
                    used_historical_years,
                    available_historical_years_of_gridded_data,
                )
            ),
            get_future_values=lambda selected_scenario: (
                _extract_future_gdp_ppp_per_capita(
                    entity_code,
                    iso_alpha_3_code,
                    global_future_gdp_ppp_per_capita,
                    future_years,
                    available_future_years_of_gridded_data,
                    available_historical_years_of_gridded_data,
                    selected_scenario,
                )
            ),
        )

    retrievals.indicators.run_retrieval(
        "gdp_ppp_per_capita",
        "GDP PPP per capita (2021 international $)",
        "GDP PPP per capita",
        code,
        file,
        get_request,
    )

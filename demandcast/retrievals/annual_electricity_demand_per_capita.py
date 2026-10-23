"""
License: AGPL-3.0.

Description:

    This module includes functions to download and extract historical
    annual electricity demand per capita data from Ember and the World
    Bank, and to calculate future annual electricity demand per capita
    based on growth rates from the IAMC scenarios. The electricity
    demand data is extracted for the countries and subdivisions of
    interest and saved into CSV and Parquet files.

    The two historical sources define the demand differently. The
    demand of Ember is the electricity generated and imported, less the
    exports: the electricity supplied, with the losses of the networks,
    and with the generation that is not on the networks of the system
    operators, such as rooftop solar and the plants of industries for
    their own use. The electric power consumption of the World Bank
    (EG.USE.ELEC.KH.PC, from the IEA) is the production of the power
    plants less the losses of transmission, distribution and
    transformation and the own use of the plants: the consumption of
    the consumers. Ember is 12% higher in the median country, from 1% to
    5% where the losses are small, such as in Korea or Chile, to 15% to
    21% where they are large, such as in South Africa, Pakistan or
    Algeria. The hourly demand of the system operators includes the
    losses of their networks, but not the generation that is not on
    them: in the median national series, its yearly demand is 0.94
    times that of Ember and 1.05 times that of the World Bank, and it
    gets closer to Ember as the embedded generation is added to it for
    the gross demand that DemandCast models. The two sources are not
    averaged, since an average of their definitions would jump where
    one of them is missing. Ember, which counts the demand whatever
    supplies it, gives the value, and the World Bank fills the
    countries and years that Ember does not have
    (before 2000, and about 46 countries), times the ratio of Ember to
    the World Bank of the country in the years that both have, or the
    median of these ratios for a country without enough such years.

    The growth rates of the scenarios are those of the final energy of
    electricity per capita (Final Energy|Electricity per capita), which
    leaves out the losses as the World Bank does, so their projections
    from the demand of Ember assume that the share of the losses stays
    the same.
"""

from typing import cast

import numpy as np
import pandas as pd
import utils.catalogue
import utils.scenarios

import retrievals.indicators
from retrievals.socio_economic_data_sources import ember, iiasa, world_bank

# The years that Ember and the World Bank both need for the ratio of a
# country.
MIN_YEARS_OF_BOTH = 3


def get_historical_data() -> pd.DataFrame:
    """
    Get historical electricity demand per capita data.

    The demand per capita of Ember is completed by that of the World
    Bank, times the ratio of Ember to the World Bank of each country,
    since the World Bank leaves out the losses of the networks.

    Returns
    -------
    pandas.DataFrame
        The historical electricity demand per capita data in kWh, by
        country code (rows) and year (columns).
    """
    # Download the electricity demand per capita from Ember.
    ember_electricity_demand_per_capita = (
        ember.download_electricity_demand_per_capita()
    )

    # Download the electricity demand per capita from the World Bank.
    world_bank_electricity_demand_per_capita = world_bank.download(
        "electricity_demand_per_capita"
    )

    # The ratio of Ember to the World Bank of each country, the median
    # of the years that both have, if there are enough of them, or the
    # median of the countries.
    ratios = (
        ember_electricity_demand_per_capita
        / world_bank_electricity_demand_per_capita
    ).replace([np.inf, -np.inf], np.nan)
    country_ratios = ratios.median(axis=1).where(
        ratios.count(axis=1) >= MIN_YEARS_OF_BOTH
    )
    country_ratios = country_ratios.reindex(
        world_bank_electricity_demand_per_capita.index
    ).fillna(country_ratios.median())

    # Fill the countries and years that Ember does not have with the
    # World Bank, scaled to Ember.
    return ember_electricity_demand_per_capita.combine_first(
        world_bank_electricity_demand_per_capita.mul(country_ratios, axis=0)
    )


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract annual electricity demand per capita.

    This function downloads historical electricity demand per capita
    data from Ember and the World Bank, extracts the electricity data
    for the countries and subdivisions of interest, calculates future
    electricity demand per capita based on growth rates from the IAMC
    scenarios, and saves it into CSV and Parquet files.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the electricity demand per capita data to be
        retrieved.
    start_year : int | None
        The start year of the range of electricity demand per capita
        data to be retrieved.
    end_year : int | None
        The end year of the range of electricity demand per capita
        data to be retrieved.
    scenario : str | None
        The scenario of the electricity demand per capita data to be
        retrieved.
    """
    # Download the historical electricity demand per capita data.
    global_historical_electricity_demand_per_capita = get_historical_data()

    # Read the growth rates of future electricity demand per capita.
    global_future_electricity_demand_per_capita_growth_rates = iiasa.read(
        "annual_electricity_demand_per_capita"
    )

    def get_request(entity_code: str) -> retrievals.indicators.Request:
        """
        Get the years and scenarios of a country or subdivision.

        A subdivision has the data of its country. The projections
        start after the last historical year of the country, from its
        value.

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

        # Extract the electricity data for the country.
        historical_electricity_demand_per_capita = cast(
            pd.Series,
            global_historical_electricity_demand_per_capita.loc[
                iso_alpha_3_code
            ],
        ).dropna()

        # Get the years of available historical and future data.
        available_historical_years = (
            historical_electricity_demand_per_capita.index.tolist()
        )
        last_historical_year = max(available_historical_years)
        available_future_years = list(
            range(
                last_historical_year + 1,
                utils.catalogue.LAST_PROJECTION_YEAR + 1,
            )
        )

        # Get the list of year and scenario combinations.
        year_scenario_list = (
            utils.scenarios.get_year_and_scenario_combinations(
                year,
                start_year,
                end_year,
                available_historical_years,
                available_future_years,
                scenario,
                list(utils.catalogue.IAMC_SCENARIOS),
            )
        )

        return retrievals.indicators.Request(
            historical_years=list(
                {
                    year
                    for year, scenario in year_scenario_list
                    if scenario is None
                }
            ),
            future_years=list(
                {
                    year
                    for year, scenario in year_scenario_list
                    if scenario is not None
                }
            ),
            scenarios=list(
                {
                    scenario
                    for __, scenario in year_scenario_list
                    if scenario is not None
                }
            ),
            get_historical_values=lambda: (
                historical_electricity_demand_per_capita
            ),
            get_future_values=lambda selected_scenario: iiasa.extrapolate(
                global_future_electricity_demand_per_capita_growth_rates,
                iso_alpha_3_code,
                selected_scenario,
                historical_electricity_demand_per_capita.loc[
                    last_historical_year
                ],
                last_historical_year,
                available_future_years,
            ),
        )

    retrievals.indicators.run_retrieval(
        "annual_electricity_demand_per_capita",
        "Annual electricity demand per capita (kWh)",
        "annual electricity demand per capita",
        code,
        file,
        get_request,
    )

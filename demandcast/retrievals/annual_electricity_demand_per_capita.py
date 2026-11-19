"""
License: AGPL-3.0.

Description:

    This module downloads the historical annual electricity demand per
    capita of Ember and the World Bank, projects it with the growth
    rates of the IAMC scenarios of IIASA, and saves the values of the
    countries and subdivisions of interest into Parquet files. A
    subdivision has the electricity demand per capita of its country.

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
    the gross demand that DemandCast models.

    The growth rates of the scenarios are those of the final energy of
    electricity per capita (Final Energy|Electricity per capita), which
    leaves out the losses as the World Bank does, so their projections
    from the demand of Ember assume that the share of the losses stays
    the same.
"""

import logging
from typing import cast

import numpy as np
import pandas as pd

import retrievals.indicators
import utils.catalogue
import utils.scenarios
from retrievals.socio_economic_data_sources import ember, iiasa, world_bank

# The years that Ember and the World Bank both need for the ratio of a
# country.
MIN_YEARS_OF_BOTH = 3


def get_historical_data() -> pd.DataFrame:
    """
    Get historical electricity demand per capita data.

    Returns
    -------
    pandas.DataFrame
        The historical electricity demand per capita data in kWh, by
        country code (rows) and year (columns).

    Notes
    -----
    The two sources are not averaged, since an average of their
    definitions would jump where one of them is missing. Ember, which
    counts the demand whatever supplies it, gives the value, and the
    World Bank fills the countries and years that Ember does not have
    (before 2000, and about 46 countries), times the ratio of Ember to
    the World Bank of the country: the median of the years that both
    have, or the median of the countries for a country with fewer than
    MIN_YEARS_OF_BOTH such years.
    """
    ember_electricity_demand_per_capita = (
        ember.download_electricity_demand_per_capita()
    )

    world_bank_electricity_demand_per_capita = world_bank.download(
        "electricity_demand_per_capita"
    )

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
    global_historical_electricity_demand_per_capita = get_historical_data()

    global_future_electricity_demand_per_capita_growth_rates = iiasa.read(
        "annual_electricity_demand_per_capita"
    )

    def get_request(entity_code: str) -> retrievals.indicators.Request:
        """
        Get the years and scenarios of a country or subdivision.

        A subdivision has the data of its country. A year without data
        between two years with data takes the value of the year before
        it, with a warning. The projections start after the last
        historical year of the country, from its value.

        Parameters
        ----------
        entity_code : str
            The code of the country or subdivision.

        Returns
        -------
        retrievals.indicators.Request
            The request.
        """
        iso_alpha_3_code = entity_code.split("_", maxsplit=1)[0]

        with_data = cast(
            pd.Series,
            global_historical_electricity_demand_per_capita.loc[
                iso_alpha_3_code
            ],
        ).dropna()

        historical_electricity_demand_per_capita = with_data.reindex(
            range(int(with_data.index.min()), int(with_data.index.max()) + 1)
        ).ffill()
        gap_years = sorted(
            set(historical_electricity_demand_per_capita.index)
            - set(with_data.index)
        )
        if gap_years:
            logging.warning(
                "The annual electricity demand per capita of "
                f"{iso_alpha_3_code} has no value in {gap_years}, which "
                "take the value of the year before them with data."
            )

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

        year_model_scenario_list = (
            utils.scenarios.get_year_model_and_scenario_combinations(
                year,
                start_year,
                end_year,
                available_historical_years,
                available_future_years,
                None,
                scenario,
                list(utils.catalogue.IAMC_SCENARIOS),
            )
        )

        return retrievals.indicators.Request(
            historical_years=list(
                {
                    year
                    for year, __, scenario in year_model_scenario_list
                    if scenario is None
                }
            ),
            future_years=list(
                {
                    year
                    for year, __, scenario in year_model_scenario_list
                    if scenario is not None
                }
            ),
            scenarios=list(
                {
                    scenario
                    for _year, _model, scenario in year_model_scenario_list
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

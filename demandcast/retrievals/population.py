"""
License: AGPL-3.0.

Description:

    This module downloads the population of the countries, historical
    from the World Bank and future from the IAMC scenarios of IIASA,
    and saves the population of the countries and subdivisions of
    interest into Parquet files.

    The population of a subdivision is its share of the population of
    its country times the population of its country, so that the
    subdivisions of a country add up to its national population. The
    share is that of the gridded population, in the shape of the
    subdivision over that of the whole country: for the past, from the
    Gridded Population of the World (version 4.11, of SEDAC), every five
    years from 2000 to 2020, with the share of 2000 before 2000 and that
    of 2020 after 2020; for the future, from the gridded population of
    the SSP scenarios. Its totals are not used: the grids of Australia
    are flat from 2000 to 2020, while its population grew by a third,
    and those of the subdivisions of Mexico grew by 43% while Mexico
    grew by 29%. The demand of Ontario since 1994 and of the regions of
    the Australian market since 1998 can then be used for training.

    A subdivision of a country without national data has its gridded
    population.
"""

import functools

import pandas as pd

import retrievals.gridded_totals
import retrievals.indicators
import utils.catalogue
import utils.scenarios
from retrievals.socio_economic_data_sources import iiasa, world_bank


@functools.cache
def _get_gridded_population(
    code: str,
    years: tuple[int, ...],
    available_years: tuple[int, ...],
    last_historical_year: int | None,
    scenario: str | None,
) -> pd.Series:
    """
    Get the gridded population of a country or subdivision.

    The totals are kept for the run of the retrieval, which clears them
    at its start: those of a country are used by each of its
    subdivisions.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    years : tuple[int, ...]
        The years of interest.
    available_years : tuple[int, ...]
        The available years of the gridded data.
    last_historical_year : int | None
        The last year of the historical gridded data, for the years of a
        scenario.
    scenario : str | None
        The scenario, for future years.

    Returns
    -------
    pandas.Series
        The population of each year, interpolated between the years of
        the gridded data.
    """
    return retrievals.gridded_totals.get_total_value_from_gridded_data(
        "population",
        code,
        list(years),
        list(available_years),
        *(() if scenario is None else (last_historical_year, scenario)),
    )


def _get_share_of_country(
    code: str,
    years: list[int],
    available_years: list[int],
    last_historical_year: int | None = None,
    scenario: str | None = None,
) -> pd.Series:
    """
    Get the share of the population of its country in a subdivision.

    Parameters
    ----------
    code : str
        The code of the subdivision.
    years : list[int]
        The years of interest.
    available_years : list[int]
        The available years of the gridded data.
    last_historical_year : int | None, optional
        The last year of the historical gridded data, for the years of a
        scenario.
    scenario : str | None, optional
        The scenario, for future years.

    Returns
    -------
    pandas.Series
        The share of each year, interpolated between the years of the
        gridded data.
    """
    totals = [
        _get_gridded_population(
            area,
            tuple(years),
            tuple(available_years),
            last_historical_year,
            scenario,
        )
        for area in (code, code.split("_", maxsplit=1)[0])
    ]
    return totals[0] / totals[1]


def _extract_historical_population(
    code: str,
    global_historical_population: pd.DataFrame,
    requested_historical_years: list[int],
    used_historical_years: list[int],
    available_historical_years_of_gridded_data: list[int],
) -> pd.Series:
    """
    Extract the historical population of a country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    global_historical_population : pandas.DataFrame
        The population of each country and year, from the World Bank.
    requested_historical_years : list[int]
        The years of interest.
    used_historical_years : list[int]
        The year of the gridded data used for each year of interest.
    available_historical_years_of_gridded_data : list[int]
        The available years of the gridded data.

    Returns
    -------
    pandas.Series
        The population of each year of interest.
    """
    if code in global_historical_population.index:
        return (
            pd.Series(global_historical_population.loc[code])
            .dropna()
            .reindex(used_historical_years)
            .set_axis(requested_historical_years)
        )

    country_code = code.split("_", maxsplit=1)[0]
    if country_code not in global_historical_population.index:
        return (
            retrievals.gridded_totals.get_total_value_from_gridded_data(
                "population",
                code,
                used_historical_years,
                available_historical_years_of_gridded_data,
            )
            .reindex(used_historical_years)
            .set_axis(requested_historical_years)
        )

    share = (
        _get_share_of_country(
            code,
            used_historical_years,
            available_historical_years_of_gridded_data,
        )
        .reindex(used_historical_years)
        .to_numpy()
    )
    national_population = (
        pd.Series(global_historical_population.loc[country_code])
        .dropna()
        .reindex(requested_historical_years, method="ffill")
    )
    return national_population * share


def _extract_future_population(
    code: str,
    global_future_population: pd.DataFrame,
    future_years: list[int],
    available_future_years_of_gridded_data: list[int],
    available_historical_years_of_gridded_data: list[int],
    scenario: str,
) -> pd.Series:
    """
    Extract the future population for the country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision of interest.
    global_future_population : pandas.DataFrame
        The global future population data.
    future_years : list[int]
        The future years of interest.
    available_future_years_of_gridded_data : list[int]
        The available future years for gridded data.
    available_historical_years_of_gridded_data : list[int]
        The available historical years for gridded data.
    scenario : str
        The scenario of the future population data.

    Returns
    -------
    pandas.Series
        The future population for the country or subdivision.
    """
    if code in global_future_population.index:
        return iiasa.extract_and_interpolate(
            global_future_population, code, scenario
        )

    last_historical_year = available_historical_years_of_gridded_data[-1]
    country_code = code.split("_", maxsplit=1)[0]
    if country_code not in global_future_population.index:
        return retrievals.gridded_totals.get_total_value_from_gridded_data(
            "population",
            code,
            future_years,
            available_future_years_of_gridded_data,
            last_historical_year,
            scenario,
        )

    return iiasa.extract_and_interpolate(
        global_future_population, country_code, scenario
    ) * _get_share_of_country(
        code,
        future_years,
        available_future_years_of_gridded_data,
        last_historical_year,
        scenario,
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
    Download and extract population data.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the population data to be retrieved.
    start_year : int | None
        The start year of the range of population data to be retrieved.
    end_year : int | None
        The end year of the range of population data to be retrieved.
    scenario : str | None
        The scenario of the population data to be retrieved.
    """
    _get_gridded_population.cache_clear()

    global_historical_population = world_bank.download("population")

    global_future_population = iiasa.read("population")

    available_historical_years_of_gridded_data = list(
        utils.catalogue.GRIDDED_POPULATION_YEARS
    )
    available_future_years_of_gridded_data = list(
        utils.catalogue.PROJECTION_YEARS
    )

    def get_request(entity_code: str) -> retrievals.indicators.Request:
        """
        Get the years and scenarios of a country or subdivision.

        Parameters
        ----------
        entity_code : str
            The code of the country or subdivision.

        Returns
        -------
        retrievals.indicators.Request
            The request.
        """
        (
            requested_historical_years,
            used_historical_years,
            future_years,
            scenarios,
        ) = utils.scenarios.get_years_and_scenarios(
            entity_code,
            year,
            start_year,
            end_year,
            scenario,
            list(utils.catalogue.SSP_SCENARIOS),
            global_historical_population,
            available_historical_years_of_gridded_data,
        )
        return retrievals.indicators.Request(
            historical_years=requested_historical_years,
            future_years=future_years,
            scenarios=scenarios,
            get_historical_values=lambda: _extract_historical_population(
                entity_code,
                global_historical_population,
                requested_historical_years,
                used_historical_years,
                available_historical_years_of_gridded_data,
            ),
            get_future_values=lambda selected_scenario: (
                _extract_future_population(
                    entity_code,
                    global_future_population,
                    future_years,
                    available_future_years_of_gridded_data,
                    available_historical_years_of_gridded_data,
                    selected_scenario,
                )
            ),
        )

    retrievals.indicators.run_retrieval(
        "population", "Population", "population", code, file, get_request
    )

"""
License: AGPL-3.0.

Description:

    This module checks for the availability of data for all the
    countries and subdivisions for which a shape is available. The
    following data sources are considered:
    - Historical population data from the World Bank.
    - Historical electricity demand per capita from Ember and the World
      Bank.
    - Historical GDP PPP per capita from the World Bank and the IMF.
    - Future population from the IIASA SSP database.
    - Future GDP PPP per capita from the IIASA SSP database.
    - Future electricity demand per capita from the IIASA SSP database.
    Per capita data is assumed to be equally distributed within a
    country, which means that the subdivisions of a country have the
    same per capita data as the parent country.
    If either historical or future data is not available from these
    sources, aggregation from gridded data will be considered if the
    country or subdivision is larger than 500 km2.
"""

import os
from collections.abc import Callable

import pandas as pd
import pycountry
import yaml

import retrievals.annual_electricity_demand_per_capita
import retrievals.gdp_ppp_per_capita
import utils.files
import utils.paths
import utils.shapes
from retrievals.socio_economic_data_sources import iiasa, world_bank


def _is_per_capita(variable: str) -> bool:
    """
    Tell whether an indicator is per capita.

    Parameters
    ----------
    variable : str
        The name of the indicator.

    Returns
    -------
    bool
        Whether the indicator is per capita.

    Notes
    -----
    The subdivisions of a country have its data per capita, but not its
    population.
    """
    return variable.endswith("_per_capita")


def _read_iiasa_country_codes() -> pd.DataFrame:
    """
    Read the countries of the IIASA electricity demand per capita.

    Returns
    -------
    pandas.DataFrame
        An empty DataFrame with the ISO Alpha-3 codes of the countries
        as its index.

    Notes
    -----
    The IIASA projections of electricity demand per capita are by
    region, and iam_regions_mapping.yaml maps the countries to their
    regions.
    """
    with open(
        os.path.join(
            utils.paths.RETRIEVALS_FOLDER,
            "socio_economic_data_sources",
            "iam_regions_mapping.yaml",
        ),
    ) as iiasa_mapping_file:
        iiasa_mapping = yaml.safe_load(iiasa_mapping_file)
    return pd.DataFrame(index=list(iiasa_mapping))


def _add_first_and_last_years(
    variable: str,
    data_source: pd.DataFrame,
    data_availability: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add the first and last available years for historical data.

    Parameters
    ----------
    variable : str
        The name of the variable.
    data_source : pandas.DataFrame
        The historical data source.
    data_availability : pandas.DataFrame
        The DataFrame to store the data availability.

    Returns
    -------
    data_availability : pandas.DataFrame
        The updated data availability DataFrame.

    Notes
    -----
    The subdivisions take the years of their country for the data per
    capita, and have none for the population. The years of a second
    source are appended after those of the first, such as those of the
    World Bank after those of Ember, so the first and last years are the
    smallest and largest ones.
    """
    first_years: list[int | None] = []
    last_years: list[int | None] = []

    codes_of_interest = (
        data_availability["parent_iso_alpha_3_code"].to_list()
        if _is_per_capita(variable)
        else data_availability.index.to_list()
    )

    for code in codes_of_interest:
        if "_" in code:
            # Data for subdivisions is not available from the source.
            first_years.append(None)
            last_years.append(None)
        elif not data_availability[variable].loc[code]:
            first_years.append(None)
            last_years.append(None)
        else:
            entity_data = data_source.loc[code]
            available_years = entity_data.dropna().index.tolist()

            if available_years:
                first_years.append(min(available_years))
                last_years.append(max(available_years))
            else:
                first_years.append(None)
                last_years.append(None)

    data_availability[f"{variable}_first_year"] = first_years
    data_availability[f"{variable}_last_year"] = last_years

    return data_availability


def _get_country_name(iso_alpha_3_code: str) -> str:
    """
    Get the name of a country from its ISO Alpha-3 code.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.

    Returns
    -------
    str
        The name of the country.

    Raises
    ------
    ValueError
        If the code is not a valid ISO Alpha-3 code.
    """
    country = pycountry.countries.get(alpha_3=iso_alpha_3_code)
    if country is None:
        raise ValueError(f"Unknown ISO Alpha-3 code: {iso_alpha_3_code}.")
    return country.name


def get_data_availability() -> pd.DataFrame:
    """
    Get the availability of data.

    The availability of each kind of data is checked for all countries
    and subdivisions with available shapes.

    Returns
    -------
    pandas.DataFrame
        The availability of each kind of data, with its first and last
        years, and whether the area is greater than 500 km², by code.

    Raises
    ------
    ValueError
        If an ISO Alpha-3 code for a country or subdivision with
        available shapes is not in the official list of ISO Alpha-3
        codes.

    Notes
    -----
    Kosovo, which is not formally recognized in ISO 3166, is added to
    pycountry with the code XKX.
    """
    entity_codes_with_shape = utils.shapes.get_all_codes_with_shapes()

    iso_alpha_3_codes_with_shapes = [
        code.split("_")[0] for code in entity_codes_with_shape
    ]

    if pycountry.countries.get(alpha_3="XKX") is None:
        pycountry.countries.add_entry(
            alpha_2="XK", alpha_3="XKX", name="Kosovo", numeric="926"
        )

    official_iso_alpha_3_codes = [
        country.alpha_3 for country in pycountry.countries
    ]

    for code in sorted(set(iso_alpha_3_codes_with_shapes)):
        if code not in official_iso_alpha_3_codes:
            raise ValueError(f"Code {code} with shape not in official list.")

    data_availability = pd.DataFrame(index=entity_codes_with_shape)
    data_availability.index.name = "entity_code"

    data_availability["entity_name"] = [
        f"Subdivision of {_get_country_name(code.split('_')[0])}"
        if "_" in code
        else _get_country_name(code)
        for code in data_availability.index
    ]

    data_availability["parent_iso_alpha_3_code"] = (
        iso_alpha_3_codes_with_shapes
    )

    # The data of each indicator, with the codes in its index.
    indicators: dict[str, Callable[[], pd.DataFrame]] = {
        "historical_population": lambda: world_bank.download("population"),
        "historical_electricity_demand_per_capita": (
            retrievals.annual_electricity_demand_per_capita.get_historical_data
        ),
        "historical_gdp_ppp_per_capita": (
            retrievals.gdp_ppp_per_capita.get_historical_data
        ),
        "future_population": lambda: iiasa.read("population"),
        "future_gdp_ppp_per_capita": lambda: iiasa.read("gdp_ppp_per_capita"),
        "future_electricity_demand_per_capita": _read_iiasa_country_codes,
    }
    for variable, read_data in indicators.items():
        data = read_data()
        available = data_availability["parent_iso_alpha_3_code"].isin(
            data.index
        )
        if not _is_per_capita(variable):
            available &= ~data_availability.index.str.contains("_")
        data_availability[variable] = available
        if variable.startswith("historical_"):
            data_availability = _add_first_and_last_years(
                variable, data, data_availability
            )

    data_availability["area_greater_than_500_km2"] = False

    for entity_code in data_availability.index:
        shape = utils.shapes.get_entity_shape(entity_code, make_plot=False)

        # The area in km², in an equal-area projection.
        area = (
            shape.geometry.set_crs(epsg=4326).to_crs("+proj=cea").area.sum()
            / 10**6
        )

        if area >= 500:
            data_availability.loc[entity_code, "area_greater_than_500_km2"] = (
                True
            )

    return data_availability.drop(columns=["parent_iso_alpha_3_code"])


def run_check() -> None:
    """
    Check for the availability of data and save its summary.

    The summary, data_availability_summary.csv in the folder of the
    checks of the code, is an input of utils.availability, which reads
    the codes that have all the data from it.
    """
    data_availability = get_data_availability()
    with utils.files.writing(
        utils.paths.get_availability_summary_file()
    ) as temporary_path:
        data_availability.to_csv(temporary_path)

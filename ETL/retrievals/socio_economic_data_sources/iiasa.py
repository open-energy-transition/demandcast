# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module is used to read Excel files already downloaded from the
    Shared Socioeconomic Pathways (SSP) database of the International
    Institute for Applied Systems Analysis (IIASA). The files contain
    future projections of population, electricity demand per capita and
    GDP PPP per capita for different scenarios.

    Source: https://tntcat.iiasa.ac.at/SspDb
    Source: https://data.ece.iiasa.ac.at/ssp
"""

import logging
import os

import cpi
import pandas
import pycountry
import yaml


def _map_from_region_to_country(
    iiasa_data: pandas.DataFrame
) -> pandas.DataFrame:
    """
    Map the data of regions to countries.

    Parameters
    ----------
    iiasa_data : pandas.DataFrame
        The IIASA data.
    n_regions : int
        The number of IAM regions available.

    Returns
    -------
    pandas.DataFrame
        The IIASA data with the region codes replaced by ISO Alpha-3
        country codes.
    """
    # Define the path to the yaml file containing the mapping of ISO
    # Alpha-3 codes to IAM regions.
    iam_region_mapping = os.path.join(
        os.path.dirname(__file__), f"iam_regions_mapping.yaml"
    )

    # Read the mapping from the yaml file.
    with open(iam_region_mapping, "r", encoding="utf-8") as file:
        iso_to_region = yaml.safe_load(file)

    for iso_alpha_3_code, region_code in iso_to_region.items():
        # Get the data for the region of interest.
        iiasa_data_of_country = iiasa_data[iiasa_data["Region"] == region_code]

        # Subsitute the region code with the ISO Alpha-3 codes.
        iiasa_data_of_country = iiasa_data_of_country.replace(
            {"Region": {region_code: iso_alpha_3_code}}
        )

        # Append the data to the main dataframe.
        iiasa_data = pandas.concat(
            [iiasa_data, iiasa_data_of_country], ignore_index=True
        )

    # Drop the rows with the region codes.
    iiasa_data = iiasa_data[
        iiasa_data["Region"].isin(iso_to_region.keys())
    ].reset_index(drop=True)

    return iiasa_data


def _calculate_gdp_ppp_per_capita(
    gdp_ppp: pandas.DataFrame, population: pandas.DataFrame
) -> pandas.DataFrame:
    """
    Calculate the GDP PPP per capita from GDP PPP and population data.

    Parameters
    ----------
    gdp_ppp : pandas.DataFrame
        A DataFrame containing GDP PPP data.
    population : pandas.DataFrame
        A DataFrame containing population data.

    Returns
    -------
    gdp_ppp_per_capita : pandas.DataFrame
        A DataFrame containing the calculated GDP PPP per capita data.
    """
    # Find regions contained in both datasets.
    common_regions = sorted(
        list(set(gdp_ppp["Region"]) & set(population["Region"]))
    )

    # Filter the datasets to keep only the common regions.
    gdp_ppp = gdp_ppp[gdp_ppp["Region"].isin(common_regions)].reset_index(
        drop=True
    )
    population = population[
        population["Region"].isin(common_regions)
    ].reset_index(drop=True)

    # Define the years of interest.
    years_of_interest = [str(year) for year in range(2025, 2101, 5)]

    # Merge the two datasets on Region and Scenario.
    gdp_ppp_per_capita = pandas.merge(
        gdp_ppp,
        population,
        on=["Region", "Scenario"],
        suffixes=("_gdp", "_pop"),
    )

    # Calculate the GDP PPP per capita for each year of interest.
    for year in years_of_interest:
        gdp_ppp_per_capita[year] = (
            gdp_ppp_per_capita[f"{year}_gdp"]
            / gdp_ppp_per_capita[f"{year}_pop"]
            * 1000
        )

    # Keep only the relevant columns.
    columns_to_keep = ["Region", "Scenario"] + years_of_interest
    gdp_ppp_per_capita = gdp_ppp_per_capita[columns_to_keep].copy()

    # Add the required columns.
    gdp_ppp_per_capita["Model"] = "IIASA 2023"
    gdp_ppp_per_capita["Variable"] = "GDP|PPP per capita"
    gdp_ppp_per_capita["Unit"] = "USD_2021/yr"

    # Reorder columns.
    columns_order = [
        "Model",
        "Scenario",
        "Region",
        "Variable",
        "Unit",
    ] + years_of_interest
    gdp_ppp_per_capita = gdp_ppp_per_capita[columns_order]

    # Convert GDP PPP per capita, which is in constant 2017
    # international $, to constant 2021 international $, which is the
    # unit used by the World Bank and the IMF.
    for year in years_of_interest:
        gdp_ppp_per_capita[year] = gdp_ppp_per_capita[year].apply(
            lambda x: cpi.inflate(x, 2017, to=2021)
        )

    return gdp_ppp_per_capita


def _from_iiasa_name_to_iso_alpha_3_code(name: str) -> str:
    """
    Convert a country name to its ISO Alpha-3 code.

    Parameters
    ----------
    name : str
        The name of the country.

    Returns
    -------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.

    Raises
    ------
    ValueError
        If the country name is not found.
    Exception
        If multiple countries are found for the given name.
    """
    # Define the mapping from country names to ISO Alpha-3 codes for
    # countries not found by pycountry.
    custom_mapping = {
        "C?te d'Ivoire": "CIV",
        "Democratic Republic of the Congo": "COD",
        "Turkey": "TUR",
        "Cura?ao": "CUW",
        "R?union": "REU",
        "United States Virgin Islands": "VIR",
    }

    try:
        try:
            country = pycountry.countries.lookup(name)
            iso_alpha_3_code = country.alpha_3
        except LookupError:
            country = pycountry.countries.search_fuzzy(name)
            if len(country) > 1:
                raise Exception(
                    f"Multiple countries found for name '{name}': "
                    f"{[c.name for c in country]}"
                )
            iso_alpha_3_code = country[0].alpha_3
    except LookupError:
        if name in custom_mapping:
            iso_alpha_3_code = custom_mapping[name]
        else:
            raise ValueError(f"Country name '{name}' not found.")

    return iso_alpha_3_code


def read(variable: str) -> pandas.DataFrame:
    """
    Read the IIASA data.

    Parameters
    ----------
    variable : str
        The variable to read. It can be either
        "population", "annual_electricity_demand_per_capita" or
        "gdp_ppp_per_capita".

    Returns
    -------
    iiasa_data : pandas.DataFrame
        The IIASA data.

    Raises
    ------
    ValueError
        If the variable is not one of the expected values.
    """
    # Define the base file path.
    base_file_path = os.path.join(
        os.path.dirname(__file__),
        "manual_downloads",
    )

    if variable == "population":
        logging.info("Loading future population data from IIASA.")
        # Read the population data.
        iiasa_data = pandas.read_csv(
            os.path.join(base_file_path, "IAM_national_population.csv"),
        ).iloc[:-1, :]

        # Convert the region names to ISO Alpha-3 codes.
        for region in iiasa_data["Region"]:
            iiasa_data.loc[iiasa_data["Region"] == region, "Region"] = (
                _from_iiasa_name_to_iso_alpha_3_code(region)
            )

        # Convert population from millions to number of people.
        years_of_interest = iiasa_data.columns.astype(str).str.isdigit()
        iiasa_data.loc[:, years_of_interest] = (
            iiasa_data.loc[:, years_of_interest] * 1e6
        )

        # Change the unit.
        iiasa_data["Unit"] = "people"
    elif variable == "annual_electricity_demand_per_capita":
        logging.info(
            "Loading future electricity demand per capita growth rates from "
            "IIASA."
        )
        # Read the growth rate of the electricity demand per capita
        # data.
        iiasa_data = pandas.read_excel(
            os.path.join(
                base_file_path,
                "IAM_regional_annual_electricity_demand_per_capita_growth.xlsx",
            ),
        ).iloc[:-2, :-2]

        # Convert the region names to ISO Alpha-3 codes.
        iiasa_data = _map_from_region_to_country(iiasa_data)
    elif variable == "gdp_ppp_per_capita":
        # Define the path to the GDP PPP per capita file.
        gdp_ppp_per_capita_file_path = os.path.join(
            base_file_path, "IAM_national_gdp_ppp_per_capita.csv"
        )

        if not os.path.exists(gdp_ppp_per_capita_file_path):
            logging.info(
                "Calculating future GDP PPP per capita data from GDP PPP and "
                "population data."
            )
            # Read population and GDP PPP data.
            iiasa_population_data = pandas.read_csv(
                os.path.join(base_file_path, "IAM_national_population.csv"),
            ).iloc[:-1, :]
            iiasa_gdp_ppp_data = pandas.read_csv(
                os.path.join(base_file_path, "IAM_national_gdp_ppp.csv"),
            ).iloc[:-1, :]

            # Calculate the GDP PPP per capita.
            iiasa_data = _calculate_gdp_ppp_per_capita(
                iiasa_gdp_ppp_data,
                iiasa_population_data,
            )

            # Save the GDP PPP per capita data to a CSV file for future
            # use.
            iiasa_data.to_csv(
                os.path.join(gdp_ppp_per_capita_file_path),
                index=False,
            )
        else:
            logging.info("Loading future GDP PPP per capita data from IIASA.")
            # Read the GDP PPP per capita data.
            iiasa_data = pandas.read_csv(
                os.path.join(gdp_ppp_per_capita_file_path),
            )

        # Convert the region names to ISO Alpha-3 codes.
        for region in iiasa_data["Region"]:
            iiasa_data.loc[iiasa_data["Region"] == region, "Region"] = (
                _from_iiasa_name_to_iso_alpha_3_code(region)
            )
    else:
        raise ValueError(
            "The variable must be either "
            "'population', 'annual_electricity_demand_per_capita' or "
            "'gdp_ppp_per_capita'."
        )

    # Reset the index to be the Region column.
    iiasa_data = iiasa_data.set_index("Region")

    return iiasa_data


def _extract(
    iiasa_data: pandas.DataFrame, iso_alpha_3_code: str, scenario: str
) -> pandas.Series:
    """
    Extract the data for a given country, scenario and future years.

    Parameters
    ----------
    iiasa_data : pandas.DataFrame
        The IIASA data.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.

    Returns
    -------
    iiasa_data_of_country : pandas.Series
        The extracted data for the given country, scenario and future
        years.

    Raises
    ------
    ValueError
        If no data is found for the given country and scenario, or if
        more than one row is found.
    """
    # Extract the data for the country and scenario of interest.
    iiasa_data_of_country = iiasa_data[
        (iiasa_data.index == iso_alpha_3_code)
        & (iiasa_data["Scenario"] == scenario)
    ]

    # Check that there is only one row.
    if len(iiasa_data_of_country) != 1:
        raise ValueError(
            f"Expected one row for country {iso_alpha_3_code} and scenario "
            f"{scenario}, but got {len(iiasa_data_of_country)}."
        )

    # Convert to a Series with years as index by selecting only the
    # columns that are digits and dropping NaN values.
    iiasa_data_of_country = iiasa_data_of_country.iloc[
        0,
        iiasa_data_of_country.columns.astype(str).str.isdigit(),
    ].dropna()

    # Convert the index to integers and the values to floats.
    iiasa_data_of_country.index = iiasa_data_of_country.index.astype(int)
    iiasa_data_of_country = iiasa_data_of_country.astype(float)

    return iiasa_data_of_country


def extract_and_interpolate(
    iiasa_data: pandas.DataFrame,
    iso_alpha_3_code: str,
    scenario: str,
) -> pandas.Series:
    """
    Interpolate the data for a given country, scenario and future years.

    Parameters
    ----------
    iiasa_data : pandas.DataFrame
        The IIASA data.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.

    Returns
    -------
    interpolated_data : pandas.Series
        The interpolated data from IIASA with years as index.
    """
    # Extract the data for the country and scenario of interest.
    iiasa_data_of_country = _extract(
        iiasa_data,
        iso_alpha_3_code,
        scenario,
    )

    # Interpolate the data to get the values for the future years.
    interpolated_data = iiasa_data_of_country.reindex(
        range(
            iiasa_data_of_country.index.min(),
            iiasa_data_of_country.index.max() + 1,
        )
    ).interpolate(method="linear")

    return interpolated_data


def extrapolate(
    iiasa_data: pandas.DataFrame,
    iso_alpha_3_code: str,
    scenario: str,
    last_historical_value: float,
    last_historical_year: int,
    future_years: list[int],
) -> pandas.Series:
    """
    Extrapolate the data for a given country, scenario and future years.

    Future data is extrapolated based on growth rates. The function
    first looks for the growth rates corresponding to the country and
    scenario of interest, and then applies them to the last historical
    value to obtain the future values.

    Parameters
    ----------
    iiasa_data : pandas.DataFrame
        The IIASA data.
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country of interest.
    scenario : str
        The scenario of interest.
    last_historical_value : float
        The last historical value of the variable of interest.
    last_historical_year : int
        The year of the last historical value.
    future_years : list[int]
        The list of future years where the variable of interest is to be
        projected.

    Returns
    -------
    extrapolated_data : pandas.Series
        The extrapolated future data from IIASA with years as index.
    """
    # Extract the data for the country and scenario of interest.
    iiasa_data_of_country = _extract(
        iiasa_data,
        iso_alpha_3_code,
        scenario,
    )

    # Initialize a Series to store the future values.
    extrapolated_data = pandas.Series(
        index=future_years,
        dtype=float,
    )

    # Set the previous value to the last historical value.
    previous_value = last_historical_value
    previous_year = last_historical_year

    # Calculate the future values by applying the annual growth rates to
    # the last historical value.
    for year in future_years:
        # Use the closest growth rate that is less than or equal to
        # the year.
        annual_growth_rate_of_year = iiasa_data_of_country[
            iiasa_data_of_country.index < year
        ].iloc[-1]

        # Calculate the value for the year.
        extrapolated_data[year] = previous_value * (
            1 + annual_growth_rate_of_year / 100
        ) ** (year - previous_year)

        # Update the previous value.
        previous_value = extrapolated_data[year]
        previous_year = year

    return extrapolated_data

# -*- coding: utf-8 -*-
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

import pandas
import pycountry
import retrievals.socio_economic_data_sources.ember as ember
import retrievals.socio_economic_data_sources.iiasa as iiasa
import retrievals.socio_economic_data_sources.imf as imf
import retrievals.socio_economic_data_sources.world_bank as world_bank
import utils.shapes
import yaml

# os.chdir(os.getcwd()+"/ETL")


def run_check() -> None:
    """
    Check for the availability of data.

    Check for the availability of data for all countries and
    subdivisions with available shapes. The results are saved to a
    CSV file.

    Raises
    ------
    ValueError
        If an ISO Alpha-3 code for a country or subdivision with
        available shapes is not in the official list of ISO Alpha-3
        codes.
    """
    # Get the list of countries and subdivisions with available shapes.
    entity_codes_with_shape = utils.shapes.get_all_codes_with_shapes()

    # Get the ISO Alpha-3 codes for all countries and the parent
    # countries of the subdivisions with available shapes.
    iso_alpha_3_codes_with_shapes = [
        code.split("_")[0] for code in entity_codes_with_shape
    ]

    # Add countries to pycountry that are not formally recognized.
    pycountry.countries.add_entry(
        alpha_2="XK", alpha_3="XKX", name="Kosovo", numeric="926"
    )

    # Get the list of all available ISO Alpha-3 codes.
    official_iso_alpha_3_codes = []
    for country in pycountry.countries:
        official_iso_alpha_3_codes.append(country.alpha_3)

    # Check that all ISO Alpha-3 codes for countries and subdivisions
    # with available shapes are in the official list of ISO Alpha-3
    # codes.
    for code in sorted(set(iso_alpha_3_codes_with_shapes)):
        if code not in official_iso_alpha_3_codes:
            raise ValueError(f"Code {code} with shape not in official list.")

    # Initialize a DataFrame to store the available data.
    data = pandas.DataFrame(index=entity_codes_with_shape)
    data.index.name = "entity_code"

    # Add a column with the entity names.
    data["entity_name"] = [
        f"Subdivision of {pycountry.countries.get(alpha_3=code.split('_')[0]).name}"
        if "_" in code
        else pycountry.countries.get(alpha_3=code).name
        for code in data.index
    ]

    # Add a column with the ISO Alpha-3 codes.
    data["parent_iso_alpha_3_code"] = iso_alpha_3_codes_with_shapes

    # Download the historical population data.
    world_bank_historical_population = world_bank.download("population")

    # Add a column to indicate the availability of historical population
    # data.
    data["historical_population"] = data["parent_iso_alpha_3_code"].isin(
        world_bank_historical_population.index
    ) & (~data.index.str.contains("_"))

    # Download the historical electricity demand per capita from Ember.
    ember_electricity_demand_per_capita = (
        ember.download_electricity_demand_per_capita()
    )

    # Download the historical electricity demand per capita from the
    # World Bank.
    world_bank_electricity_demand_per_capita = world_bank.download(
        "electricity_demand_per_capita"
    )

    # Add a column to indicate the availability of historical
    # electricity demand per capita data.
    data["historical_electricity_demand_per_capita"] = data[
        "parent_iso_alpha_3_code"
    ].isin(ember_electricity_demand_per_capita.index) | data[
        "parent_iso_alpha_3_code"
    ].isin(world_bank_electricity_demand_per_capita.index)

    # Download the historical GDP PPP per capita from the World Bank.
    world_bank_gdp_ppp_per_capita = world_bank.download("gdp_ppp_per_capita")

    # Download the historical GDP PPP per capita from the IMF.
    imf_gdp_ppp_per_capita = imf.download_gdp_ppp_per_capita()

    # For the IMF data, change the code for Kosovo and Palestine.
    imf_gdp_ppp_per_capita = imf_gdp_ppp_per_capita.rename(
        index={"KOS": "XKX", "WBG": "PSE"}
    )

    # Add a column to indicate the availability of historical GDP PPP
    # per capita data.
    data["historical_gdp_ppp_per_capita"] = data[
        "parent_iso_alpha_3_code"
    ].isin(world_bank_gdp_ppp_per_capita.index) | data[
        "parent_iso_alpha_3_code"
    ].isin(imf_gdp_ppp_per_capita.index)

    # Read future population from the IIASA SSP database.
    iiasa_future_population = iiasa.read("population")

    # Add a column to indicate the availability of future population
    # data.
    data["future_population"] = data["parent_iso_alpha_3_code"].isin(
        iiasa_future_population.index
    ) & (~data.index.str.contains("_"))

    # Read future GDP PPP per capita from the IIASA SSP database.
    iiasa_future_gdp_ppp_per_capita = iiasa.read("gdp_ppp_per_capita")

    # Add a column to indicate the availability of future GDP PPP per
    # capita data.
    data["future_gdp_ppp_per_capita"] = data["parent_iso_alpha_3_code"].isin(
        iiasa_future_gdp_ppp_per_capita.index
    )

    # Read codes available for future electricity demand per capita
    # projections from the IIASA SSP database.
    iiasa_future_electricity_demand_per_capita_mapping = yaml.safe_load(
        open(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "retrievals",
                "socio_economic_data_sources",
                "iam_5_regions_mapping.yaml",
            ),
            "r",
        )
    )
    iiasa_future_electricity_demand_per_capita_codes = [
        code
        for code, __ in iiasa_future_electricity_demand_per_capita_mapping.items()
    ]

    # Add a column to indicate the availability of future electricity
    # demand per capita data.
    data["future_electricity_demand_per_capita"] = data[
        "parent_iso_alpha_3_code"
    ].isin(iiasa_future_electricity_demand_per_capita_codes)

    # Initialize a column to indicate if the area of the country is
    # smaller than 500 km2.
    data["area_greater_than_500_km2"] = False

    # Loop over all countries and subdivisions to check if their area is
    # greater than 500 km2.
    for entity_code in data.index:
        # Get the shape of the country.
        shape = utils.shapes.get_entity_shape(entity_code, make_plot=False)

        # Get the area of the country in square kilometers.
        area = (
            shape.geometry.set_crs(epsg=4326).to_crs("+proj=cea").area.iloc[0]
            / 10**6
        )

        if area >= 500:
            data.loc[entity_code, "area_greater_than_500_km2"] = True

    # Drop the column with the parent ISO Alpha-3 codes.
    data = data.drop(columns=["parent_iso_alpha_3_code"])

    # Save the data to a CSV file.
    data.to_csv(
        os.path.join(
            os.path.dirname(__file__), "data_availability_summary.csv"
        )
    )

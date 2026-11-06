"""
License: AGPL-3.0.

Description:

    This module gives the ISO codes, the names and the continents of
    the countries and subdivisions, with the entities that pycountry
    and pytz do not fully recognize.
"""

import functools

import pycountry
import yaml

import utils.data_sources
import utils.paths

# Define information for entities not fully recognized in pycountry or
# pytz.
EXTRA_ENTITIES = {
    "XKX": {
        "name": "Kosovo",
        "iso_alpha_2": "XK",
        "time_zone": "Europe/Belgrade",
        "continent_code": "EU",
    },
}


def get_iso_alpha_2_code(iso_alpha_3_code: str) -> str:
    """
    Get the ISO Alpha-2 code of a country from its ISO Alpha-3 code.

    Parameters
    ----------
    iso_alpha_3_code : str
        The ISO Alpha-3 code of the country.

    Returns
    -------
    iso_alpha_2_code : str
        The ISO Alpha-2 code of the country.

    Raises
    ------
    KeyError
        If the country is not found in pycountry or in the predefined
        entities.
    """
    if iso_alpha_3_code in EXTRA_ENTITIES:
        return EXTRA_ENTITIES[iso_alpha_3_code]["iso_alpha_2"]

    country = pycountry.countries.get(alpha_3=iso_alpha_3_code)
    if country is None:
        raise KeyError(
            f"Country code {iso_alpha_3_code} is not available in pycountry."
        )

    return country.alpha_2


@functools.cache
def _read_continent_codes() -> dict[str, str]:
    """
    Read the continent codes of the countries.

    Returns
    -------
    continent_codes : dict[str, str]
        The continent code of each country, by ISO Alpha-3 code.
    """
    file_path = utils.paths.get_config_file("continents.yaml")
    with open(file_path, encoding="utf-8") as file:
        return yaml.safe_load(file)["continents"]


def get_name_from_code(code: str) -> str:  # noqa: C901
    """
    Get the name of a country or subdivision from its code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    name : str
        The name of the country or subdivision.

    Raises
    ------
    ValueError
        If the country or subdivision with the given code is not found
        in pycountry.

    Notes
    -----
    A subdivision takes its name from the yaml file of the first data
    source that has it, or else from pycountry.
    """
    # Extract the ISO Alpha-3 code from the code.
    if "_" not in code and "-" not in code:
        iso_alpha_3_code = code
    elif "_" in code:
        iso_alpha_3_code = code.split("_", maxsplit=1)[0]
    else:
        iso_alpha_3_code = code.split("-", maxsplit=1)[0]

    iso_alpha_2_code = get_iso_alpha_2_code(iso_alpha_3_code)

    if "_" not in code and "-" not in code:
        if iso_alpha_3_code in EXTRA_ENTITIES:
            name = EXTRA_ENTITIES[iso_alpha_3_code]["name"]
        else:
            name = pycountry.countries.lookup(iso_alpha_3_code).name
    else:
        data_sources = utils.data_sources.get_electricity_demand_data_sources_containing_code(
            code
        )

        if len(data_sources) > 0:
            data_source = data_sources[0]
            entities = utils.data_sources.read_entities_info(
                data_source=data_source
            )
            for entity in entities:
                if utils.data_sources.get_code_of(entity) == code.replace(
                    "-", "_"
                ):
                    name = entity["subdivision_name"]
                    break

        else:
            # Reconstruct the subdivision code of pycountry.
            if "_" in code:
                subdivision_code = iso_alpha_2_code + "-" + code.split("_")[1]
            else:
                subdivision_code = iso_alpha_2_code + "-" + code.split("-")[1]

            subdivision = pycountry.subdivisions.get(code=subdivision_code)

            # Handle if subdivision is a list or a single object.
            if isinstance(subdivision, list):
                raise ValueError(
                    "pycountry.subdivisions should not return a list."
                )
            if subdivision is None:
                raise ValueError(
                    f"Subdivision with code {subdivision_code} not found in "
                    "pycountry or any of the yaml files of the electricity "
                    "demand data sources."
                )
            name = subdivision.name

    return name


def get_continent_code(code: str) -> str:
    """
    Get the continent of a country or subdivision.

    The continent code comes from the ISO Alpha-3 code of the country,
    through config/continents.yaml and the predefined entities.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    continent_code : str
        The continent code of the country or subdivision.

    Raises
    ------
    ValueError
        If no continent code is available for the country.
    """
    # Get the ISO Alpha-3 code of the country or of the country to
    # which the subdivision belongs.
    iso_alpha_3_code = code.split("_", maxsplit=1)[0]

    continent_codes = _read_continent_codes()
    if iso_alpha_3_code in continent_codes:
        continent_code = continent_codes[iso_alpha_3_code]
    elif iso_alpha_3_code in EXTRA_ENTITIES:
        continent_code = EXTRA_ENTITIES[iso_alpha_3_code]["continent_code"]
    else:
        raise ValueError(
            f"No continent code is available for country code "
            f"{iso_alpha_3_code}."
        )

    return continent_code

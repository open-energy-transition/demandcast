"""
License: AGPL-3.0.

Description:

    This module gives the codes of the countries and subdivisions of
    interest and checks that they have the data that a step needs: the
    electricity demand, from the YAML files of the data sources, or all
    the data, from the summary of the availability of the data
    (checks/data_availability_summary.csv, written by check.py).
"""

import logging
import os

import pandas as pd

import utils.data_sources
import utils.paths


def read_codes_with_all_data() -> list[str]:
    """
    Get the codes of all countries and subdivisions with all data.

    This function retrieves the codes of all countries and
    subdivisions for which all required data for the demand forecasting
    model is available. This includes the availability of shapes,
    historical and future population data, historical and future
    electricity demand per capita, and historical and future GDP PPP per
    capita.

    Returns
    -------
    list[str]
        A list of codes of all countries and subdivisions for which all
        required data is available.
    """
    # Read the CSV file containing the available data information.
    data = pd.read_csv(
        os.path.join(
            utils.paths.CHECKS_FOLDER,
            "data_availability_summary.csv",
        ),
        index_col=0,
        na_filter=False,
    )

    # Initialize a list to store the codes.
    all_codes = []

    # Filter the data to get only the countries and subdivisions with
    # all required data available.
    for code in data.index:
        if (
            data.loc[code, "historical_population"]
            and data.loc[code, "historical_electricity_demand_per_capita"]
            and data.loc[code, "historical_gdp_ppp_per_capita"]
            and data.loc[code, "future_population"]
            and data.loc[code, "future_electricity_demand_per_capita"]
            and data.loc[code, "future_gdp_ppp_per_capita"]
        ):
            all_codes.append(code)
        elif (
            data.loc[code, "historical_electricity_demand_per_capita"]
            and data.loc[code, "future_electricity_demand_per_capita"]
            and data.loc[code, "area_greater_than_500_km2"]
        ):
            # In this case, the population and GDP PPP per capita data
            # can be estimated by aggregating gridded data.
            all_codes.append(code)

    return all_codes


def check_and_get_codes_with(  # noqa: C901
    feature: str,
    code: str | None = None,
    data_source: str | None = None,
    file_path: str | None = None,
) -> list[str]:
    """
    Check code validity (if provided) or get all available codes.

    This function checks if the code provided as an argument or the
    codes in the specified file are valid by comparing them with the
    list of available codes for which a certain feature is available.
    If no code or file path is provided, it returns all available codes
    for which the feature is available.

    Parameters
    ----------
    feature : str
        The feature of interest. Available features are
        "electricity_demand_data" and "all_data".
    code : str, optional
        The code of the country or subdivision.
    data_source : str, optional
        The name of the data source.
    file_path : str, optional
        The path to the file containing the information of the countries
        and subdivisions.

    Returns
    -------
    codes : list[str]
        The list of codes of the countries and subdivisions of interest.

    Raises
    ------
    ValueError
        If the feature is not valid, or if the code is not available,
        or if none of the codes in the file are available.
    """
    # Get the list of available countries and subdivisions according to
    # the arguments.
    if feature == "electricity_demand_data":
        if data_source is not None:
            all_codes = utils.data_sources.read_codes_in(
                data_source=data_source
            )
        else:
            all_codes = utils.data_sources.read_all_codes_with_electricity_demand_data()
    elif feature == "all_data":
        if data_source is not None:
            raise ValueError(
                "The 'all_data' feature is not associated with a data source."
            )
        all_codes = read_codes_with_all_data()
    else:
        raise ValueError(
            f"Invalid feature: {feature}. Available features are: "
            "'electricity_demand_data' and 'all_data'."
        )

    if code is not None:
        # Check if the code is available.
        if code not in all_codes:
            if data_source is not None:
                raise ValueError(
                    f"Code {code} is not available in data source "
                    f"{data_source}. Please choose one of the following: "
                    f"{', '.join(all_codes)}"
                )
            raise ValueError(
                f"Code {code} does not have {feature}. Please choose "
                f"one of the following: {', '.join(all_codes)}"
            )
        codes = [code]

    elif file_path is not None:
        # Get the list of countries and subdivisions available on the
        # specified file.
        codes = utils.data_sources.read_codes_in(file_path=file_path)

        # Initialize a list of the remaining codes.
        remaining_codes = codes.copy()

        # Check if the codes are available.
        for entity_code in codes:
            if entity_code not in all_codes:
                if data_source is not None:
                    logging.error(
                        f"Code {entity_code} is not available in data source "
                        f"{data_source}."
                    )
                else:
                    logging.error(
                        f"Code {entity_code} does not have {feature}."
                    )
                remaining_codes.remove(entity_code)

        # Check if there are any codes left.
        if len(remaining_codes) == 0:
            raise ValueError(
                "None of the codes in the file are available. Please choose "
                f"from the following: {', '.join(all_codes)}"
            )
        # If there are codes left, return them.
        codes = remaining_codes
    else:
        # If no code or file path is provided, use all available codes.
        codes = all_codes

    return codes

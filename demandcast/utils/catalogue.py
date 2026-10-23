"""
License: AGPL-3.0.

Description:

    This module is the catalogue of the scenarios, years and climate
    models of the data that DemandCast retrieves.

    The scenarios are of three kinds:

    - the Shared Socioeconomic Pathways (SSP1 to SSP5), of the
      population and GDP projections of IIASA and of the gridded
      population and GDP;
    - the IAMC scenarios of the SSP database, an SSP with a target of
      radiative forcing in W/m² times 10 (SSP2-45) or its baseline, of
      the projections of the electricity demand per capita;
    - the CMIP6 scenarios, an SSP with its radiative forcing
      (SSP2-4.5), of the projections of the climate models, which run
      only some of them.

    The year ranges are tuples, so that a caller that sorts or extends
    a list of years makes its own copy.
"""

import pandas as pd

# The Shared Socioeconomic Pathways.
SSP_SCENARIOS = ("SSP1", "SSP2", "SSP3", "SSP4", "SSP5")

# The IAMC scenarios of the electricity demand per capita.
IAMC_SCENARIOS = (
    "SSP1-Baseline",
    "SSP1-19",
    "SSP1-26",
    "SSP1-34",
    "SSP1-45",
    "SSP2-Baseline",
    "SSP2-19",
    "SSP2-26",
    "SSP2-34",
    "SSP2-45",
    "SSP2-60",
    "SSP3-Baseline",
    "SSP3-34",
    "SSP3-45",
    "SSP3-60",
    "SSP4-Baseline",
    "SSP4-26",
    "SSP4-34",
    "SSP4-45",
    "SSP4-60",
    "SSP5-Baseline",
    "SSP5-19",
    "SSP5-26",
    "SSP5-34",
    "SSP5-45",
    "SSP5-60",
)

# The CMIP6 scenarios of each climate model of the Climate Data Store,
# with the country of its institute.
CLIMATE_MODEL_SCENARIOS: dict[str, tuple[str, ...]] = {
    # China.
    "CAMS-CSM1-0": (
        "SSP1-1.9",
        "SSP1-2.6",
        "SSP2-4.5",
        "SSP3-7.0",
        "SSP5-8.5",
    ),
    # United States.
    "CESM2": ("SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"),
    # France.
    "CNRM-ESM2-1": (
        "SSP1-1.9",
        "SSP1-2.6",
        "SSP4-3.4",
        "SSP2-4.5",
        "SSP4-6.0",
        "SSP3-7.0",
        "SSP5-8.5",
    ),
    # Europe.
    "EC-Earth3-Veg-LR": (
        "SSP1-1.9",
        "SSP1-2.6",
        "SSP2-4.5",
        "SSP3-7.0",
        "SSP5-8.5",
    ),
    # United Kingdom.
    "HadGEM3-GC31-LL": ("SSP1-2.6", "SSP2-4.5", "SSP5-8.5"),
    # Japan.
    "MIROC-ES2L": ("SSP1-1.9", "SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"),
    # Germany.
    "MPI-ESM1-2-LR": ("SSP1-2.6", "SSP2-4.5", "SSP3-7.0", "SSP5-8.5"),
}

# The last year of the projections.
LAST_PROJECTION_YEAR = 2100

# The years of the SSP projections, every five years: those of IIASA
# and those of the gridded population and GDP.
PROJECTION_YEARS = tuple(range(2025, LAST_PROJECTION_YEAR + 1, 5))

# The historical years of the gridded population density of SEDAC.
GRIDDED_POPULATION_YEARS = tuple(range(2000, 2021, 5))

# The historical years of the gridded GDP of Zenodo.
GRIDDED_GDP_PPP_YEARS = tuple(range(2000, 2021))

# The first year of the reanalysis of the weather. ERA5 starts in 1940,
# but the years before 1990 are not needed.
FIRST_REANALYSIS_YEAR = 1990


def get_reanalysis_years() -> list[int]:
    """
    Get the years of the reanalysis of the weather.

    The current year, incomplete, belongs to the projections only, so
    that a year is never retrieved both ways, and the statistics of a
    year, such as its mean temperature, cover the whole year.

    Returns
    -------
    list[int]
        The years from the first one needed to the last complete one.
    """
    return list(range(FIRST_REANALYSIS_YEAR, pd.Timestamp.now().year))


def get_climate_projection_years() -> list[int]:
    """
    Get the years of the projections of the climate models.

    Returns
    -------
    list[int]
        The years from the current one to the last projection year.
    """
    return list(range(pd.Timestamp.now().year, LAST_PROJECTION_YEAR + 1))


def get_ssp(scenario: str) -> str:
    """
    Get the Shared Socioeconomic Pathway of a scenario.

    Parameters
    ----------
    scenario : str
        An IAMC or CMIP6 scenario, such as SSP2-45 or SSP2-4.5.

    Returns
    -------
    str
        The pathway, such as SSP2.

    Raises
    ------
    ValueError
        If the scenario has none of the pathways.
    """
    for ssp in SSP_SCENARIOS:
        if ssp in scenario.upper():
            return ssp
    raise ValueError(
        f"The scenario {scenario} is not valid. It must include one of "
        f"the following: {', '.join(SSP_SCENARIOS)}."
    )


def get_scenario(scenario: str, scenarios: tuple[str, ...]) -> str:
    """
    Get a scenario of a list, ignoring the case.

    Parameters
    ----------
    scenario : str
        The scenario, in any case.
    scenarios : tuple[str, ...]
        The available scenarios.

    Returns
    -------
    str
        The scenario, spelt as in the list.

    Raises
    ------
    ValueError
        If the scenario is not available.
    """
    for available_scenario in scenarios:
        if available_scenario.upper() == scenario.upper():
            return available_scenario
    raise ValueError(
        f"The scenario '{scenario}' is not available. Available "
        f"scenarios are: {list(scenarios)}."
    )


def get_climate_model_and_scenario(
    climate_model: str | None, scenario: str | None
) -> tuple[str | None, str | None]:
    """
    Get a climate model and its scenario, ignoring the case.

    Parameters
    ----------
    climate_model : str | None
        The climate model, None for all of them.
    scenario : str | None
        The scenario, None for all of those of the model.

    Returns
    -------
    tuple[str | None, str | None]
        The climate model and the scenario, spelt as in the catalogue.

    Raises
    ------
    ValueError
        If the climate model, or its scenario, is not available.
    """
    if climate_model is not None:
        models = {model.upper(): model for model in CLIMATE_MODEL_SCENARIOS}
        if climate_model.upper() not in models:
            raise ValueError(
                f"The climate model '{climate_model}' is not available. "
                f"Available models are: {list(CLIMATE_MODEL_SCENARIOS)}."
            )
        climate_model = models[climate_model.upper()]
        scenarios = CLIMATE_MODEL_SCENARIOS[climate_model]
    else:
        scenarios = tuple(
            dict.fromkeys(
                s
                for model_scenarios in CLIMATE_MODEL_SCENARIOS.values()
                for s in model_scenarios
            )
        )
    if scenario is not None:
        scenario = get_scenario(scenario, scenarios)
    return climate_model, scenario

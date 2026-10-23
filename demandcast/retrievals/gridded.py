"""
License: AGPL-3.0.

Description:

    This module runs the steps that the retrievals of gridded data
    share: the extraction of the grid of each country and subdivision
    from a global grid, and, for the gridded population and GDP, the
    loop over the years and scenarios of their global grids.

    The grid of a country or subdivision covers the bounds of its shape,
    west, south, east and north, and is saved in a NetCDF file.
"""

import logging
import os
from collections.abc import Callable
from typing import Literal

import xarray
from tqdm import tqdm

import utils.availability
import utils.catalogue
import utils.paths
import utils.scenarios
import utils.shapes

type Grid = xarray.DataArray | xarray.Dataset
type Bounds = list[float]


def extract_entity_grids(
    global_grid: Grid,
    codes: list[str],
    get_file_path: Callable[[str], str],
    description: str,
    process: Callable[[Grid, Bounds], Grid] = lambda grid, _bounds: grid,
    is_up_to_date: Callable[[str], bool] = os.path.exists,
) -> None:
    """
    Extract and save the grid of each country and subdivision.

    Parameters
    ----------
    global_grid : Grid
        The global grid, with the coordinates x and y.
    codes : list[str]
        The codes of the countries and subdivisions.
    get_file_path : Callable[[str], str]
        The function that gives the path of the file of a code.
    description : str
        The name of the data in the messages of the log.
    process : Callable[[Grid, Bounds], Grid], optional
        The function that processes the grid of a code, with its
        bounds, before it is saved. By default, the grid is saved as it
        is.
    is_up_to_date : Callable[[str], bool], optional
        The function that tells whether the file of a code can be
        kept. By default, a file that exists is kept.
    """
    for entity_code in tqdm(
        codes, desc="Countries and subdivisions", leave=False
    ):
        file_path = get_file_path(entity_code)
        if is_up_to_date(file_path):
            logging.info(
                f"The gridded {description} of {entity_code} already "
                "exists. Skipping extraction."
            )
            continue

        logging.info(f"Extracting the gridded {description} of {entity_code}.")
        bounds = utils.shapes.get_entity_bounds(
            utils.shapes.get_entity_shape(entity_code, make_plot=False)
        )  # West, South, East, North
        entity_grid = global_grid.sel(
            x=slice(bounds[0], bounds[2]), y=slice(bounds[1], bounds[3])
        )
        process(entity_grid, bounds).to_netcdf(file_path)
        logging.info(
            f"The gridded {description} of {entity_code} has been saved."
        )


def _get_file_path_function(
    variable: Literal["population", "gdp_ppp"],
    year: int,
    scenario: str | None,
) -> Callable[[str], str]:
    """
    Get the function that gives the path of the grid of a code.

    Parameters
    ----------
    variable : str
        The gridded variable, "population" or "gdp_ppp".
    year : int
        The year of the grid.
    scenario : str | None
        The scenario of the grid, none for a historical year.

    Returns
    -------
    Callable[[str], str]
        The function that gives the path of the grid of a code.
    """
    return lambda code: utils.paths.get_gridded_file(
        variable, code, year, scenario
    )


def _get_process_function(
    process: Callable[[Grid, Bounds, int], Grid], year: int
) -> Callable[[Grid, Bounds], Grid]:
    """
    Get the processing of the grid of a code in a year.

    Parameters
    ----------
    process : Callable[[Grid, Bounds, int], Grid]
        The processing of a grid, with its bounds and its year.
    year : int
        The year.

    Returns
    -------
    Callable[[Grid, Bounds], Grid]
        The processing of a grid of the year, with its bounds.
    """
    return lambda grid, bounds: process(grid, bounds, year)


def run_retrieval(
    variable: Literal["population", "gdp_ppp"],
    description: str,
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
    historical_years: tuple[int, ...],
    get_global_grid: Callable[[int, str | None], Grid],
    process: Callable[[Grid, Bounds, int], Grid],
) -> None:
    """
    Save the grids of the countries and subdivisions by year.

    The global grid of each year and scenario is read once, and the
    grids of the countries and subdivisions that are missing are
    extracted from it. The historical years have no scenario, and the
    future years, those of the SSP projections, one of the SSPs.

    Parameters
    ----------
    variable : str
        The gridded variable, "population" or "gdp_ppp".
    description : str
        The name of the data in the messages of the log.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The file path containing the codes of the countries or
        subdivisions of interest.
    year : int | None
        The year of the data to be retrieved.
    start_year : int | None
        The start year of the range of data to be retrieved.
    end_year : int | None
        The end year of the range of data to be retrieved.
    scenario : str | None
        The scenario of the data to be retrieved.
    historical_years : tuple[int, ...]
        The historical years of the global grids.
    get_global_grid : Callable[[int, str | None], Grid]
        The function that downloads, if needed, and reads the global
        grid of a year and a scenario.
    process : Callable[[Grid, Bounds, int], Grid]
        The function that processes the grid of a code, with its bounds
        and its year, before it is saved.
    """
    os.makedirs(utils.paths.get_gridded_folder(variable, "raw"), exist_ok=True)
    os.makedirs(
        utils.paths.get_gridded_folder(variable, "processed"), exist_ok=True
    )

    year_scenario_list = utils.scenarios.get_year_and_scenario_combinations(
        year,
        start_year,
        end_year,
        list(historical_years),
        list(utils.catalogue.PROJECTION_YEARS),
        scenario,
        list(utils.catalogue.SSP_SCENARIOS),
    )
    codes = utils.availability.check_and_get_codes_with(
        "historical_data", code=code, file_path=file
    )

    for selected_year, selected_scenario in tqdm(
        year_scenario_list, desc="Years and scenarios"
    ):
        logging.info(
            f"Processing the gridded {description} of {selected_year}"
            + (
                f" and scenario {selected_scenario}."
                if selected_scenario
                else "."
            )
        )
        extract_entity_grids(
            get_global_grid(selected_year, selected_scenario),
            codes,
            _get_file_path_function(
                variable, selected_year, selected_scenario
            ),
            description,
            _get_process_function(process, selected_year),
        )

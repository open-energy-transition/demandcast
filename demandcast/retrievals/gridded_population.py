"""
License: AGPL-3.0.

Description:

    This module downloads the global gridded population: the population
    density of the Gridded Population of the World (version 4.11) of
    SEDAC, every five years from 2000 to 2020, and the population count
    of each Shared Socioeconomic Pathway (SSP) from Figshare, every five
    years from 2025 to 2100. It saves the population count of each
    country and subdivision of interest, at a 0.25-degree resolution,
    into NetCDF files, and gives the population in the shape of a
    country or subdivision at the resolution of the global grids.

    Source: https://doi.org/10.7927/H49C6VHW
    Source: https://doi.org/10.6084/m9.figshare.19608594
    Source: https://doi.org/10.1038/s41597-022-01675-x
"""

import json
import logging
import os
import tempfile
import zipfile
from typing import cast

import requests
import shapely
import xarray

import retrievals.gridded
import utils.catalogue
import utils.fetcher
import utils.files
import utils.geospatial
import utils.paths
import utils.shapes

# The resolution of the global grids, in degrees.
RESOLUTION = 30 / 3600

# The number of rows of a global grid read at once for the population in
# a shape.
ROWS_PER_READ = 600

# The folders of the scenarios in their archives, when they have
# another name.
ARCHIVE_FOLDERS = {
    "SSP1": "SPP1",
    "SSP2": "SPP2",
    "SSP4": "SPP4",
    "SSP5": "SPP5",
}


def _download_historical_gridded_population_density(
    downloaded_data_directory: str, year: int
) -> None:
    """
    Download historical population density data from SEDAC.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population density data will be saved.
    year : int
        The year of the population density data to be downloaded.

    Raises
    ------
    ValueError
        If the year is not available.
    """
    if year not in utils.catalogue.GRIDDED_POPULATION_YEARS:
        raise ValueError(
            "year must be one of the available years: "
            f"{list(utils.catalogue.GRIDDED_POPULATION_YEARS)}."
        )

    file_path = os.path.join(downloaded_data_directory, f"{year}.tif")

    if not os.path.exists(file_path):
        logging.info(
            "Downloading global gridded population density data from SEDAC "
            f"for the year {year}."
        )

        url = (
            "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
            f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
        )

        response = utils.fetcher.fetch_response(url, timeout=60)

        with (
            utils.files.writing(file_path) as temporary_path,
            open(temporary_path, "wb") as file,
        ):
            file.write(response.content)

        logging.info(
            f"Global gridded population density data for the year {year} has "
            "been downloaded successfully."
        )
    else:
        logging.info(
            f"Global gridded population density data for the year {year} "
            "already exists. Skipping download."
        )


def _download_future_gridded_population(
    downloaded_data_directory: str, scenario: str
) -> None:
    """
    Download future population data from Figshare.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population data will be saved.
    scenario : str
        The scenario of the population data to be downloaded.

    Raises
    ------
    ValueError
        If the scenario is not available.

    Notes
    -----
    The archives are downloaded from the download server of Figshare,
    which its API gives as their download URL, since the links of its
    website, under figshare.com, answer scripts with a challenge for
    bots. An archive, of about 2.5 GB, is downloaded into a file in
    chunks, and extracted into a temporary folder next to the folder of
    the scenario, to which its folder is moved once complete, since the
    folder of a scenario is not downloaded again once it exists. The
    folders of SSP1, SSP2, SSP4 and SSP5 in their archives are named
    SPP1, SPP2, SPP4 and SPP5.
    """
    if scenario not in utils.catalogue.SSP_SCENARIOS:
        raise ValueError(
            "ssp must be one of the following: "
            f"{list(utils.catalogue.SSP_SCENARIOS)}."
        )

    folder_name = os.path.join(
        downloaded_data_directory,
        scenario,
    )

    if not os.path.exists(folder_name):
        logging.info(
            "Downloading global gridded population data from Figshare for "
            f"{scenario}."
        )
        match scenario:
            case "SSP1":
                url = "https://ndownloader.figshare.com/files/34829160"
            case "SSP2":
                url = "https://ndownloader.figshare.com/files/34829370"
            case "SSP3":
                url = "https://ndownloader.figshare.com/files/45894312"
            case "SSP4":
                url = "https://ndownloader.figshare.com/files/34829385"
            case "SSP5":
                url = "https://ndownloader.figshare.com/files/34829391"

        os.makedirs(downloaded_data_directory, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=downloaded_data_directory
        ) as temporary_folder:
            archive_path = os.path.join(temporary_folder, f"{scenario}.zip")
            with (
                requests.get(url, stream=True, timeout=60) as response,
                open(archive_path, "wb") as archive_file,
            ):
                response.raise_for_status()
                archive_file.writelines(
                    response.iter_content(chunk_size=1 << 20)
                )
            with zipfile.ZipFile(archive_path) as archive:
                archive.extractall(path=temporary_folder)
            os.replace(
                os.path.join(
                    temporary_folder,
                    ARCHIVE_FOLDERS.get(scenario, scenario),
                ),
                folder_name,
            )

        logging.info(
            f"Global gridded population data for {scenario} has been "
            "downloaded successfully."
        )
    else:
        logging.info(
            f"Global gridded population data for {scenario} already exists. "
            "Skipping download."
        )


def _read_population_dataset(
    downloaded_data_directory: str, year: int, scenario: str | None
) -> xarray.DataArray:
    """
    Read the global population of a year.

    The dataset is the population density of a historical year, or the
    population count of a future year.

    Parameters
    ----------
    downloaded_data_directory : str
        The directory where the population dataset is stored.
    year : int
        The year of the population dataset to be read.
    scenario : str | None
        The scenario of the population dataset to be read. If None,
        the historical population density data will be read.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year and scenario.

    Notes
    -----
    The rasters of the future population give their coordinates in
    pixels, not in degrees. Their cells are of 30 arc seconds and cover
    the longitudes from -180 to 180 and the latitudes from -72 to 84
    (their .tfw world files), so the pixels are mapped to the centers
    of the cells, half a cell inside these limits.
    """
    if scenario is None:
        file_path = os.path.join(downloaded_data_directory, f"{year}.tif")
    else:
        file_path = os.path.join(
            downloaded_data_directory,
            scenario,
            f"{scenario}_{year}.tif",
        )

    global_population_dataset = xarray.open_dataarray(
        file_path, engine="rasterio"
    )

    if scenario is not None:
        cell = 30 / 3600
        for coordinate, (lowest, highest) in (
            ("x", (-180, 180)),
            ("y", (-72, 84)),
        ):
            pixels = global_population_dataset[coordinate]
            global_population_dataset[coordinate] = (pixels - pixels.min()) / (
                pixels.max() - pixels.min()
            ) * (highest - lowest - cell) + (lowest + cell / 2)

    global_population_dataset = utils.geospatial.harmonize_coords(
        global_population_dataset
    )

    return utils.geospatial.clean_raster(
        global_population_dataset, "population"
    )


def _get_global_grid(year: int, scenario: str | None) -> xarray.DataArray:
    """
    Download, if needed, and read the global population of a year.

    Parameters
    ----------
    year : int
        The year.
    scenario : str | None
        The scenario, none for a historical year.

    Returns
    -------
    xarray.DataArray
        The population density of a historical year, or the population
        of a future year, read lazily.
    """
    raw_directory = utils.paths.get_gridded_folder("population", "raw")
    if year <= 2020:
        _download_historical_gridded_population_density(raw_directory, year)
    elif year >= 2025 and scenario is not None:
        _download_future_gridded_population(raw_directory, scenario)
    return _read_population_dataset(raw_directory, year, scenario)


def get_total_in_geometry(
    geometry: shapely.Geometry, year: int, scenario: str | None
) -> float:
    """
    Sum the population of the global grid in a shape.

    Parameters
    ----------
    geometry : shapely.Geometry
        The shape.
    year : int
        The year.
    scenario : str | None
        The scenario, none for a historical year.

    Returns
    -------
    float
        The population of the cells of the global grid whose centers are
        in the shape.

    Notes
    -----
    Each part of the shape is read in bands of ROWS_PER_READ rows of the
    grid, within its bounds and one cell around them, so that a large
    country is never read whole. A last band of one row is read with the
    band before it, since the area of a cell is computed from the
    distance between the rows.
    """
    global_grid = _get_global_grid(year, scenario)
    total = 0.0
    for part in shapely.get_parts(geometry):
        west, south, east, north = part.bounds
        window = global_grid.sel(
            x=slice(west - RESOLUTION, east + RESOLUTION),
            y=slice(south - RESOLUTION, north + RESOLUTION),
        )
        rows = window.sizes["y"]
        starts = list(range(0, rows, ROWS_PER_READ))
        if len(starts) > 1 and rows - starts[-1] < 2:
            starts.pop()
        for start, end in zip(starts, [*starts[1:], rows], strict=True):
            band = window.isel(y=slice(start, end)).load()
            if scenario is None:
                band = utils.geospatial.from_density_to_count(band)
            total += utils.geospatial.get_total_of_cells_in_shape(band, part)
    return total


def get_total_in_shape(code: str, year: int, scenario: str | None) -> float:
    """
    Get the population in the shape of a country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    year : int
        The year of the global grid.
    scenario : str | None
        The scenario of the global grid, none for a historical year.

    Returns
    -------
    float
        The population of the cells of the global grid, at its
        resolution, whose centers are in the shape.

    Notes
    -----
    At the 30 arc seconds of the grids, the people of the cells cut by
    a coast or a border are counted in the shape where they live. The
    totals of a code are kept in a JSON file of the folder of the
    totals, with the fingerprint of its shape (see
    retrievals.gridded.get_shape_fingerprint), and computed again when
    the shape changes.
    """
    folder = utils.paths.get_gridded_folder("population", "totals")
    file_path = os.path.join(folder, f"{code}.json")
    fingerprint = retrievals.gridded.get_shape_fingerprint(code)
    key = str(year) if scenario is None else f"{year}_{scenario}"
    totals: dict[str, float] = {}
    if os.path.exists(file_path):
        with open(file_path) as file:
            saved = json.load(file)
        if saved["shape"] == fingerprint:
            totals = saved["totals"]
    if key not in totals:
        totals[key] = get_total_in_geometry(
            utils.shapes.get_entity_shape(code, make_plot=False).union_all(),
            year,
            scenario,
        )
        os.makedirs(folder, exist_ok=True)
        with (
            utils.files.writing(file_path) as temporary_path,
            open(temporary_path, "w") as file,
        ):
            json.dump(
                {"shape": fingerprint, "totals": totals},
                file,
                indent=1,
                sort_keys=True,
            )
    return totals[key]


def run_data_retrieval(
    code: str | None,
    file: str | None,
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    scenario: str | None,
) -> None:
    """
    Download and extract gridded population data.

    Parameters
    ----------
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    year : int | None
        The year of the population data to be retrieved.
    start_year : int | None
        The start year of the range of population data to be retrieved.
    end_year : int | None
        The end year of the range of population data to be retrieved.
    scenario : str | None
        The scenario of the population data to be retrieved.
    """

    def process(
        population: retrievals.gridded.Grid,
        bounds: retrievals.gridded.Bounds,
        selected_year: int,
    ) -> retrievals.gridded.Grid:
        """
        Get the population count at the resolution of the weather data.

        Parameters
        ----------
        population : retrievals.gridded.Grid
            The population density of a historical year, or the
            population of a future year, of a country or subdivision.
        bounds : retrievals.gridded.Bounds
            The bounds of the country or subdivision.
        selected_year : int
            The year.

        Returns
        -------
        retrievals.gridded.Grid
            The population, at 0.25 degrees.
        """
        population = cast(xarray.DataArray, population)
        if selected_year in utils.catalogue.GRIDDED_POPULATION_YEARS:
            population = utils.geospatial.from_density_to_count(population)
        return utils.geospatial.coarsen(population, bounds)

    retrievals.gridded.run_retrieval(
        "population",
        "population",
        code,
        file,
        year,
        start_year,
        end_year,
        scenario,
        utils.catalogue.GRIDDED_POPULATION_YEARS,
        _get_global_grid,
        process,
    )

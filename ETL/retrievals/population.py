# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module downloads population density data from SEDAC
    (Socioeconomic Data and Applications Center). It then extracts the
    population density data for the countries and subdivisions of
    interest, coarsens the data to a 0.25-degree resolution, and saves
    it into NetCDF files. The country and subdivision code can be
    specified or a list can be provided as a yaml file. If no file or
    code is provided, the script will use all available codes. The year
    of the population density data can be specified as a command line
    argument.

    Source: https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/browseui/#sedac-popdensity-yeargrid5yr-v4.11/
    Source: https://doi.org/10.6084/m9.figshare.19608594
    Source: https://doi.org/10.1038/s41597-022-01675-x
"""

import io
import logging
import os
import zipfile

import requests
import utils.directories
import utils.entities
import utils.figures
import utils.geospatial
import utils.shapes
import xarray


def _get_year_and_ssp_combinations(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    ssp: int | None,
) -> list[str]:
    """
    Get the list of years and SSP combinations.

    Parameters
    ----------
    year : int | None
        The specific year for which population data is to be downloaded.
    start_year : int | None
        The start year of the range of years for which population data
        is to be downloaded.
    end_year : int | None
        The end year of the range of years for which population data is
        to be downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.

    Returns
    -------
    year_ssp : list[str]
        A list of strings representing the years and SSP combinations.
    """
    # Define the available years for the population data.
    available_years = list(range(2000, 2101, 5))

    if year is not None:
        assert start_year is None and end_year is None, (
            "If year is specified, start_year and end_year must be None."
        )
        assert year in available_years, (
            f"year must be one of the available years: {available_years}."
        )
        # Use the specified year.
        years = [year]
    elif start_year is not None and end_year is not None:
        assert start_year < end_year, "start_year must be less than end_year."
        assert start_year in available_years, (
            "start_year must be one of the available years: "
            f"{available_years}."
        )
        assert end_year in available_years, (
            f"end_year must be one of the available years: {available_years}."
        )
        # Use the range of years from start_year to end_year.
        years = [y for y in available_years if start_year <= y <= end_year]
    else:
        # Use all available years.
        years = available_years

    # Define the available SSPs.
    available_ssps = [1, 2, 3, 4, 5]

    if ssp is not None:
        assert ssp in available_ssps, (
            f"ssp must be one of the following: {available_ssps}."
        )
        # Use the specified SSP.
        ssps = [ssp]
    else:
        # Use all available SSPs.
        ssps = available_ssps

    # Create a list of year and SSP combinations.
    year_ssp_list = []
    for year in years:
        if year <= 2020:
            # For years 2000-2020, no SSP is needed.
            year_ssp_list.append(f"{year}")
        elif year >= 2025:
            # For years 2025-2100, SSP is needed.
            for ssp in ssps:
                year_ssp_list.append(f"{year}_ssp{ssp}")

    return year_ssp_list


def _download_historic_population(year: int) -> xarray.DataArray:
    """
    Download population data from SEDAC.

    Parameters
    ----------
    year : int
        The year of the population data to be downloaded.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year.
    """
    logging.info(
        f"Downloading population data from SEDAC for the year {year}."
    )

    assert year in list(range(2000, 2021, 5)), (
        "year must be one of the available years: "
        f"{list(range(2000, 2021, 5))}."
    )

    # Define the URL of the population data.
    url = (
        "https://data.ghg.center/sedac-popdensity-yeargrid5yr-v4.11/"
        f"gpw_v4_population_density_rev11_{year}_30_sec_{year}.tif"
    )

    # Download the population data.
    global_population = xarray.open_dataarray(url, engine="rasterio")

    # Harmonize the population data.
    global_population = utils.geospatial.harmonize_coords(global_population)

    # Clean the dataset.
    global_population = utils.geospatial.clean_raster(
        global_population, "population"
    )

    return global_population


def _download_future_population(year: int, ssp: str) -> xarray.DataArray:
    """
    Download future population data from Figshare.

    Parameters
    ----------
    year : int
        The year of the population data to be downloaded.
    ssp : str
        The Shared Socioeconomic Pathway (SSP) scenario.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year and SSP.
    """
    logging.info(
        "Downloading population data from Figshare for the year "
        f"{year} and {ssp.upper()}."
    )

    assert year in list(range(2025, 2101, 5)), (
        "year must be one of the available years: "
        f"{list(range(2025, 2101, 5))}."
    )
    assert ssp in ["ssp1", "ssp2", "ssp3", "ssp4", "ssp5"], (
        "ssp must be one of the following: ['ssp1', 'ssp2', 'ssp3', "
        "'ssp4', 'ssp5']."
    )

    # Define the URL of the population data.
    match ssp:
        case "ssp1":
            url = "https://figshare.com/ndownloader/files/34829160"
        case "ssp2":
            url = "https://figshare.com/ndownloader/files/34829370"
        case "ssp3":
            url = "https://figshare.com/ndownloader/files/45894312"
        case "ssp4":
            url = "https://figshare.com/ndownloader/files/34829385"
        case "ssp5":
            url = "https://figshare.com/ndownloader/files/34829391"

    # Fetch the data from the URL.
    response = requests.get(url)

    # Check if the request was successful.
    response.raise_for_status()

    return response


def _extract_future_population(
    response: requests.Response, year_ssp: str
) -> xarray.DataArray:
    """
    Extract future population data for a specific year and SSP.

    Parameters
    ----------
    response : requests.Response
        The response object containing the future population data.
    year_ssp : str
        The year and SSP combination for which population data is to be
        extracted.

    Returns
    -------
    xarray.DataArray
        The population data for the specified year and SSP.
    """
    # Extract the year and SSP from the year_ssp string.
    year, ssp = year_ssp.split("_")

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        # Find the file name that matches the year and SSP. In this way,
        # we can handle a typo in the SSP1 folder name (actually SPP1).
        file_name = [
            name
            for name in archive.namelist()
            if ssp.upper() in name and year in name and name.endswith(".tif")
        ][0]

        global_population = xarray.open_dataarray(
            archive.open(file_name),
            engine="rasterio",
        )

        # Harmonize the population data.
        global_population = utils.geospatial.harmonize_coords(
            global_population
        )

        # Clean the dataset.
        global_population = utils.geospatial.clean_raster(
            global_population, "population"
        )

        return global_population


def run_data_retrieval(
    year: int | None,
    start_year: int | None,
    end_year: int | None,
    ssp: int | None,
    code: str | None,
    file: str | None,
) -> None:
    """
    Download and extract the population data.

    This function downloads population data from SEDAC, extracts the
    population data for the countries and subdivisions of interest,
    coarsens the data to a 0.25-degree resolution, and saves it into
    NetCDF files.

    Parameters
    ----------
    year : int | None
        The year of the population data to be downloaded.
    start_year : int | None
        The start year of the range of population data to be
        downloaded.
    end_year : int | None
        The end year of the range of population data to be downloaded.
    ssp : int | None
        The Shared Socioeconomic Pathway (SSP) scenario.
    code : str | None
        The code of the country or subdivision of interest.
    file : str | None
        The path to the file containing the list of codes of the
        countries and subdivisions of interest.
    """
    # Get the directory to store the population density data.
    result_directory = utils.directories.read_folders_structure()[
        "population_folder"
    ]
    os.makedirs(result_directory, exist_ok=True)

    # Get the list of years and SSP combinations.
    year_ssp_list = _get_year_and_ssp_combinations(
        year, start_year, end_year, ssp
    )

    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes(code=code, file_path=file)

    # Loop over the years.
    for year_ssp in year_ssp_list:
        logging.info(
            f"Downloading population for the year {year_ssp.split('_')[0]}"
            + (
                f" and SSP {year_ssp.split('_ssp')[1]}."
                if "ssp" in year_ssp
                else "."
            )
        )

        if "ssp" not in year_ssp:
            # For years 2000-2020, download historic population data.
            global_population = _download_historic_population(int(year_ssp))
        else:
            # For years 2025-2100, download population data for the
            # specified SSP scenario.
            dataset_response = _download_future_population(
                int(year_ssp.split("_")[0]), year_ssp.split("_")[1]
            )

            # Extract the population data for the specified year and
            # SSP.
            global_population = _extract_future_population(
                dataset_response, year_ssp
            )

        # Loop over the countries and subdivisions of interest.
        for code in codes:
            # Define the file path of the population density data for
            # the country or subdivision.
            file_path = os.path.join(
                result_directory, f"{code}_0.25_deg_{year_ssp}.nc"
            )

            if not os.path.exists(file_path):
                logging.info(f"Extracting population density data of {code}.")

                # Get the shape of the country or subdivision.
                entity_shape = utils.shapes.get_entity_shape(
                    code, make_plot=False
                )

                # Get the lateral bounds of the country or subdivision
                # of interest.
                entity_bounds = utils.shapes.get_entity_bounds(
                    entity_shape
                )  # West, South, East, North

                # Select the population density data in the bounding box
                # of the country or subdivision of interest.
                population = global_population.sel(
                    x=slice(entity_bounds[0], entity_bounds[2]),
                    y=slice(entity_bounds[1], entity_bounds[3]),
                )

                # Coarsen the population density data to the same
                # resolution as the weather data.
                population = utils.geospatial.coarsen(
                    population, entity_bounds
                )

                # Save the population density data.
                population.to_netcdf(file_path)

                make_plot = False
                if make_plot:
                    # Make a plot of the population density data.
                    utils.figures.simple_plot(
                        population,
                        f"population_density_{code}_{year_ssp}",
                    )

                logging.info(
                    f"Population density data for {code} has been "
                    "successfully extracted and saved."
                )

            else:
                logging.info(
                    f"Population density data for {code} already exists. "
                    "Skipping extraction."
                )

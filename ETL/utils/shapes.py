# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module retrieves standard shapes of countries and subdivisions
    from the Natural Earth shapefile database. It also retrieves
    non-standard subdivision shapes from the shapes directory.
"""

import os

import cartopy.io.shapereader
import geopandas
import pandas
import pycountry
import pycountry_convert
from shapely import Polygon

import utils.directories
import utils.entities
import utils.figures


def _remove_islands(
    entity_shape: geopandas.GeoDataFrame, code: str
) -> geopandas.GeoDataFrame:
    """
    Remove small remote islands from the shape of some countries.

    This function modifies the shape of certain countries to exclude
    small remote islands that are not relevant for the analysis and
    would otherwise lead to the download of large weather datasets.

    Parameters
    ----------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the country or subdivision of interest.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the country or subdivision of interest
        without small remote islands.
    """
    new_bounds = None

    # Create a GeoSeries containing the new bounds of the country or
    # subdivision of interest.
    match code:
        case "CHL":  # Chile
            new_bounds = geopandas.GeoSeries(
                Polygon([(-80, -60), (-60, -60), (-60, 0), (-80, 0)])
            )
        case "ESP":  # Spain
            new_bounds = geopandas.GeoSeries(
                Polygon([(-10, 35), (5, 35), (5, 45), (-10, 45)])
            )
        case "FRA":  # France
            new_bounds = geopandas.GeoSeries(
                Polygon([(-5, 40), (10, 40), (10, 55), (-5, 55)])
            )
        case "NLD":  # Netherlands
            new_bounds = geopandas.GeoSeries(
                Polygon([(0, 50), (10, 50), (10, 55), (0, 55)])
            )
        case "NOR":  # Norway
            new_bounds = geopandas.GeoSeries(
                Polygon([(0, 55), (35, 55), (35, 73), (0, 73)])
            )
        case "NZL":  # New Zealand
            new_bounds = geopandas.GeoSeries(
                Polygon([(165, -50), (180, -50), (180, -30), (165, -30)])
            )
        case "PRT":  # Portugal
            new_bounds = geopandas.GeoSeries(
                Polygon([(-10, 35), (0, 35), (0, 45), (-10, 45)])
            )

    if new_bounds is not None:
        # Convert the GeoSeries to a GeoDataFrame and set the coordinate
        # reference system to EPSG 4326.
        new_bounds = geopandas.GeoDataFrame.from_features(new_bounds, crs=4326)

        # Remove any area outside the new bounds.
        entity_shape = entity_shape.overlay(new_bounds, how="intersection")

    return entity_shape


def get_standard_shape(
    code: str, remove_remote_islands: bool = True
) -> geopandas.GeoDataFrame:
    """
    Retrieve the shape of a country or subdivision.

    This function retrieves the shape of a country or subdivision from
    the Natural Earth shapefile database.

    Parameters
    ----------
    code : str
        The code of the entity (ISO Alpha-3 code or a combination of ISO
        Alpha-3 code and subdivision code).
    remove_remote_islands : bool, optional
        Whether to remove small remote islands from the shape of some
        countries.

    Returns
    -------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the shape of the country or subdivision.
    """
    # If there isn't an underscore in the code, it is the ISO Alpha-3
    # code of the country, and the entity is therefore the country.
    # If there is an underscore in the code, it is a combination of ISO
    # Alpha-3 code and subdivision code, and the entity is a subdivision
    # of the country.

    if "_" not in code:
        # Define the relevant parameters for the shapefile retrieval.
        shapefile_name = "admin_0_countries"
        main_keys = ["ISO_A3", "ISO_A3_EH"]
        secondary_keys = ["NAME", "NAME_LONG"]
        code_to_search = code
    else:
        # Define the relevant parameters for the shapefile retrieval.
        shapefile_name = "admin_1_states_provinces"
        main_keys = ["iso_3166_2"]
        secondary_keys = ["name"]

        # Split the code into ISO Alpha-3 code and subdivision code.
        iso_alpha_3_code, subdivision_code = code.split("_")

        # Get the ISO Alpha-2 code from the ISO Alpha-3 code.
        iso_alpha_2_code = pycountry_convert.country_alpha3_to_country_alpha2(
            iso_alpha_3_code
        )

        # Combine the ISO Alpha-2 code and the subdivision code to
        # match the format used in the shapefile database.
        code_to_search = f"{iso_alpha_2_code}-{subdivision_code}"

    # Load the shapefile containing the subdivision shapes from the
    # Natural Earth database.
    all_shapes = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name=shapefile_name
    )

    # Define a reader for the shapefile.
    reader = cartopy.io.shapereader.Reader(all_shapes)

    try:
        # Read the shape of the country or subdivision of interest by
        # searching for its code.
        entity_shape = [
            shape
            for shape in list(reader.records())
            if code_to_search in [shape.attributes[key] for key in main_keys]
        ][0]
    except IndexError:
        # Get the name of the country or subdivision of interest based
        # on its code.
        name_to_search = utils.entities.get_name_from_code(code)

        # Read the shape of the country or subdivision of interest by
        # searching for its name.
        entity_shape = [
            shape
            for shape in list(reader.records())
            if name_to_search
            in [shape.attributes[key] for key in secondary_keys]
        ][0]

    # Convert the shape to a GeoDataFrame.
    entity_shape = pandas.Series({"geometry": entity_shape.geometry})
    entity_shape = geopandas.GeoSeries(entity_shape)
    entity_shape = geopandas.GeoDataFrame.from_features(entity_shape, crs=4326)

    # Remove small remote islands from the shape of some countries.
    if remove_remote_islands:
        entity_shape = _remove_islands(entity_shape, code)

    return entity_shape


def _read_non_standard_shape_codes() -> dict[str, list[str]]:
    """
    Read the non-standard shapes codes from the shapes directory.

    This function reads the codes of the non-standard shapes from the
    shapes directory. Non-standard shapes are those that are not
    available in the Natural Earth shapefile database and are defined by
    the user in the shapes directory.

    Returns
    -------
    non_standard_shape_codes : dict[str, list[str]]
        Dictionary containing the non-standard shapes and their
        respective codes.
    """
    # Get the path to the shapes directory.
    shapes_directory = utils.directories.read_folders_structure()[
        "shapes_folder"
    ]

    # Create a dictionary to store the non-standard shapes and their
    # respective codes.
    non_standard_shape_codes = {}

    # Iterate over the folders in the shapes directory.
    for folder in os.listdir(shapes_directory):
        # Check if folder is a directory.
        if os.path.isdir(os.path.join(shapes_directory, folder)):
            # Define the path to the shapefile.
            shapefile_path = os.path.join(
                shapes_directory, folder, folder + ".shp"
            )

            # Read the shapefile of the subdivisions of the data source.
            entity_shapes = geopandas.read_file(shapefile_path)

            # Get the codes of the subdivisions in the shapefile.
            entity_codes = entity_shapes["code"].unique()

            # Add the non-standard shapes and their respective codes to
            # the dictionary.
            non_standard_shape_codes[folder] = list(entity_codes)

    return non_standard_shape_codes


def _get_non_standard_shape(
    code: str, data_source: str
) -> geopandas.GeoDataFrame:
    """
    Retrieve the shape of a non-standard subdivision.

    This function retrieves the shape of a non-standard subdivision from
    the shapes directory. Non-standard subdivisions are those that are
    not available in the Natural Earth shapefile database and are
    defined by the user in the shapes directory.

    Parameters
    ----------
    code : str
        The combination of ISO Alpha-3 code and subdivision code.
    data_source : str
        The data source of the subdivision shape.

    Returns
    -------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the shape of the subdivision.
    """
    # Get the path to the shapes directory.
    shapes_directory = utils.directories.read_folders_structure()[
        "shapes_folder"
    ]

    # Define the path to the shapefile based on the data source.
    shapefile_path = os.path.join(
        shapes_directory, data_source, data_source + ".shp"
    )

    # Read the shapefile of the subdivisions of the data source.
    entity_shapes = geopandas.read_file(shapefile_path)

    # Get the shape of the subdivision of interest.
    entity_shape = entity_shapes[entity_shapes["code"] == code]
    entity_shape = geopandas.GeoDataFrame.from_features(
        entity_shape["geometry"]
    )

    return entity_shape


def get_entity_shape(
    code: str, make_plot: bool = True, remove_remote_islands: bool = True
) -> geopandas.GeoDataFrame:
    """
    Get the shape of a country or subdivision of interest.

    This function retrieves the shape of a country or subdivision of
    interest based on its code. If the country or subdivision is not
    found in the Natural Earth shapefile database, it checks if it is a
    non-standard shape defined by the user in the shapes directory.

    Parameters
    ----------
    code : str
        The code of the entity (ISO Alpha-3 code or a combination of ISO
        Alpha-3 code and subdivision code).
    make_plot : bool, optional
        Whether to make a plot of the entity of interest.
    remove_remote_islands : bool, optional
        Whether to remove small remote islands from the shape of some
        countries.

    Returns
    -------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the country or subdivision of interest.
    """
    # If there isn't an underscore in the code, it is the ISO Alpha-3
    # code of the country. If there is an underscore in the code, it is
    # a combination of ISO Alpha-3 code and subdivision code.
    if "_" not in code:
        # Get the shape of the country from the Natural Earth
        # shapefile database.
        entity_shape = get_standard_shape(code, remove_remote_islands)
    else:
        # Define a flag to check if the subdivision is in the list of
        # non-standard shapes.
        is_non_standard_shape = False
        selected_data_source = ""

        # Read the codes of the non-standard shapes contained in the
        # shapes directory.
        non_standard_shape_codes = _read_non_standard_shape_codes()

        # Iterate over the codes of the non-standard shapes and check if
        # the subdivision code is in the list of non-standard shapes.
        for (
            data_source,
            codes_of_data_source,
        ) in non_standard_shape_codes.items():
            if code in codes_of_data_source:
                is_non_standard_shape = True
                selected_data_source = data_source
                break

        if is_non_standard_shape:
            # Get the shape of the subdivision from the user-defined
            # shapes in the shapes directory.
            entity_shape = _get_non_standard_shape(code, selected_data_source)
        else:
            # Get the shape of the subdivision from the Natural Earth
            # shapefile database.
            entity_shape = get_standard_shape(code, remove_remote_islands)

    # Add the code as index to the GeoDataFrame.
    entity_shape["code"] = code
    entity_shape = entity_shape.set_index("code")

    if make_plot:
        utils.figures.simple_plot(entity_shape, f"entity_shape_{code}")

    return entity_shape


def get_entity_bounds(
    entity_shape: geopandas.GeoDataFrame, target_resolution: float = 0.25
) -> list[float]:
    """
    Get the lateral bounds of the country or subdivision.

    This function retrieves the lateral bounds of a country or
    subdivision of interest. The bounds are returned as a list
    containing the western, southern, eastern, and northern bounds,
    respectively. The bounds are rounded to the closest 0.25 degree.
    One degree of buffer is added to the bounds.

    Parameters
    ----------
    entity_shape : geopandas.GeoDataFrame
        GeoDataFrame containing the country or subdivision of interest.
    target_resolution : float, optional
        The target resolution in degrees to which the bounds should be
        rounded. Default is 0.25 degrees.

    Returns
    -------
    entity_bounds : list[float]
        List containing the lateral bounds of the country or subdivision
        of interest.
    """
    # Get the lateral bounds of the country or subdivision of interest
    # including a buffer layer of one degree.
    entity_bounds = (
        entity_shape.union_all().buffer(1).bounds
    )  # West, South, East, North

    # If longitude bounds are outside the range of -180 to 180 degrees,
    # adjust them to be within this range.
    if entity_bounds[0] < -180:
        entity_bounds = (
            -180,
            entity_bounds[1],
            entity_bounds[2],
            entity_bounds[3],
        )
    if entity_bounds[2] > 180:
        entity_bounds = (
            entity_bounds[0],
            entity_bounds[1],
            180,
            entity_bounds[3],
        )

    # Round the bounds to the closest target resolution.
    entity_bounds = [
        round(x / target_resolution) * target_resolution for x in entity_bounds
    ]

    return entity_bounds


def get_all_codes_with_shapes() -> list[str]:
    """
    Get the list of all available codes for which shapes are available.

    This function retrieves the list of all available codes for which
    shapes are available. This includes both standard shapes from the
    Natural Earth shapefile database and non-standard shapes defined by
    the user in the shapes directory.

    Returns
    -------
    all_codes : list[str]
        List of all available codes for which shapes are available.
    """
    # Get the shape of all countries from the Natural Earth shapefile
    # database.
    shapes_of_all_countries = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name="admin_0_countries"
    )

    # Define a reader for the shapefile.
    reader = cartopy.io.shapereader.Reader(shapes_of_all_countries)

    # Get the list of ISO Alpha-3 codes of all countries. Currently,
    # the Natural Earth shapefile database contains some countries not
    # internationally recognized and without an ISO Alpha-3 code.
    # These are Somaliland and Northern Cyprus. Another country not
    # internationally recognized but with an ISO Alpha-3 code is Kosovo.
    # There are also some territories controlled by other countries or
    # under dispute, which are the Australian Indian Ocean Territories
    # (AU), Ashmore and Cartier Islands (AU), and the Siachen Glacier.
    # Taiwan is included as a separate country with its own code, which
    # is TWN.
    codes_of_all_countries = []
    for shape in list(reader.records()):
        if shape.attributes["ISO_A3"] != "-99":
            codes_of_all_countries.append(shape.attributes["ISO_A3"])
        elif shape.attributes["ISO_A3_EH"] != "-99":
            codes_of_all_countries.append(shape.attributes["ISO_A3_EH"])

    # Get the shape of standard subdivisions from the Natural Earth
    # shapefile database.
    shapes_of_all_standard_subdivisions = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name="admin_1_states_provinces"
    )

    # Define a reader for the shapefile.
    reader = cartopy.io.shapereader.Reader(shapes_of_all_standard_subdivisions)

    # Get the list of codes of all standard subdivisions. Standard
    # subdivisions are available for Australia, Brazil, Canada, China,
    # India, Russia, South Africa, Ukraine, and the United States.
    # Subdivisions of Australia include six states and three internal
    # territories. Subdivisions of Brazil include 26 states and one
    # federal district. Subdivisions of Canada include 10 provinces and
    # three territories. Subdivisions of China include 22 provinces,
    # five autonomous regions, and four municipalities. Subdivisions
    # of India include 28 states and eight union territories.
    # Subdivisions of Russia include 22 republics, nine krais, 46
    # oblasts, three federal cities, one autonomous oblast, and four
    # autonomous okrugs. Subdivisions of South Africa include nine
    # provinces. Sudivisions of Ukraine include Crimea and Sevastopol.
    # Subdivisions of the United States include 50 states and one
    # federal district.
    codes_of_all_standard_subdivisions = [
        shape.attributes["iso_3166_2"] for shape in list(reader.records())
    ]

    # Replace the ISO Alpha-2 code in the subdivision codes with the
    # corresponding ISO Alpha-3 code.
    for i, code in enumerate(codes_of_all_standard_subdivisions):
        iso_alpha_2_code, subdivision_code = code.split("-")
        iso_alpha_3_code = pycountry.countries.get(
            alpha_2=iso_alpha_2_code
        ).alpha_3
        codes_of_all_standard_subdivisions[i] = (
            iso_alpha_3_code + "_" + subdivision_code
        )

    # Get the codes of all non-standard shapes defined by the user in
    # the shapes directory.
    codes_of_all_non_standard_subdivisions = []
    non_standard_shape_codes = _read_non_standard_shape_codes()
    for codes in non_standard_shape_codes.values():
        codes_of_all_non_standard_subdivisions.extend(codes)

    # Combine the lists of codes of all countries, standard
    # subdivisions, and non-standard subdivisions.
    all_codes = (
        codes_of_all_countries
        + codes_of_all_standard_subdivisions
        + codes_of_all_non_standard_subdivisions
    )

    # Remove any duplicates and sort the list of codes.
    return sorted(list(set(all_codes)))

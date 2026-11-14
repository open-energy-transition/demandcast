"""
License: AGPL-3.0.

Description:

    This module retrieves standard shapes of countries and subdivisions
    from the Natural Earth shapefile database. It also retrieves
    non-standard subdivision shapes from the shapes directory: the
    shapes of subdivisions that Natural Earth does not have, defined in
    a shapefile for each data source, or in ``composites.yaml`` as
    unions of standard subdivisions of Natural Earth at 1:10m, without
    the parts of some of them that polygons mark.
"""

import functools
import os

import cartopy.io.shapereader
import geopandas
import pandas as pd
import pycountry
import shapely
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)
from shapely import Polygon

import utils.codes
import utils.figures
import utils.paths


class Cut(BaseModel):
    """
    Polygon of the parts of standard subdivisions outside composites.

    Attributes
    ----------
    description : str
        What the polygon cuts, and why.
    polygon : str
        The polygon or multipolygon, in WKT, in degrees of longitude
        and latitude.
    """

    model_config = ConfigDict(extra="forbid")

    description: str
    polygon: str

    @field_validator("polygon")
    @classmethod
    def _check_polygon(cls, polygon: str) -> str:
        """
        Check that the polygon is a valid polygon or multipolygon.

        Parameters
        ----------
        polygon : str
            The polygon, in WKT.

        Returns
        -------
        str
            The polygon, unchanged.

        Raises
        ------
        ValueError
            If the text is not the WKT of a valid polygon or
            multipolygon.
        """
        try:
            geometry = shapely.from_wkt(polygon)
        except shapely.errors.GEOSException as error:
            raise ValueError(f"invalid WKT: {error}") from error
        if geometry.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"{geometry.geom_type} is not a polygon")
        if not geometry.is_valid:
            raise ValueError("the polygon is not valid")
        return polygon


class Composite(BaseModel):
    """
    Non-standard subdivision made of standard subdivisions.

    Attributes
    ----------
    name : str
        Name of the subdivision.
    regions : list[str]
        ISO 3166-2 codes of the standard subdivisions of Natural Earth
        at 1:10m that make it, separated by spaces in the file.
    cuts : dict[str, str]
        The name of the cut of some of the standard subdivisions, by
        their ISO 3166-2 code.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    regions: list[str]
    cuts: dict[str, str] = {}

    @field_validator("regions", mode="before")
    @classmethod
    def _split_regions(cls, regions: object) -> object:
        """
        Split the codes of the regions, separated by spaces.

        Parameters
        ----------
        regions : object
            The codes, as a string or already as a list.

        Returns
        -------
        object
            The list of codes, or the value unchanged if it is not a
            string.
        """
        return regions.split() if isinstance(regions, str) else regions


class Composites(BaseModel):
    """
    Content of ``composites.yaml``.

    Attributes
    ----------
    cuts : dict[str, Cut]
        The cuts, by name.
    composites : dict[str, Composite]
        The composites, by code of the subdivision.
    """

    model_config = ConfigDict(extra="forbid")

    cuts: dict[str, Cut]
    composites: dict[str, Composite]

    @model_validator(mode="after")
    def _check_cuts(self) -> "Composites":
        """
        Check that each cut of a composite exists, on its regions.

        Returns
        -------
        Composites
            The composites, unchanged.

        Raises
        ------
        ValueError
            If a composite cuts a region that it does not have, or with
            a cut that does not exist, or a cut is not used.
        """
        used = set()
        for code, composite in self.composites.items():
            for region, cut in composite.cuts.items():
                if region not in composite.regions:
                    raise ValueError(f"{code} cuts {region}, not its region")
                if cut not in self.cuts:
                    raise ValueError(f"{code} has an unknown cut {cut}")
                used.add(cut)
        unused = sorted(set(self.cuts) - used)
        if unused:
            raise ValueError(f"unused cuts: {', '.join(unused)}")
        return self


@functools.cache
def read_composites() -> Composites:
    """
    Read the composites of the shapes directory.

    Returns
    -------
    Composites
        The cuts and the composites of ``composites.yaml``.

    Raises
    ------
    ValueError
        If the file is not valid.
    """
    with open(utils.paths.COMPOSITES_FILE, encoding="utf-8") as file:
        content = yaml.safe_load(file)
    try:
        return Composites.model_validate(content)
    except ValidationError as error:
        raise ValueError(
            f"The file of the composites is not valid: {error}"
        ) from error


@functools.cache
def _read_detailed_standard_subdivisions() -> geopandas.GeoDataFrame:
    """
    Read the standard subdivisions of Natural Earth at 1:10m.

    Returns
    -------
    geopandas.GeoDataFrame
        The standard subdivisions, with their ISO 3166-2 code in the
        column ``iso_3166_2``.
    """
    path = cartopy.io.shapereader.natural_earth(
        resolution="10m", category="cultural", name="admin_1_states_provinces"
    )
    return geopandas.read_file(path)


def _get_composite_shape(code: str) -> geopandas.GeoDataFrame:
    """
    Make the shape of a composite.

    Parameters
    ----------
    code : str
        The combination of ISO Alpha-3 code and subdivision code.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame with the standard subdivisions of the composite,
        one per row, each without the polygon of its cut, if any.

    Raises
    ------
    ValueError
        If Natural Earth does not have a standard subdivision of the
        composite.
    """
    composites = read_composites()
    composite = composites.composites[code]
    regions = _read_detailed_standard_subdivisions()
    selected = regions[regions["iso_3166_2"].isin(composite.regions)]
    missing = sorted(set(composite.regions) - set(selected["iso_3166_2"]))
    if missing:
        raise ValueError(
            f"Natural Earth has no subdivision {', '.join(missing)} of "
            f"the composite {code}."
        )
    geometries = []
    for region, geometry in zip(
        selected["iso_3166_2"], selected.geometry, strict=True
    ):
        part = geometry
        if region in composite.cuts:
            cut = composites.cuts[composite.cuts[region]]
            part = geometry.difference(shapely.from_wkt(cut.polygon))
        geometries.append(part)
    return geopandas.GeoDataFrame(geometry=geometries, crs=4326)


def _remove_islands_and_clip_to_180(  # noqa: C901
    entity_shape: geopandas.GeoDataFrame, code: str
) -> geopandas.GeoDataFrame:
    """
    Remove small remote islands and clip to 180/-180 longitude.

    The shape of some countries and subdivisions is cut to a box that
    leaves out their small remote islands and the parts beyond the
    180/-180 longitude.

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

    Notes
    -----
    The small remote islands are not relevant for the analysis and
    would lead to the download of large weather datasets. The clipping
    to the 180/-180 longitude avoids issues with the data retrieval.
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
        case "FJI":  # Fiji
            new_bounds = geopandas.GeoSeries(
                Polygon([(172, -22), (180, -22), (180, -10), (172, -10)])
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
        case "RUS":  # Russia
            new_bounds = geopandas.GeoSeries(
                Polygon([(0, 0), (180, 0), (180, 90), (0, 90)])
            )
        case "RUS_CHU":  # Russia - Chukotka Autonomous Okrug
            new_bounds = geopandas.GeoSeries(
                Polygon([(150, 60), (180, 60), (180, 75), (150, 75)])
            )
        case "USA":  # United States
            new_bounds = geopandas.GeoSeries(
                Polygon([(-180, 10), (-50, 10), (-50, 90), (-180, 90)])
            )

    if new_bounds is not None:
        new_bounds_frame = geopandas.GeoDataFrame.from_features(
            new_bounds, crs=4326
        )
        entity_shape = entity_shape.overlay(
            new_bounds_frame, how="intersection"
        )

    return entity_shape


def get_standard_shape(
    code: str, remove_remote_islands: bool = True
) -> geopandas.GeoDataFrame:
    """
    Retrieve the shape of a country or subdivision.

    The shape comes from the Natural Earth shapefile database, found by
    the code of the entity, or else by its name.

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

    Raises
    ------
    ValueError
        If no shape matches the code or the name of the entity.
    """
    if "_" not in code:
        shapefile_name = "admin_0_countries"
        main_keys = ["ISO_A3", "ISO_A3_EH"]
        secondary_keys = ["NAME", "NAME_LONG"]
        code_to_search = code
    else:
        shapefile_name = "admin_1_states_provinces"
        main_keys = ["iso_3166_2"]
        secondary_keys = ["name"]

        iso_alpha_3_code, subdivision_code = code.split("_")
        iso_alpha_2_code = utils.codes.get_iso_alpha_2_code(iso_alpha_3_code)

        # Combine the ISO Alpha-2 code and the subdivision code to
        # match the format used in the shapefile database.
        code_to_search = f"{iso_alpha_2_code}-{subdivision_code}"

    all_shapes = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name=shapefile_name
    )
    reader = cartopy.io.shapereader.Reader(all_shapes)

    entity_shape = next(
        (
            shape
            for shape in reader.records()
            if code_to_search in [shape.attributes[key] for key in main_keys]
        ),
        None,
    )

    if entity_shape is None:
        name_to_search = utils.codes.get_name_from_code(code)
        entity_shape = next(
            (
                shape
                for shape in reader.records()
                if name_to_search
                in [shape.attributes[key] for key in secondary_keys]
            ),
            None,
        )

    if entity_shape is None:
        raise ValueError(f"No shape found for {code} in Natural Earth.")

    entity_series = geopandas.GeoSeries(
        pd.Series({"geometry": entity_shape.geometry})
    )
    entity_shape_frame = geopandas.GeoDataFrame.from_features(
        entity_series, crs=4326
    )

    if remove_remote_islands:
        entity_shape_frame = _remove_islands_and_clip_to_180(
            entity_shape_frame, code
        )

    return entity_shape_frame


def _read_non_standard_shape_codes() -> dict[str, list[str]]:
    """
    Read the non-standard shapes codes from the shapes directory.

    The codes are read from the shapefile of each data source in the
    shapes directory.

    Returns
    -------
    non_standard_shape_codes : dict[str, list[str]]
        Dictionary containing the non-standard shapes and their
        respective codes.
    """
    shapes_directory = utils.paths.SHAPES_FOLDER

    non_standard_shape_codes = {}
    for folder in os.listdir(shapes_directory):
        if os.path.isdir(os.path.join(shapes_directory, folder)):
            shapefile_path = os.path.join(
                shapes_directory, folder, folder + ".shp"
            )
            entity_shapes = geopandas.read_file(shapefile_path)
            entity_codes = entity_shapes["code"].unique()
            non_standard_shape_codes[folder] = list(entity_codes)

    return non_standard_shape_codes


def _get_non_standard_shape(
    code: str, data_source: str
) -> geopandas.GeoDataFrame:
    """
    Retrieve the shape of a non-standard subdivision.

    The shape is read from the shapes directory.

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
    shapes_directory = utils.paths.SHAPES_FOLDER
    shapefile_path = os.path.join(
        shapes_directory, data_source, data_source + ".shp"
    )
    entity_shapes = geopandas.read_file(shapefile_path)

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

    A country has the shape of the Natural Earth shapefile database. A
    subdivision has its non-standard shape, if it has one, as a
    composite or in the shapefile of a data source, and that of the
    Natural Earth shapefile database otherwise.

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
    if "_" not in code:
        entity_shape = get_standard_shape(code, remove_remote_islands)
    elif code in read_composites().composites:
        entity_shape = _get_composite_shape(code)
    else:
        is_non_standard_shape = False
        selected_data_source = ""

        non_standard_shape_codes = _read_non_standard_shape_codes()
        for (
            data_source,
            codes_of_data_source,
        ) in non_standard_shape_codes.items():
            if code in codes_of_data_source:
                is_non_standard_shape = True
                selected_data_source = data_source
                break

        if is_non_standard_shape:
            entity_shape = _get_non_standard_shape(code, selected_data_source)
        else:
            entity_shape = get_standard_shape(code, remove_remote_islands)

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

    The bounds are returned as a list containing the western,
    southern, eastern, and northern bounds, respectively. One degree of
    buffer is added to the bounds, which are kept within -180 and 180
    degrees of longitude and rounded to the closest multiple of the
    target resolution.

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
    entity_bounds = (
        entity_shape.union_all().buffer(1).bounds
    )  # West, South, East, North

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

    return [
        round(x / target_resolution) * target_resolution for x in entity_bounds
    ]


def get_all_codes_with_shapes() -> list[str]:
    """
    Get the list of all available codes for which shapes are available.

    The codes are those of the countries and standard subdivisions of
    the Natural Earth shapefile database, and of the non-standard
    shapes in the shapes directory, composites included.

    Returns
    -------
    all_codes : list[str]
        List of all available codes for which shapes are available.

    Raises
    ------
    ValueError
        If a subdivision has an unknown ISO Alpha-2 code.

    Notes
    -----
    The countries of Natural Earth include Somaliland and Northern
    Cyprus, which are not internationally recognized and have no ISO
    Alpha-3 code, and Kosovo, which has one, but whose shape does not:
    it is found by its name among the entities that pycountry does not
    list. They also include territories controlled by other countries
    or under dispute: the Australian Indian Ocean Territories (AU),
    Ashmore and Cartier Islands (AU) and the Siachen Glacier. Taiwan is
    a separate country, with the code TWN.

    The standard subdivisions are those of Australia (six states and
    three internal territories), Brazil (26 states and one federal
    district), Canada (10 provinces and three territories), China (22
    provinces, five autonomous regions and four municipalities), India
    (28 states and eight union territories), Russia (22 republics, nine
    krais, 46 oblasts, three federal cities, one autonomous oblast and
    four autonomous okrugs), South Africa (nine provinces), Ukraine
    (Crimea and Sevastopol) and the United States (50 states and one
    federal district).
    """
    shapes_of_all_countries = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name="admin_0_countries"
    )
    reader = cartopy.io.shapereader.Reader(shapes_of_all_countries)

    # Get the list of ISO Alpha-3 codes of all countries.
    codes_of_extra_entities = {
        info["name"]: code for code, info in utils.codes.EXTRA_ENTITIES.items()
    }
    codes_of_all_countries = []
    for shape in list(reader.records()):
        if shape.attributes["ISO_A3"] != "-99":
            codes_of_all_countries.append(shape.attributes["ISO_A3"])
        elif shape.attributes["ISO_A3_EH"] != "-99":
            codes_of_all_countries.append(shape.attributes["ISO_A3_EH"])
        elif shape.attributes["NAME"] in codes_of_extra_entities:
            codes_of_all_countries.append(
                codes_of_extra_entities[shape.attributes["NAME"]]
            )

    shapes_of_all_standard_subdivisions = cartopy.io.shapereader.natural_earth(
        resolution="50m", category="cultural", name="admin_1_states_provinces"
    )
    reader = cartopy.io.shapereader.Reader(shapes_of_all_standard_subdivisions)

    # Get the list of codes of all standard subdivisions.
    codes_of_all_standard_subdivisions = [
        shape.attributes["iso_3166_2"] for shape in list(reader.records())
    ]

    # Replace the ISO Alpha-2 code in the subdivision codes with the
    # corresponding ISO Alpha-3 code.
    for i, code in enumerate(codes_of_all_standard_subdivisions):
        iso_alpha_2_code, subdivision_code = code.split("-")
        country = pycountry.countries.get(alpha_2=iso_alpha_2_code)
        if country is None:
            raise ValueError(f"Unknown ISO Alpha-2 code: {iso_alpha_2_code}.")
        iso_alpha_3_code = country.alpha_3
        codes_of_all_standard_subdivisions[i] = (
            iso_alpha_3_code + "_" + subdivision_code
        )

    # Get the codes of all non-standard shapes defined by the user in
    # the shapes directory.
    codes_of_all_non_standard_subdivisions = []
    non_standard_shape_codes = _read_non_standard_shape_codes()
    for codes in non_standard_shape_codes.values():
        codes_of_all_non_standard_subdivisions.extend(codes)
    codes_of_all_non_standard_subdivisions.extend(read_composites().composites)

    all_codes = (
        codes_of_all_countries
        + codes_of_all_standard_subdivisions
        + codes_of_all_non_standard_subdivisions
    )

    return sorted(set(all_codes))

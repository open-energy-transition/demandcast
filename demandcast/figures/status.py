"""
License: AGPL-3.0.

Description:

    This module draws the figures and writes the numbers of the current
    state of DemandCast, which the "Current state" page of the
    documentation shows: the countries and subdivisions with retrieval
    modules of electricity demand data, on a map and by GDP PPP and
    annual electricity demand per capita, and how many countries,
    subdivisions, data sources and years of data there are.

    The figures are drawn into the folder of the figures and copied
    into webpage/docs/status/, with the numbers in numbers.md, which the
    page includes. The README shows the same numbers, in its block
    between the markers STATUS_START and STATUS_END, which is replaced.

    The numbers come from the YAML files of the data sources, like the
    map: the years of a country or subdivision are those of the longest
    period of data of its data sources.
"""

import dataclasses
import datetime
import os
import shutil

import figures.data_availability
import figures.map_of_available_entities
import utils.data_sources
import utils.paths

# The figures of the page, as figures.data_availability and
# figures.map_of_available_entities name them.
FIGURE_FILES = (
    "available_entities_light_mode.png",
    "available_entities_dark_mode.png",
    "data_availability_by_gpd_ppp_and_electricity_demand.png",
)

# The file of the numbers, in the folder of the page.
NUMBERS_FILE = "numbers.md"

# The markers of the block of the numbers in the README.
STATUS_START = "<!-- status:start -->"
STATUS_END = "<!-- status:end -->"


@dataclasses.dataclass(frozen=True)
class Numbers:
    """
    The numbers of the current state of the data.

    Attributes
    ----------
    date : datetime.date
        The date of the numbers.
    countries : int
        The number of countries with national data.
    subdivisions : int
        The number of subdivisions with data.
    countries_covered : int
        The number of countries with national data or data of some of
        their subdivisions.
    data_sources : int
        The number of data sources.
    years : int
        The years of data of all the countries and subdivisions.
    first_year : int
        The first year of data.
    """

    date: datetime.date
    countries: int
    subdivisions: int
    countries_covered: int
    data_sources: int
    years: int
    first_year: int


def get_numbers(date: datetime.date) -> Numbers:
    """
    Count the countries, subdivisions, data sources and years of data.

    Parameters
    ----------
    date : datetime.date
        The date of the numbers.

    Returns
    -------
    Numbers
        The numbers.
    """
    date_ranges = utils.data_sources.read_all_date_ranges()
    codes = utils.data_sources.read_all_codes_with_electricity_demand_data()
    periods = [date_ranges[code] for code in codes]
    subdivisions = [code for code in codes if "_" in code]
    return Numbers(
        date=date,
        countries=len(codes) - len(subdivisions),
        subdivisions=len(subdivisions),
        countries_covered=len({code.split("_")[0] for code in codes}),
        data_sources=len(utils.data_sources.read_data_sources()),
        years=round(
            sum((end - start).days for start, end in periods) / 365.25
        ),
        first_year=min(start.year for start, _ in periods),
    )


def describe(numbers: Numbers) -> str:
    """
    Describe the numbers in a sentence of Markdown.

    Parameters
    ----------
    numbers : Numbers
        The numbers.

    Returns
    -------
    str
        The sentence.
    """
    return (
        f"As of {numbers.date:%d %B %Y}, DemandCast has retrieval modules "
        f"for the hourly electricity demand of **{numbers.countries} "
        f"countries and {numbers.subdivisions} subdivisions**, in "
        f"{numbers.countries_covered} countries, from "
        f"**{numbers.data_sources} data sources**, with about "
        f"**{numbers.years:,} years of data** in total since "
        f"{numbers.first_year}."
    )


def update_readme(readme_file: str, text: str) -> None:
    """
    Replace the block of the numbers in the README.

    Parameters
    ----------
    readme_file : str
        The path of the README.
    text : str
        The text of the block.

    Raises
    ------
    ValueError
        If the README has not the markers of the block.
    """
    with open(readme_file, encoding="utf-8") as file:
        readme = file.read()
    start = readme.find(STATUS_START)
    end = readme.find(STATUS_END)
    if start == -1 or end < start:
        raise ValueError(
            f"The README {readme_file} has not the markers {STATUS_START} "
            f"and {STATUS_END} of the block of the numbers."
        )
    readme = (
        readme[: start + len(STATUS_START)] + "\n" + text + "\n" + readme[end:]
    )
    with open(readme_file, "w", encoding="utf-8") as file:
        file.write(readme)


def plot(
    figure_directory: str,
    status_folder: str = utils.paths.STATUS_FOLDER,
    readme_file: str = utils.paths.README_FILE,
) -> None:
    """
    Draw the figures and write the numbers of the current state.

    Parameters
    ----------
    figure_directory : str
        The directory where the figures are drawn.
    status_folder : str, optional
        The folder of the files of the "Current state" page.
    readme_file : str, optional
        The path of the README.
    """
    figures.map_of_available_entities.plot(figure_directory)
    figures.data_availability.plot(figure_directory)

    os.makedirs(status_folder, exist_ok=True)
    for file_name in FIGURE_FILES:
        shutil.copyfile(
            os.path.join(figure_directory, file_name),
            os.path.join(status_folder, file_name),
        )

    text = describe(get_numbers(datetime.datetime.now().astimezone().date()))
    with open(
        os.path.join(status_folder, NUMBERS_FILE), "w", encoding="utf-8"
    ) as file:
        file.write(text + "\n")
    update_readme(readme_file, text)

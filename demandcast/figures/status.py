"""
License: AGPL-3.0.

Description:

    This module draws the figures and writes the numbers of the current
    state of DemandCast, which the "Current state" page of the
    documentation shows: the countries and subdivisions with retrieval
    modules of electricity demand data, on a map and by GDP PPP and
    annual electricity demand per capita, how many countries,
    subdivisions, data sources and years of data there are, and the
    errors of a validation and of a cross-validation of the models (see
    figures.ml_results): the error of each code, their distribution and
    the hourly demand of the codes with the lowest and the highest
    error, with the median WAPE of each case in ml_validation.md and
    ml_cross_validation.md.

    The figures are drawn into the folder of the figures and copied
    into webpage/docs/status/, with the numbers in numbers.md, which the
    page includes. The README shows the same numbers, in its block
    between the markers STATUS_START and STATUS_END, which is replaced,
    and the map on a white background.
"""

import dataclasses
import datetime as dt
import os
import shutil
from typing import Literal, cast

import pandas as pd

import figures.data_availability
import figures.map_of_available_entities
import figures.ml_results
import ml_models.files
import utils.data_sources
import utils.paths

# The figures of the page, as figures.data_availability and
# figures.map_of_available_entities name them. The README shows the map
# on a white background, which reads with both the light and the dark
# theme of GitHub, whatever the colour scheme of the browser.
FIGURE_FILES = (
    "available_entities.png",
    "available_entities_light_mode.png",
    "available_entities_dark_mode.png",
    "data_availability_by_gpd_ppp_and_electricity_demand.png",
)

# The file of the numbers, in the folder of the page.
NUMBERS_FILE = "numbers.md"

# The figures of the errors of the models on the page, the bars of the
# codes, their distribution and the hourly demand of the best and the
# worst code, by case of the results.
ML_FIGURE_FILES: dict[
    Literal["validation", "cross_validation"], tuple[str, str, str]
] = {
    case: (
        f"wape_{case}.png",
        f"wape_{case}_distribution.png",
        f"wape_{case}_best_and_worst.png",
    )
    for case in ("validation", "cross_validation")
}

# The files of the description of the model and of the errors of each
# case, in the folder of the page.
ML_RESULTS_FILES = {
    "model": "ml_model.md",
    "validation": "ml_validation.md",
    "cross_validation": "ml_cross_validation.md",
}

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

    date: dt.date
    countries: int
    subdivisions: int
    countries_covered: int
    data_sources: int
    years: int
    first_year: int


def get_numbers(date: dt.date) -> Numbers:
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

    Notes
    -----
    The numbers come from the YAML files of the data sources: the years
    of a country or subdivision are those of the longest period of data
    of its data sources.
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
        f"{numbers.first_year}, in the periods that the data sources "
        "cover, before the cleaning and the selection of the complete "
        "years for training."
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


def _find_results(
    case: Literal["validation", "cross_validation"],
    file_path: str | None = None,
) -> tuple[str, ml_models.files.Results] | None:
    """
    Find the results of a case to publish, checked with their summary.

    Parameters
    ----------
    case : str
        The case of the results, "validation" or "cross_validation".
    file_path : str | None, optional
        The Parquet file of the results, by default the latest of all
        the versions of the case, by the time in their names.

    Returns
    -------
    tuple[str, ml_models.files.Results] | None
        The version of the results, the trained model of a validation or
        the algorithm of a cross-validation, and the results checked
        against their manifest (see ml_models.files.read_results), or
        None if the case has no results.

    Raises
    ------
    ValueError
        If the results have no summary or no predictions in their
        manifest.
    """
    file_path = file_path or ml_models.files.find_latest_results(
        utils.paths.get_results_folder(case), "*"
    )
    if file_path is None:
        return None
    results = ml_models.files.read_results(file_path)
    if results.summary is None or "predictions" not in (
        results.manifest or {}
    ):
        raise ValueError(
            f"The results {file_path} have no summary or no predictions in "
            "their manifest, so they cannot be described."
        )
    version = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
    return version.removeprefix("with_"), results


def _get_median_wape(
    summary: pd.DataFrame, group: str = "All", value: str = "All"
) -> float:
    """
    Get the median WAPE of a group of codes, in percent.

    Parameters
    ----------
    summary : pandas.DataFrame
        The summary of the results by group of codes.
    group : str, optional
        The group, such as "Seen in training".
    value : str, optional
        The value of the group, such as "Yes".

    Returns
    -------
    float
        The median WAPE of the codes of the group, in percent.
    """
    rows = summary[(summary["Group"] == group) & (summary["Value"] == value)]
    return float(rows["Median WAPE"].iloc[0]) * 100


def describe_model(
    validation: tuple[str, ml_models.files.Results] | None,
    cross_validation: tuple[str, ml_models.files.Results] | None,
) -> str:
    """
    Describe the models of the results in a paragraph.

    Each evaluation trains its own models, without the data that it
    leaves out, which its section describes, so the paragraph names
    their algorithm, not a trained model.

    Parameters
    ----------
    validation : tuple[str, ml_models.files.Results] | None
        The trained model of the validation and its results, or None if
        there is none.
    cross_validation : tuple[str, ml_models.files.Results] | None
        The algorithm of the cross-validation and its results, or None
        if there is none.

    Returns
    -------
    str
        The paragraph, in Markdown, empty without results.
    """
    algorithms = [
        found[0].partition("_model_")[0]
        for found in (validation, cross_validation)
        if found is not None
    ]
    names = list(
        dict.fromkeys(
            figures.ml_results.ALGORITHM_NAMES.get(algorithm, algorithm)
            for algorithm in algorithms
        )
    )
    if not names:
        return ""
    return (
        f"Each trains {' and '.join(names)} models on the data above, "
        "without the data that it scores them on, which its section "
        "describes."
    )


def describe_validation(
    validation: tuple[str, ml_models.files.Results] | None,
) -> str:
    """
    Describe the errors of the validation in a paragraph of Markdown.

    Parameters
    ----------
    validation : tuple[str, ml_models.files.Results] | None
        The trained model of the validation and its results, or None if
        there is none.

    Returns
    -------
    str
        The paragraph.
    """
    if validation is None:
        return "The models have no validation yet."
    version, results = validation
    summary = cast(pd.DataFrame, results.summary)
    algorithm = version.partition("_model_")[0]
    name = figures.ml_results.ALGORITHM_NAMES.get(algorithm, algorithm)
    return (
        f"In the validation of {name}, the median WAPE of the countries and "
        "subdivisions is "
        f"**{_get_median_wape(summary):.1f}%**: "
        f"{_get_median_wape(summary, 'Seen in training', 'Yes'):.1f}% for "
        "those whose other years the model saw in training, and "
        f"{_get_median_wape(summary, 'Seen in training', 'No'):.1f}% for "
        "those that it never saw."
    )


def describe_cross_validation(
    cross_validation: tuple[str, ml_models.files.Results] | None,
) -> str:
    """
    Describe the errors of the cross-validation in a paragraph.

    The cross-validation is described by the holdout that its manifest
    records, a held-out entity by default.

    Parameters
    ----------
    cross_validation : tuple[str, ml_models.files.Results] | None
        The algorithm of the cross-validation and its results, or None
        if there is none.

    Returns
    -------
    str
        The paragraph, in Markdown.
    """
    if cross_validation is None:
        return "The models have no cross-validation yet."
    algorithm, results = cross_validation
    summary = cast(pd.DataFrame, results.summary)
    name = figures.ml_results.ALGORITHM_NAMES.get(algorithm, algorithm)
    holdout = (results.manifest or {}).get("holdout", "entity")
    codes = int(summary.loc[summary["Group"] == "All", "Codes"].iloc[0])
    return (
        f"The cross-validation of {name} leaves "
        + (
            "each country, with its subdivisions,"
            if holdout == "country"
            else "each country or subdivision"
        )
        + " out of the training in turn, and the median WAPE of the "
        f"{codes} held-out countries and subdivisions is "
        f"**{_get_median_wape(summary):.1f}%**, an estimate of the "
        + (
            "error for a country without data."
            if holdout == "country"
            else "error for a country or subdivision without data, whose "
            "country can have data of its other subdivisions."
        )
    )


def _plot_ml_results(
    figure_directory: str,
    status_folder: str,
    results_files: dict[str, str | None] | None = None,
) -> tuple[tuple[str, ml_models.files.Results] | None, ...]:
    """
    Draw the figures of the errors of the models into the page.

    Parameters
    ----------
    figure_directory : str
        The directory where the figures are drawn.
    status_folder : str
        The folder of the files of the "Current state" page.
    results_files : dict[str, str | None] | None, optional
        The Parquet file of the results of each case, by default the
        latest.

    Returns
    -------
    tuple[tuple[str, ml_models.files.Results] | None, ...]
        The version and results of the validation and of the
        cross-validation, or None for a case without results.
    """
    published = []
    for case, file_names in ML_FIGURE_FILES.items():
        found = _find_results(case, (results_files or {}).get(case))
        published.append(found)
        if found is None:
            continue
        version, results = found
        results_directory = utils.paths.get_results_folder(case)
        figures.ml_results.plot(
            figure_directory,
            version,
            results_directory=results_directory,
            results_file=results.file_path,
        )
        _, stem = figures.ml_results.describe_version(
            results_directory, version, results.file_path
        )
        for drawn, file_name in zip(
            (
                f"wape_{stem}.png",
                f"wape_{stem}_distribution.png",
                f"wape_{stem}_best_and_worst.png",
            ),
            file_names,
            strict=True,
        ):
            shutil.copyfile(
                os.path.join(figure_directory, drawn),
                os.path.join(status_folder, file_name),
            )
    return tuple(published)


def plot(
    figure_directory: str,
    status_folder: str = utils.paths.STATUS_FOLDER,
    readme_file: str = utils.paths.README_FILE,
    results_files: dict[str, str | None] | None = None,
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
    results_files : dict[str, str | None] | None, optional
        The Parquet file of the results of the validation and of the
        cross-validation to publish ("validation" and
        "cross_validation"), by default the latest of each.
    """
    figures.map_of_available_entities.plot(figure_directory)
    figures.data_availability.plot(figure_directory)

    os.makedirs(status_folder, exist_ok=True)
    for file_name in FIGURE_FILES:
        shutil.copyfile(
            os.path.join(figure_directory, file_name),
            os.path.join(status_folder, file_name),
        )

    text = describe(get_numbers(dt.datetime.now().astimezone().date()))
    with open(
        os.path.join(status_folder, NUMBERS_FILE), "w", encoding="utf-8"
    ) as file:
        file.write(text + "\n")
    update_readme(readme_file, text)

    validation, cross_validation = _plot_ml_results(
        figure_directory, status_folder, results_files
    )
    for case, text in (
        ("model", describe_model(validation, cross_validation)),
        ("validation", describe_validation(validation)),
        ("cross_validation", describe_cross_validation(cross_validation)),
    ):
        with open(
            os.path.join(status_folder, ML_RESULTS_FILES[case]),
            "w",
            encoding="utf-8",
        ) as file:
            file.write(text + "\n")

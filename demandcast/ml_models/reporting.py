"""
License: AGPL-3.0.

Description:

    This module describes the countries and subdivisions on which a
    model is scored, and summarizes its errors by group of them, so
    that the results tell where the model fails, not only how much.

    Each country or subdivision is described by whether the model saw
    other years of it in training, its number of years, its mean load
    and its size class, its continent, and the data source of most of
    its scored hours with what the demand of that source counts of the
    embedded generation (see utils.data_sources), read from its
    combined demand.

    The summary groups the codes by whether the model saw them, by
    size class, by continent and by what their demand counts of the
    embedded generation, and gives for each group its median WAPE, its
    WAPE weighted by the energy of each code, which is that of the
    group as a whole, and its median MAPE.
"""

import logging

import numpy as np
import pandas as pd

import ml_models.data
import utils.codes
import utils.data_sources
import utils.paths

# The upper limits of the mean load of the size classes, in MW.
SIZE_CLASSES = {"Small": 300.0, "Medium": 5000.0, "Large": np.inf}

# The names of the continent codes of config/continents.yaml.
CONTINENT_NAMES = {
    "AF": "Africa",
    "AN": "Antarctica",
    "AS": "Asia",
    "EU": "Europe",
    "NA": "North America",
    "OC": "Oceania",
    "SA": "South America",
}

# The names of the values of the yes-or-no columns of the description.
_VALUE_NAMES = {True: "Yes", False: "No"}

# The columns of the description that group the codes in the summary.
GROUPING_COLUMNS = (
    "Seen in training",
    "Size class",
    "Continent",
    "Embedded generation",
)


def get_size_class(mean_load: float) -> str:
    """
    Get the size class of a mean load.

    Parameters
    ----------
    mean_load : float
        The mean load, in MW.

    Returns
    -------
    str
        The first size class whose upper limit is above the load.
    """
    return next(
        name for name, limit in SIZE_CLASSES.items() if mean_load < limit
    )


def _get_main_source(
    code: str, times: pd.Series
) -> tuple[str | None, str | None]:
    """
    Get the data source of most of the scored hours of a code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    times : pandas.Series
        The scored hours, by their ends in UTC.

    Returns
    -------
    tuple[str | None, str | None]
        The data source, and what its demand counts of the embedded
        generation on the middle scored day, or None if the code has no
        combined demand at those hours.
    """
    file_path = utils.paths.get_electricity_demand_file("combined", code)
    try:
        sources = pd.read_parquet(file_path, columns=["Source"])["Source"]
    except FileNotFoundError:
        logging.warning(f"{code} has no combined demand to describe.")
        return None, None
    scored_sources = sources[
        sources.index.isin(pd.DatetimeIndex(times).as_unit("us"))
    ].dropna()
    if scored_sources.empty:
        return None, None
    data_source = str(scored_sources.value_counts().index[0])
    middle_day = pd.Timestamp(times.median()).date()
    definition = utils.data_sources.get_definition(data_source, middle_day)
    return data_source, definition.embedded_generation


def describe_entities(
    scored: ml_models.data.PreparedDataset,
    training: ml_models.data.PreparedDataset | None = None,
) -> pd.DataFrame:
    """
    Describe the countries and subdivisions of a scored set.

    Parameters
    ----------
    scored : PreparedDataset
        The scored rows, with their times and local years, and their
        load in MW among their other fields if known.
    training : PreparedDataset | None, optional
        The training rows of the model, to tell which codes it saw.
        None if it saw none of the scored codes, as in a
        cross-validation.

    Returns
    -------
    pandas.DataFrame
        For each code ("Entity code"), "Seen in training" and "Training
        years" if training rows are given, "Scored years", "Scored
        hours", "Mean load (MW)", "Size class", "Continent", "Data
        source" and "Embedded generation".
    """
    others = scored.get("others", pd.DataFrame(index=scored["group"].index))
    rows = pd.DataFrame(
        {
            "Entity code": scored["group"],
            "Time": scored["time"],
            "Local year": scored["local_year"],
            "Load (MW)": others.get("Load (MW)", np.nan),
        }
    )

    descriptions = []
    for code, entity_rows in rows.groupby("Entity code", sort=True):
        description: dict[str, object] = {"Entity code": code}
        if training is not None:
            training_years = training["local_year"][
                training["group"] == code
            ].nunique()
            description["Seen in training"] = training_years > 0
            description["Training years"] = training_years
        mean_load = float(entity_rows["Load (MW)"].mean())
        data_source, embedded_generation = _get_main_source(
            str(code), entity_rows["Time"]
        )
        description |= {
            "Scored years": entity_rows["Local year"].nunique(),
            "Scored hours": len(entity_rows),
            "Mean load (MW)": mean_load,
            "Size class": get_size_class(mean_load)
            if np.isfinite(mean_load)
            else None,
            "Continent": CONTINENT_NAMES[
                utils.codes.get_continent_code(str(code))
            ],
            "Data source": data_source,
            "Embedded generation": embedded_generation,
        }
        descriptions.append(description)
    return pd.DataFrame(descriptions)


def group_codes(
    results: pd.DataFrame, column: str
) -> list[tuple[str, pd.DataFrame]]:
    """
    Group the codes of the results by a column of their description.

    Parameters
    ----------
    results : pandas.DataFrame
        The results of each code, with its description (see
        describe_entities).
    column : str
        The column of the description, such as "Size class".

    Returns
    -------
    list[tuple[str, pandas.DataFrame]]
        The name of each value of the column, "Yes" or "No" for a
        column of yes or no, and the results of its codes: the size
        classes from the smallest, the other values in alphabetical
        order, without the codes whose value is not known.
    """
    values = (
        pd.Series(
            pd.Categorical(results[column], categories=list(SIZE_CLASSES)),
            index=results.index,
        )
        if column == "Size class"
        else results[column].map(_VALUE_NAMES).fillna(results[column])
    )
    return [
        (str(value), rows)
        for value, rows in results.groupby(values, sort=True, observed=True)
    ]


def summarize(results: pd.DataFrame, set_name: str) -> pd.DataFrame:
    """
    Summarize the errors of a set by group of codes.

    Parameters
    ----------
    results : pandas.DataFrame
        The errors of each code, in the columns "<Set> MAPE" and "<Set>
        WAPE", with its description (see describe_entities).
    set_name : str
        The name of the set, such as "Testing".

    Returns
    -------
    pandas.DataFrame
        For all the codes and for each group ("Group" and "Value"), the
        number of codes ("Codes"), their "Median WAPE", their WAPE
        weighted by their energy ("Energy-weighted WAPE") and their
        "Median MAPE".
    """
    scored = results.dropna(subset=[f"{set_name} WAPE"])
    groups = [("All", "All", scored)]
    for column in GROUPING_COLUMNS:
        if column in scored:
            groups += [
                (column, value, rows)
                for value, rows in group_codes(scored, column)
            ]

    summary = []
    for group, value, rows in groups:
        energy = rows["Mean load (MW)"] * rows["Scored hours"]
        summary.append(
            {
                "Group": group,
                "Value": value,
                "Codes": len(rows),
                "Median WAPE": rows[f"{set_name} WAPE"].median(),
                "Energy-weighted WAPE": float(
                    (rows[f"{set_name} WAPE"] * energy).sum() / energy.sum()
                )
                if energy.sum() > 0
                else np.nan,
                "Median MAPE": rows[f"{set_name} MAPE"].median(),
            }
        )
    return pd.DataFrame(summary)


def log_summary(summary: pd.DataFrame, title: str) -> None:
    """
    Log the summary of the errors by group of codes.

    Parameters
    ----------
    summary : pandas.DataFrame
        The summary (see summarize).
    title : str
        What the summary is of, such as "Testing set".
    """
    logging.info(f"{title}, by group of codes:")
    for row in summary.to_dict("records"):
        logging.info(
            f" - {row['Group']}: {row['Value']} ({row['Codes']} codes): "
            f"median WAPE {row['Median WAPE']:.1%}, energy-weighted WAPE "
            f"{row['Energy-weighted WAPE']:.1%}, median MAPE "
            f"{row['Median MAPE']:.1%}"
        )

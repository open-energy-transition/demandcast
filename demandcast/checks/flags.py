"""
License: AGPL-3.0.

Description:

    This module gathers the flags of the cleaned electricity demand of
    all the countries, subdivisions and data sources, which the cleaning
    saves next to the cleaned data (see cleaning/flags.py), into one
    report, and compares them with the flags that have been reviewed.

    The reviews, in checks/reviewed_flags.yaml, give a data source, a
    code, a flag, the periods of the flag that they review (all of them
    if not given), the verdict of the review and a note. The verdicts
    are:

    - source_error: the data of the source is wrong.
    - reading_error: DemandCast reads the data of the source wrongly.
    - definition_change: what the data of the source covers changes.
    - net_demand: the data leaves out the demand that the generation
      embedded in the distribution networks supplies, while DemandCast
      models the gross demand.
    - real_event: the demand itself changes, such as in a lockdown.
    - false_positive: the flag comes from its rule, not from the data.

    The flags of the combined electricity demand of each code (see
    cleaning/combining.py) have the data source "combined". A combined
    flag takes the review that has the data source "combined", if there
    is one, and otherwise, if its main source, the data source of most
    of the hours of the flagged period, has the same flag in the same
    period, the review of that flag: a flag that comes from the data of
    a source is reviewed once. A flag that its main source does not
    have comes from the combination and needs its own review.

    The report, flags_report.csv and flags_report.md in the results of
    the checks (see utils/paths.py), lists the flags that have not been
    reviewed, those that have, with their verdicts, and the reviews that
    match no flag any more, such as those of the errors that have been
    fixed, which can be removed. The combined flags have their own
    section.
"""

import datetime
import glob
import logging
import os
from typing import Literal

import pandas as pd
import utils.entities
import utils.paths
import yaml
from pydantic import BaseModel, ConfigDict

# The data source of the flags of the combined electricity demand.
COMBINED = "combined"

# The name of the file of the reviews, and of the files of the report,
# without extension.
REVIEWS_NAME = "reviewed_flags"
REPORT_NAME = "flags_report"

# The columns of the flags, and of the report, with the verdict and the
# note of the review of each flag and the data source of the review.
FLAG_COLUMNS = [
    "data_source",
    "main_source",
    "code",
    "flag",
    "period",
    "start",
    "end",
    "value",
    "reference",
]
COLUMNS = [*FLAG_COLUMNS, "verdict", "note", "review_of"]


class Review(BaseModel):
    """The review of a flag of a data source and a code."""

    # A misspelt field is an error, so that a review of some periods
    # does not become one of all the periods.
    model_config = ConfigDict(extra="forbid")

    data_source: str
    code: str
    flag: str
    periods: list[str] | None = None
    verdict: Literal[
        "source_error",
        "reading_error",
        "definition_change",
        "net_demand",
        "real_event",
        "false_positive",
    ]
    note: str

    def matches(
        self, data_source: str, code: str, flag: str, period: str
    ) -> bool:
        """
        Check whether the review is of a flagged period.

        Parameters
        ----------
        data_source : str
            The data source.
        code : str
            The code of the country or subdivision.
        flag : str
            The flag.
        period : str
            The flagged period.

        Returns
        -------
        bool
            Whether the review is of the flagged period.
        """
        return (self.data_source, self.code, self.flag) == (
            data_source,
            code,
            flag,
        ) and (self.periods is None or period in self.periods)


def _split_name(name: str, data_sources: list[str]) -> tuple[str, str]:
    """
    Split the name of a file into the code and the data source.

    Parameters
    ----------
    name : str
        The name of the file, "<code>_<data source>", without extension.
    data_sources : list[str]
        The data sources.

    Returns
    -------
    tuple[str, str]
        The code and the data source, the longest that ends the name.

    Raises
    ------
    ValueError
        If no data source ends the name.
    """
    for data_source in sorted(data_sources, key=len, reverse=True):
        if name.endswith("_" + data_source):
            return name.removesuffix("_" + data_source), data_source
    raise ValueError(f"The file {name} is not of a known data source.")


def _get_main_source(code: str, start: object, end: object) -> str:
    """
    Get the data source of most of the hours of a combined period.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    start : object
        The first day of the period.
    end : object
        The last day of the period.

    Returns
    -------
    str
        The data source of most of the hours of the combined electricity
        demand in the period, or of all of them without hours in it.
    """
    sources = pd.read_parquet(
        utils.paths.get_electricity_demand_file("combined", code),
        columns=["Source"],
    )["Source"]
    days = pd.DatetimeIndex(sources.index).normalize()
    in_period = (days >= pd.Timestamp(str(start))) & (
        days <= pd.Timestamp(str(end))
    )
    counts = (
        sources[in_period] if in_period.any() else sources
    ).value_counts()
    return str(counts.index[0])


def read_flags() -> pd.DataFrame:
    """
    Read the flags of the cleaned and combined electricity demand.

    Returns
    -------
    pandas.DataFrame
        The flags of all the countries, subdivisions and data sources,
        with their data source ("data_source", "combined" for the
        combined demand), main source ("main_source", the data source
        itself, or that of most hours of a combined flag) and code
        ("code").
    """
    data_sources = utils.entities.read_data_sources()
    frames = []
    for file_path in sorted(
        glob.glob(
            os.path.join(
                utils.paths.get_electricity_demand_folder("cleaned"),
                "*_flags.parquet",
            )
        )
    ):
        name = os.path.basename(file_path).removesuffix("_flags.parquet")
        code, data_source = _split_name(name, data_sources)
        flags = pd.read_parquet(file_path)
        if not flags.empty:
            frames.append(
                flags.assign(
                    data_source=data_source, main_source=data_source, code=code
                )
            )
    for file_path in sorted(
        glob.glob(
            os.path.join(
                utils.paths.get_electricity_demand_folder("combined"),
                "*_flags.parquet",
            )
        )
    ):
        code = os.path.basename(file_path).removesuffix("_flags.parquet")
        flags = pd.read_parquet(file_path)
        if not flags.empty:
            main_sources = [
                _get_main_source(code, start, end)
                for start, end in zip(
                    flags["start"].tolist(), flags["end"].tolist(), strict=True
                )
            ]
            frames.append(
                flags.assign(
                    data_source=COMBINED, main_source=main_sources, code=code
                )
            )
    if not frames:
        return pd.DataFrame(columns=FLAG_COLUMNS)
    return pd.concat(frames, ignore_index=True)[FLAG_COLUMNS]


def read_reviews() -> list[Review]:
    """
    Read the reviews of the flags.

    Returns
    -------
    list[Review]
        The reviews.
    """
    file_path = os.path.join(
        utils.paths.CHECKS_FOLDER,
        REVIEWS_NAME + ".yaml",
    )
    with open(file_path, encoding="utf-8") as file:
        reviews = yaml.safe_load(file)["reviews"] or []
    return [Review(**review) for review in reviews]


def _add_reviews(flags: pd.DataFrame, reviews: list[Review]) -> pd.DataFrame:
    """
    Add the verdict and the note of its review to each flag.

    Parameters
    ----------
    flags : pandas.DataFrame
        The flags.
    reviews : list[Review]
        The reviews.

    Returns
    -------
    pandas.DataFrame
        The flags, with the verdict ("verdict") and the note ("note") of
        their review, empty if they have not been reviewed, and the data
        source of the review ("review_of"): a combined flag without its
        own review takes that of the same flag of its main source.
    """
    source_flags = set(
        zip(
            flags["data_source"].astype(str),
            flags["code"].astype(str),
            flags["flag"].astype(str),
            flags["period"].astype(str),
            strict=True,
        )
    )
    verdicts, notes, reviews_of = [], [], []
    for row in flags.itertuples():
        data_sources = [str(row.data_source)]
        if (
            row.data_source == COMBINED
            and (
                str(row.main_source),
                str(row.code),
                str(row.flag),
                str(row.period),
            )
            in source_flags
        ):
            data_sources.append(str(row.main_source))
        review = next(
            (
                review
                for data_source in data_sources
                for review in reviews
                if review.matches(
                    data_source, str(row.code), str(row.flag), str(row.period)
                )
            ),
            None,
        )
        verdicts.append(review.verdict if review else "")
        notes.append(review.note if review else "")
        reviews_of.append(review.data_source if review else "")
    return flags.assign(verdict=verdicts, note=notes, review_of=reviews_of)[
        COLUMNS
    ]


def _table(rows: list[list[str]], header: list[str]) -> str:
    """
    Format rows as a Markdown table.

    Parameters
    ----------
    rows : list[list[str]]
        The rows.
    header : list[str]
        The names of the columns.

    Returns
    -------
    str
        The table, or "None." without rows.
    """
    if not rows:
        return "None.\n"
    lines = ["| " + " | ".join(header) + " |"]
    lines.append("|" + "---|" * len(header))
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def _format_report(
    flags: pd.DataFrame, unmatched: list[Review], checked_at: datetime.datetime
) -> str:
    """
    Format the flags and their reviews as a Markdown text.

    Parameters
    ----------
    flags : pandas.DataFrame
        The flags, with their reviews.
    unmatched : list[Review]
        The reviews that match no flag.
    checked_at : datetime.datetime
        The time of the report.

    Returns
    -------
    str
        The report.
    """
    keys = ["data_source", "code", "flag"]
    combined = flags[flags["data_source"] == COMBINED]
    flags = flags[flags["data_source"] != COMBINED]
    not_reviewed = flags[flags["verdict"] == ""]
    reviewed = flags[flags["verdict"] != ""]
    summary = [
        [
            str(flag),
            str(len(group)),
            str(group[["data_source", "code"]].drop_duplicates().shape[0]),
            str((group["verdict"] == "").sum()),
        ]
        for flag, group in flags.groupby("flag")
    ]
    not_reviewed_rows = [
        [*map(str, key), ", ".join(group["period"])]
        for key, group in not_reviewed.groupby(keys)
    ]
    reviewed_rows = [
        [*map(str, key[:3]), ", ".join(group["period"]), *map(str, key[3:])]
        for key, group in reviewed.groupby([*keys, "verdict", "note"])
    ]
    unmatched_rows = [
        [review.data_source, review.code, review.flag, review.verdict]
        for review in unmatched
    ]
    series = flags[["data_source", "code"]].drop_duplicates().shape[0]
    return (
        "# Flags of the electricity demand\n\n"
        f"Report of {checked_at:%Y-%m-%d %H:%M} UTC: {len(flags)} flags of "
        f"{series} series, {len(not_reviewed)} not reviewed. The flags "
        "and their reasons are in `demandcast/cleaning/flags.py`, and the "
        "reviews in `demandcast/checks/reviewed_flags.yaml`.\n\n"
        "## Summary\n\n"
        + _table(summary, ["Flag", "Flags", "Series", "Not reviewed"])
        + "\n## Not reviewed\n\n"
        + _table(not_reviewed_rows, ["Data source", "Code", "Flag", "Periods"])
        + "\n## Reviewed\n\n"
        + _table(
            reviewed_rows,
            ["Data source", "Code", "Flag", "Periods", "Verdict", "Note"],
        )
        + "\n## Reviews without flags\n\n"
        "These reviews match no flag any more, such as when the error has "
        "been fixed, and can be removed.\n\n"
        + _table(unmatched_rows, ["Data source", "Code", "Flag", "Verdict"])
        + _format_combined_report(combined)
    )


def _format_combined_report(combined: pd.DataFrame) -> str:
    """
    Format the flags of the combined electricity demand.

    Parameters
    ----------
    combined : pandas.DataFrame
        The combined flags, with their reviews.

    Returns
    -------
    str
        The section of the report on the combined flags.
    """
    keys = ["code", "flag"]
    own = combined[combined["review_of"] == COMBINED]
    not_reviewed = combined[combined["verdict"] == ""]
    inherited = len(combined) - len(own) - len(not_reviewed)
    not_reviewed_rows = [
        [
            *map(str, key),
            ", ".join(group["period"]),
            ", ".join(group["main_source"].unique()),
        ]
        for key, group in not_reviewed.groupby(keys)
    ]
    own_rows = [
        [*map(str, key[:2]), ", ".join(group["period"]), *map(str, key[2:])]
        for key, group in own.groupby([*keys, "verdict", "note"])
    ]
    return (
        "\n## Combined series\n\n"
        f"{len(combined)} flags of {combined['code'].nunique()} codes: "
        f"{inherited} with the review of the same flag of their main "
        f"source, {len(own)} with their own review, and "
        f"{len(not_reviewed)} not reviewed. The main source of a flag is "
        "the data source of most of the hours of its period. A flag that "
        "its main source does not have comes from the combination, such "
        "as a step where a source fills the hours after another, and is "
        'reviewed with the data source "combined".\n\n'
        "### Not reviewed\n\n"
        + _table(not_reviewed_rows, ["Code", "Flag", "Periods", "Main source"])
        + "\n### With their own review\n\n"
        + _table(own_rows, ["Code", "Flag", "Periods", "Verdict", "Note"])
    )


def run_check() -> pd.DataFrame:
    """
    Gather the flags of the cleaned electricity demand into a report.

    Returns
    -------
    pandas.DataFrame
        The flags, with the verdicts and notes of their reviews.
    """
    reviews = read_reviews()
    flags = _add_reviews(read_flags(), reviews)
    unmatched = [
        review
        for review in reviews
        if not any(
            review.matches(*map(str, row))
            for row in flags[
                ["data_source", "code", "flag", "period"]
            ].itertuples(index=False)
        )
    ]

    checks_directory = utils.paths.get_results_folder("checks")
    os.makedirs(checks_directory, exist_ok=True)
    file_path = os.path.join(checks_directory, REPORT_NAME)
    flags.to_csv(file_path + ".csv", index=False)
    checked_at = datetime.datetime.now(datetime.UTC)
    with open(file_path + ".md", "w", encoding="utf-8") as file:
        file.write(_format_report(flags, unmatched, checked_at))

    logging.info(
        f"{len(flags)} flags, {(flags['verdict'] == '').sum()} not reviewed, "
        f"and {len(unmatched)} reviews without flags. Report saved to "
        f"{file_path}.csv and {file_path}.md."
    )
    return flags

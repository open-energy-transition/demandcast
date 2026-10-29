"""
License: AGPL-3.0.

Description:

    This module combines the cleaned electricity demand of all the data
    sources of a country or subdivision into one hourly series, with the
    data source of each hour, and saves it with a table of the sources
    and of what was done with each of them, and with its flags (see
    cleaning/flags.py).

    The sources are ranked, from the best:

    1. Those whose data covers the area of the shape of the code before
       those that cover only part of it (same_area false in the yaml
       file of the data source, such as CAISO for California).
    2. The data of the system operators before the data that a source
       republishes (compiled in the yaml file of the data source, such
       as the EIA): a copy cannot count more than the original, even
       when its definition is less known, as for the CCEI, whose
       definition differs by province.
    3. By the definition of their demand, on average over their hours:
       the gross demand (with the embedded generation included or
       added) before the one that counts only part of it, before the
       one whose embedded generation is unknown, before the net demand.
       The seasons flagged with a midday dip that the reviews find to be
       net demand count as net.
    4. The longer data before the shorter.

    The ranking is of whole sources, not hour by hour: a source keeps
    its rank in all its hours, so that the series does not switch
    between sources at each change of their definitions. The hours of
    the seasons whose flags the reviews find to be errors of the source
    or of its reading are taken out of their source, and come after all
    the sources: they fill only the hours that no source gives.

    The best source gives all its hours. Each of the others, in order,
    fills only the hours outside the range of the hours already combined
    and the gaps of at least a day in it, so that the series does not
    switch between sources at each missing hour. A source fills them
    only if it gives the same quantity as the hours already combined:
    over its common hours with them, the median of its ratio to them
    must be within 2% of 1, and 90% of the ratios within 5% of 1. With
    less than 7 days of common hours, such as for a source that ends
    before the other starts, the ratios cannot show whether it gives the
    same quantity: it fills the hours, as unverified, and the step
    between them shows in the flags of the annual change of the combined
    series. Even then, with at least a day of common hours, a source
    whose median ratio is more than 10% from 1 gives another quantity,
    such as twice the demand, and does not fill them.

    The combined series keeps all its hours, and tells whether each can
    be used to train the models ("Eligible"): the hours of the errors of
    their source are not, so that the training data has no error that a
    review has found.

    A combined series records the fingerprint of what decided it: the
    version of the combination (COMBINATION_VERSION), the reviews of the
    flags and the YAML files of its data sources. A series without it,
    with another one, or older than the cleaned data of one of its data
    sources is not current, and the assembly of the training data
    combines it again from the cleaned data (see
    ensure_current_combination), so that a series made by older code or
    before a review, such as one copied from a bucket, does not become
    training data.
"""

import hashlib
import logging
import os

import numpy as np
import pandas as pd

import checks.flags
import cleaning.flags
import utils.data_sources
import utils.paths

# The rank of the definitions of the embedded generation.
EMBEDDED_GENERATION_RANKS = {
    "included": 0,
    "added": 0,
    "partial": 1,
    "unknown": 2,
    "excluded": 3,
}

# The rank of the hours of the seasons that the reviews of the flags
# find to be net demand, or errors.
NET_DEMAND_RANK = 3
ERROR_RANK = 4
ERROR_VERDICTS = ("source_error", "reading_error")

# The shortest gap that another source fills.
SHORTEST_GAP = pd.Timedelta(hours=24)

# The common hours needed to compare two sources, and the largest
# differences of their ratio from 1, for its median and for 90% of it.
SHORTEST_OVERLAP_HOURS = 7 * 24
LARGEST_MEDIAN_DIFFERENCE = 0.02
LARGEST_SPREAD = 0.05

# The common hours that show a different quantity, and the largest
# difference of the median of the ratio from 1 below the shortest
# overlap.
SHORTEST_CHECKED_OVERLAP_HOURS = 24
LARGEST_UNVERIFIED_MEDIAN_DIFFERENCE = 0.10

# The version of the combination, which changes when the code changes
# what a combined series is, such as its columns or its rules.
COMBINATION_VERSION = 1

# The key of the attributes of a combined series with its fingerprint.
FINGERPRINT_KEY = "demandcast_combination"

# The columns of the table of the sources.
SOURCE_COLUMNS = [
    "data_source",
    "rank",
    "hours",
    "first",
    "last",
    "common_hours",
    "median_ratio",
    "low_ratio",
    "high_ratio",
    "used_hours",
    "decision",
]


def _read_cleaned_data(code: str) -> dict[str, pd.Series]:
    """
    Read the cleaned electricity demand of all the sources of a code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    dict[str, pandas.Series]
        The hourly electricity demand in MW, at the ends of the hours in
        UTC, of each data source that has cleaned data of the code.
    """
    cleaned = {}
    for data_source in (
        utils.data_sources.get_electricity_demand_data_sources_containing_code(
            code
        )
    ):
        file_path = utils.paths.get_electricity_demand_file(
            "cleaned", code, data_source
        )
        if os.path.exists(file_path):
            values = pd.read_parquet(file_path)["Load (MW)"].sort_index()
            if not values.empty:
                cleaned[data_source] = values
    return cleaned


def _get_definition_ranks(
    code: str, data_source: str, times: pd.DatetimeIndex
) -> np.ndarray:
    """
    Get the rank of the definition of the demand of a source, by hour.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    times : pandas.DatetimeIndex
        The hours of its data, in UTC.

    Returns
    -------
    numpy.ndarray
        The rank of each hour: 0 for the gross demand, 1 for the
        embedded generation counted in part, 2 for unknown embedded
        generation, 3 for the net demand and 4 for the errors.
    """
    # The rank of the definition of each period.
    ranks = np.zeros(len(times), dtype=int)
    dates = times.normalize()
    for period in utils.data_sources.read_definition(data_source):
        started = dates >= pd.Timestamp(period.start_date)
        ranks[started] = EMBEDDED_GENERATION_RANKS[period.embedded_generation]
    first_period = utils.data_sources.read_definition(data_source)[0]
    ranks[dates < pd.Timestamp(first_period.start_date)] = (
        EMBEDDED_GENERATION_RANKS[first_period.embedded_generation]
    )

    # The seasons of the flags that the reviews find to be net demand,
    # or errors.
    flags_path = utils.paths.get_electricity_demand_file(
        "cleaned", code, data_source
    ).removesuffix(".parquet")
    flags_path += "_flags.parquet"
    if os.path.exists(flags_path):
        reviews = checks.flags.read_reviews()
        flags = pd.read_parquet(flags_path)
        for start, end, flag, period in zip(
            flags["start"].tolist(),
            flags["end"].tolist(),
            flags["flag"].tolist(),
            flags["period"].tolist(),
            strict=True,
        ):
            review = next(
                (
                    review
                    for review in reviews
                    if review.matches(
                        data_source, code, str(flag), str(period)
                    )
                ),
                None,
            )
            if review is None:
                continue
            rank = (
                ERROR_RANK
                if review.verdict in ERROR_VERDICTS
                else NET_DEMAND_RANK
                if review.verdict == "net_demand"
                else None
            )
            if rank is not None:
                flagged = (dates >= pd.Timestamp(start)) & (
                    dates <= pd.Timestamp(end)
                )
                ranks[flagged] = np.maximum(ranks[flagged], rank)

    return ranks


def _rank_data_sources(
    code: str, cleaned: dict[str, pd.Series], ranks: dict[str, np.ndarray]
) -> list[str]:
    """
    Rank the data sources of a code, from the best.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    cleaned : dict[str, pandas.Series]
        The cleaned electricity demand of each data source.
    ranks : dict[str, numpy.ndarray]
        The rank of the definition of each hour of each data source.

    Returns
    -------
    list[str]
        The data sources, from the best.
    """

    def key(data_source: str) -> tuple[bool, bool, float, int]:
        entity = next(
            entity
            for entity in utils.data_sources.read_entities(data_source)
            if entity.code == code
        )
        return (
            not entity.same_area,
            utils.data_sources.read_compiled(data_source),
            float(ranks[data_source].mean()),
            -len(cleaned[data_source]),
        )

    return sorted(cleaned, key=key)


def _compare(values: pd.Series, combined: pd.Series) -> dict[str, float]:
    """
    Compare the values of a source with those already combined.

    Parameters
    ----------
    values : pandas.Series
        The values of the source.
    combined : pandas.Series
        The values already combined.

    Returns
    -------
    dict[str, float]
        The common hours ("common_hours"), and the median and the 5th
        and 95th percentiles of the ratio of the values of the source to
        the combined ones in them ("median_ratio", "low_ratio" and
        "high_ratio"), not numbers without common hours.
    """
    common = values.index.intersection(combined.index)
    ratios = values[common] / combined[common]
    if ratios.empty:
        return {
            "common_hours": 0,
            "median_ratio": np.nan,
            "low_ratio": np.nan,
            "high_ratio": np.nan,
        }
    return {
        "common_hours": len(common),
        "median_ratio": float(ratios.median()),
        "low_ratio": float(ratios.quantile(0.05)),
        "high_ratio": float(ratios.quantile(0.95)),
    }


def _is_same_quantity(comparison: dict[str, float]) -> bool:
    """
    Check whether a source gives the same quantity as the combined data.

    Parameters
    ----------
    comparison : dict[str, float]
        The comparison of the source with the combined data.

    Returns
    -------
    bool
        Whether the ratios of the common hours are close to 1.
    """
    return (
        abs(comparison["median_ratio"] - 1) <= LARGEST_MEDIAN_DIFFERENCE
        and comparison["low_ratio"] >= 1 - LARGEST_SPREAD
        and comparison["high_ratio"] <= 1 + LARGEST_SPREAD
    )


def _is_other_quantity(comparison: dict[str, float]) -> bool:
    """
    Check whether a source gives another quantity than the combined one.

    Parameters
    ----------
    comparison : dict[str, float]
        The comparison of the source with the combined data.

    Returns
    -------
    bool
        Whether the ratios of enough common hours are not close to 1,
        or, with fewer common hours, their median is far from 1.
    """
    if comparison["common_hours"] >= SHORTEST_OVERLAP_HOURS:
        return not _is_same_quantity(comparison)
    return (
        comparison["common_hours"] >= SHORTEST_CHECKED_OVERLAP_HOURS
        and abs(comparison["median_ratio"] - 1)
        > LARGEST_UNVERIFIED_MEDIAN_DIFFERENCE
    )


def _get_hours_to_fill(
    combined: pd.Series, hours: pd.DatetimeIndex
) -> pd.DatetimeIndex:
    """
    Get the hours that another source can fill.

    Parameters
    ----------
    combined : pandas.Series
        The values already combined.
    hours : pandas.DatetimeIndex
        The hours of the other source.

    Returns
    -------
    pandas.DatetimeIndex
        The hours of the other source outside the range of the combined
        values, or in their gaps of at least a day.
    """
    missing = hours.difference(pd.DatetimeIndex(combined.index))
    if missing.empty or combined.empty:
        return missing
    inside = (missing > combined.index[0]) & (missing < combined.index[-1])

    # The gap of each missing hour inside the range: the combined hours
    # before and after it.
    positions = combined.index.searchsorted(missing[inside])
    gaps = combined.index[positions] - combined.index[positions - 1]
    long_gap = np.zeros(len(missing), dtype=bool)
    long_gap[inside] = gaps > SHORTEST_GAP
    return missing[~inside | long_gap]


def _combine(
    cleaned: dict[str, pd.Series],
    ranked: list[str],
    errors: dict[str, pd.Series] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combine the electricity demand of the ranked data sources.

    Parameters
    ----------
    cleaned : dict[str, pandas.Series]
        The cleaned electricity demand of each data source.
    ranked : list[str]
        The data sources, from the best.
    errors : dict[str, pandas.Series] | None, optional
        The hours of each data source that the reviews of its flags find
        to be errors, taken out of its cleaned demand.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame]
        The combined electricity demand ("Load (MW)"), the data source
        of each hour ("Source") and whether it can be used for training
        ("Eligible"), and the table of the sources.
    """
    # The data sources from the best, and then their errors.
    entries = [
        (data_source, cleaned[data_source], False) for data_source in ranked
    ]
    entries += [
        (data_source, values, True)
        for data_source, values in (errors or {}).items()
        if not values.empty
    ]

    combined = pd.Series(dtype="float64")
    sources = pd.Series(dtype="string")
    eligible = pd.Series(dtype="bool")
    rows = []
    for rank, (data_source, values, are_errors) in enumerate(entries, start=1):
        comparison = _compare(values, combined)
        if combined.empty:
            used, decision = pd.DatetimeIndex(values.index), "best"
        elif not are_errors and _is_other_quantity(comparison):
            used, decision = pd.DatetimeIndex([]), "different quantity"
        else:
            used = _get_hours_to_fill(combined, pd.DatetimeIndex(values.index))
            decision = (
                "not needed"
                if used.empty
                else "fills"
                if comparison["common_hours"] >= SHORTEST_OVERLAP_HOURS
                else "fills unverified"
            )
        if are_errors:
            decision = "reviewed errors"
        if len(used):
            combined = pd.concat([combined, values[used]]).sort_index()
            sources = pd.concat(
                [sources, pd.Series(data_source, index=used, dtype="string")]
            ).sort_index()
            eligible = pd.concat(
                [eligible, pd.Series(not are_errors, index=used, dtype="bool")]
            ).sort_index()
        rows.append(
            {
                "data_source": data_source,
                "rank": rank,
                "hours": len(values),
                "first": values.index[0],
                "last": values.index[-1],
                **comparison,
                "used_hours": len(used),
                "decision": decision,
            }
        )

    combined_data = pd.DataFrame(
        {"Load (MW)": combined, "Source": sources, "Eligible": eligible}
    )
    combined_data.index.name = entries[0][1].index.name
    return combined_data, pd.DataFrame(rows, columns=SOURCE_COLUMNS)


def get_fingerprint(code: str) -> str:
    """
    Get the fingerprint of what decides the combined series of a code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    str
        The SHA-256 checksum of the version of the combination, of the
        reviews of the flags and of the YAML files of the data sources
        of the code.
    """
    checksum = hashlib.sha256(f"version {COMBINATION_VERSION}".encode())
    file_paths = [
        os.path.join(
            utils.paths.CHECKS_FOLDER, checks.flags.REVIEWS_NAME + ".yaml"
        )
    ] + [
        os.path.join(utils.paths.DATA_SOURCES_FOLDER, f"{data_source}.yaml")
        for data_source in sorted(
            utils.data_sources.get_electricity_demand_data_sources_containing_code(
                code
            )
        )
    ]
    for file_path in file_paths:
        with open(file_path, "rb") as file:
            checksum.update(file.read())
    return checksum.hexdigest()


def is_current(code: str) -> bool:
    """
    Check whether the combined series of a code is current.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    bool
        Whether the combined series exists, has the column "Eligible"
        and the current fingerprint, and is not older than the cleaned
        data of its data sources.
    """
    file_path = utils.paths.get_electricity_demand_file("combined", code)
    if not os.path.exists(file_path):
        return False
    combined = pd.read_parquet(file_path)
    if "Eligible" not in combined.columns or combined.attrs.get(
        FINGERPRINT_KEY
    ) != get_fingerprint(code):
        return False
    written = os.path.getmtime(file_path)
    return all(
        os.path.getmtime(cleaned_path) <= written
        for data_source in (
            utils.data_sources.get_electricity_demand_data_sources_containing_code(
                code
            )
        )
        if os.path.exists(
            cleaned_path := utils.paths.get_electricity_demand_file(
                "cleaned", code, data_source
            )
        )
    )


def ensure_current_combination(code: str) -> None:
    """
    Combine the electricity demand of a code again if it is not current.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    """
    if is_current(code):
        return
    logging.info(
        f"The combined electricity demand of {code} is not current, such "
        "as after a change of the reviews of the flags or of the data "
        "sources, so it is combined again from the cleaned data."
    )
    combine_data(code)


def combine_data(code: str) -> pd.DataFrame | None:
    """
    Combine and save the cleaned electricity demand of a code.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    pandas.DataFrame | None
        The hourly electricity demand in MW ("Load (MW)"), its data
        source ("Source") and whether it can be used for training
        ("Eligible"), at the ends of the hours in UTC, or None if no
        data source has cleaned data of the code.
    """
    cleaned = _read_cleaned_data(code)
    if not cleaned:
        logging.warning(f"No data source has cleaned data of {code}.")
        return None

    # Take the hours of the seasons reviewed as errors out of their
    # source, to fill only the hours that no source gives.
    ranks = {
        data_source: _get_definition_ranks(
            code, data_source, pd.DatetimeIndex(values.index)
        )
        for data_source, values in cleaned.items()
    }
    errors = {
        data_source: values[ranks[data_source] == ERROR_RANK]
        for data_source, values in cleaned.items()
    }
    sound = {
        data_source: values[ranks[data_source] != ERROR_RANK]
        for data_source, values in cleaned.items()
    }
    sound_ranks = {
        data_source: ranks[data_source][ranks[data_source] != ERROR_RANK]
        for data_source in cleaned
    }
    ranked = _rank_data_sources(
        code,
        {source: values for source, values in sound.items() if len(values)},
        sound_ranks,
    )
    combined, sources = _combine(sound, ranked, errors)
    combined.attrs[FINGERPRINT_KEY] = get_fingerprint(code)

    file_path = utils.paths.get_electricity_demand_file("combined", code)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    combined.to_parquet(file_path)
    sources.to_parquet(file_path.removesuffix(".parquet") + "_sources.parquet")
    cleaning.flags.flag_data(code)
    for row in sources.itertuples():
        logging.info(
            f"Combined electricity demand of {code}: {row.data_source} "
            f"({row.decision}, {row.used_hours} of {row.hours} hours)."
        )

    return combined


def combine_all_data() -> list[str]:
    """
    Combine the cleaned electricity demand of all the codes.

    Returns
    -------
    list[str]
        The codes whose electricity demand was combined.
    """
    combined = [
        code
        for code in utils.data_sources.read_all_codes_with_electricity_demand_data()
        if combine_data(code) is not None
    ]
    logging.info(f"Combined the electricity demand of {len(combined)} codes.")
    return combined

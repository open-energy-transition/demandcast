"""
License: AGPL-3.0.

Description:

    This module combines the cleaned electricity demand of all the data
    sources of a country or subdivision into one hourly series, with the
    data source of each hour, and saves it with a table of the sources
    and of what was done with each of them.

    The sources are ranked, from the best:

    1. Those whose data covers the area of the shape of the code before
       those that cover only part of it (same_area false in the yaml
       file of the data source, such as CAISO for California).
    2. The data of the system operators before the data that a source
       republishes (compiled in the yaml file of the data source, such
       as the EIA): a copy cannot count more than the original, even
       when its definition is less known, as for the CCEI, whose
       definition differs by province.
    3. By the definition of their demand, hour by hour: the gross demand
       (with the embedded generation included or added) before the one
       whose embedded generation is unknown, before the net demand. The
       seasons flagged with a midday dip that the reviews find to be net
       demand count as net, and those that they find to be errors of the
       source or of its reading come last.
    4. The longer data before the shorter.

    The best source gives all its hours. Each of the others, in order,
    fills only the hours outside the range of the hours already combined
    and the gaps of at least a day in it, so that the series does not
    switch between sources at each missing hour. A source fills them
    only if it gives the same quantity as the hours already combined:
    over at least 30 days of common hours, the median of its ratio to
    them must be within 2% of 1, and 90% of the ratios within 5% of 1.
    A source without enough common hours, such as one that ends before
    the other starts, fills them too, and the step between them shows in
    the flags of the annual change of the combined series.
"""

import logging
import os

import checks.flags
import numpy as np
import pandas as pd
import utils.config
import utils.entities

# The rank of the definitions of the embedded generation.
EMBEDDED_GENERATION_RANKS = {
    "included": 0,
    "added": 0,
    "unknown": 1,
    "excluded": 2,
}

# The rank of the hours of the seasons that the reviews of the flags
# find to be net demand, or errors.
NET_DEMAND_RANK = 2
ERROR_RANK = 3
ERROR_VERDICTS = ("source_error", "reading_error")

# The shortest gap that another source fills.
SHORTEST_GAP = pd.Timedelta(hours=24)

# The common hours needed to compare two sources, and the largest
# differences of their ratio from 1, for its median and for 90% of it.
SHORTEST_OVERLAP_HOURS = 30 * 24
LARGEST_MEDIAN_DIFFERENCE = 0.02
LARGEST_SPREAD = 0.05

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
    for (
        data_source
    ) in utils.entities.get_electricity_demand_data_sources_containing_code(
        code
    ):
        file_path = utils.config.get_electricity_demand_file_path(
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
        The rank of each hour: 0 for the gross demand, 1 for unknown
        embedded generation, 2 for the net demand and 3 for the errors.
    """
    # The rank of the definition of each period.
    ranks = np.zeros(len(times), dtype=int)
    dates = times.normalize()
    for period in utils.entities.read_definition(data_source):
        started = dates >= pd.Timestamp(period.start_date)
        ranks[started] = EMBEDDED_GENERATION_RANKS[period.embedded_generation]
    first_period = utils.entities.read_definition(data_source)[0]
    ranks[dates < pd.Timestamp(first_period.start_date)] = (
        EMBEDDED_GENERATION_RANKS[first_period.embedded_generation]
    )

    # The seasons of the flags that the reviews find to be net demand,
    # or errors.
    flags_path = utils.config.get_electricity_demand_file_path(
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


def _rank_data_sources(code: str, cleaned: dict[str, pd.Series]) -> list[str]:
    """
    Rank the data sources of a code, from the best.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    cleaned : dict[str, pandas.Series]
        The cleaned electricity demand of each data source.

    Returns
    -------
    list[str]
        The data sources, from the best.
    """

    def key(data_source: str) -> tuple[bool, bool, float, int]:
        entity = next(
            entity
            for entity in utils.entities.read_entities(data_source)
            if entity.code == code
        )
        times = pd.DatetimeIndex(cleaned[data_source].index)
        return (
            not entity.same_area,
            utils.entities.read_compiled(data_source),
            float(_get_definition_ranks(code, data_source, times).mean()),
            -len(times),
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
        Whether the source has too few common hours to compare, or the
        ratios of the common hours are close to 1.
    """
    if comparison["common_hours"] < SHORTEST_OVERLAP_HOURS:
        return True
    return (
        abs(comparison["median_ratio"] - 1) <= LARGEST_MEDIAN_DIFFERENCE
        and comparison["low_ratio"] >= 1 - LARGEST_SPREAD
        and comparison["high_ratio"] <= 1 + LARGEST_SPREAD
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
    cleaned: dict[str, pd.Series], ranked: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Combine the electricity demand of the ranked data sources.

    Parameters
    ----------
    cleaned : dict[str, pandas.Series]
        The cleaned electricity demand of each data source.
    ranked : list[str]
        The data sources, from the best.

    Returns
    -------
    tuple[pandas.DataFrame, pandas.DataFrame]
        The combined electricity demand ("Load (MW)") and the data
        source of each hour ("Source"), and the table of the sources.
    """
    best = ranked[0]
    combined = cleaned[best]
    sources = pd.Series(best, index=combined.index)
    rows = [
        {
            "data_source": best,
            "rank": 1,
            "hours": len(combined),
            "first": combined.index[0],
            "last": combined.index[-1],
            "common_hours": 0,
            "median_ratio": np.nan,
            "low_ratio": np.nan,
            "high_ratio": np.nan,
            "used_hours": len(combined),
            "decision": "best",
        }
    ]

    for rank, data_source in enumerate(ranked[1:], start=2):
        values = cleaned[data_source]
        comparison = _compare(values, combined)
        used = pd.DatetimeIndex([])
        if not _is_same_quantity(comparison):
            decision = "different quantity"
        else:
            used = _get_hours_to_fill(combined, pd.DatetimeIndex(values.index))
            decision = "fills" if len(used) else "not needed"
        if len(used):
            combined = pd.concat([combined, values[used]]).sort_index()
            sources = pd.concat(
                [sources, pd.Series(data_source, index=used)]
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
        {"Load (MW)": combined, "Source": sources.astype("string")}
    )
    combined_data.index.name = cleaned[best].index.name
    return combined_data, pd.DataFrame(rows, columns=SOURCE_COLUMNS)


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
        The hourly electricity demand in MW ("Load (MW)") and its data
        source ("Source"), at the ends of the hours in UTC, or None if
        no data source has cleaned data of the code.
    """
    cleaned = _read_cleaned_data(code)
    if not cleaned:
        logging.warning(f"No data source has cleaned data of {code}.")
        return None

    ranked = _rank_data_sources(code, cleaned)
    combined, sources = _combine(cleaned, ranked)

    file_path = utils.config.get_electricity_demand_file_path("combined", code)
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    combined.to_parquet(file_path)
    sources.to_parquet(file_path.removesuffix(".parquet") + "_sources.parquet")
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
        for code in utils.entities.read_all_codes_with_electricity_demand_data()
        if combine_data(code) is not None
    ]
    logging.info(f"Combined the electricity demand of {len(combined)} codes.")
    return combined

"""
License: AGPL-3.0.

Description:

    This module flags the changes in the cleaned electricity demand of a
    data source that need a review, without removing any value, and
    saves them next to the cleaned electricity demand. The flags are:

    - midday_dip: the demand around solar noon falls, compared with the
      morning and afternoon, below what it was in the same quarter of
      earlier years. This is the sign of a demand that leaves out the
      generation embedded in the distribution networks, such as rooftop
      solar, whose growth over the years hides more and more of the
      demand at midday. DemandCast models the gross demand, with the
      demand that this generation supplies, so the flag marks the series
      that do not have it, or a change of what a series has.

    The midday index of a day is the mean demand of the three hours
    around solar noon (10:30 to 13:30 in solar time, from the longitude
    of the country or subdivision), divided by the mean of the two hours
    from 7:00 and the two hours from 15:00. Its median over the days of
    a quarter (December to February, March to May, June to August and
    September to November) is compared with the highest median of the
    same quarter in the earlier years, since the sunny season is not
    the same everywhere. The quarters with fewer than 60 days are left
    out. A drop of more than 0.05 is flagged: the demand of a system
    without solar keeps its midday index within about 0.02 from year to
    year, while the national demand of Great Britain, without the
    embedded solar, drops from about 1.02 in 2011 to 0.87 in 2026 in
    summer. The flag does not prove that solar is missing: the index
    also drops when the demand changes at midday, such as during the
    lockdowns of 2020, and it cannot see the solar that was already
    there when the series starts.
"""

import logging
import os

import pandas as pd
import utils.config
import utils.shapes

# The hours of the midday and of the morning and afternoon around it,
# from and to, in solar time.
MIDDAY_HOURS = (10.5, 13.5)
MORNING_HOURS = (7.0, 9.0)
AFTERNOON_HOURS = (15.0, 17.0)

# The days that a quarter needs, and the drop of the midday index that
# is flagged.
MIN_DAYS_OF_QUARTER = 60
MIDDAY_DIP_DROP = 0.05

# The names of the quarters, from December to February.
QUARTERS = ["DJF", "MAM", "JJA", "SON"]


def _get_longitude(code: str) -> float:
    """
    Get the longitude of a country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.

    Returns
    -------
    float
        The longitude of a point inside its shape, in degrees.
    """
    shape = utils.shapes.get_entity_shape(code)
    return float(shape.union_all().representative_point().x)


def _get_midday_index(cleaned: pd.Series, longitude: float) -> pd.Series:
    """
    Get the midday index of each day.

    Parameters
    ----------
    cleaned : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    longitude : float
        The longitude of the country or subdivision.

    Returns
    -------
    pandas.Series
        The midday index of each solar day that has all the hours of
        the midday, morning and afternoon.
    """
    # The middle of each hour in solar time.
    middle = (
        pd.DatetimeIndex(cleaned.index)
        - pd.Timedelta(minutes=30)
        + pd.to_timedelta(longitude / 15, unit="h")
    )
    hours = middle.hour + middle.minute / 60
    values = pd.Series(cleaned.to_numpy(), index=middle.normalize())

    def mean_of(window: tuple[float, float]) -> pd.Series:
        in_window = (hours >= window[0]) & (hours < window[1])
        days = values[in_window].groupby(level=0).agg(["mean", "count"])
        complete = days["count"] == window[1] - window[0]
        return days.loc[complete, "mean"]

    midday = mean_of(MIDDAY_HOURS)
    around = (mean_of(MORNING_HOURS) + mean_of(AFTERNOON_HOURS)) / 2
    return (midday / around).dropna()


def _get_quarterly_index(daily: pd.Series) -> pd.DataFrame:
    """
    Get the median midday index of each quarter of each year.

    Parameters
    ----------
    daily : pandas.Series
        The midday index of each day.

    Returns
    -------
    pandas.DataFrame
        The median by year (rows), in which December goes with the next
        year, and quarter (columns, from 0 for December to February),
        with no value for the quarters with too few days.
    """
    days = pd.DatetimeIndex(daily.index)
    frame = pd.DataFrame(
        {
            "year": days.year + (days.month == 12),
            "quarter": (days.month % 12) // 3,
            "index": daily.to_numpy(),
        }
    )
    medians = frame.pivot_table(
        index="year", columns="quarter", values="index", aggfunc="median"
    )
    counts = frame.pivot_table(
        index="year", columns="quarter", values="index", aggfunc="count"
    )
    medians = medians.where(counts >= MIN_DAYS_OF_QUARTER)
    return medians.reindex(columns=range(4))


def _find_midday_dips(cleaned: pd.Series, longitude: float) -> pd.DataFrame:
    """
    Find the quarters whose midday index drops below earlier years.

    Parameters
    ----------
    cleaned : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    longitude : float
        The longitude of the country or subdivision.

    Returns
    -------
    pandas.DataFrame
        The first and last day ("start" and "end"), the flag ("flag"),
        the name of the quarter ("period"), its midday index ("value")
        and the highest one of earlier years ("reference") of each
        flagged quarter.
    """
    quarterly = _get_quarterly_index(_get_midday_index(cleaned, longitude))
    rows = []
    for quarter in range(4):
        index = quarterly[quarter].dropna()
        reference = index.cummax().shift()
        for year in index.index[index < reference - MIDDAY_DIP_DROP]:
            start = pd.Timestamp(year=year, month=3 * quarter or 12, day=1)
            if quarter == 0:
                start -= pd.DateOffset(years=1)
            rows.append(
                {
                    "start": start,
                    "end": start + pd.DateOffset(months=3, days=-1),
                    "flag": "midday_dip",
                    "period": f"{QUARTERS[quarter]} {year}",
                    "value": index[year],
                    "reference": reference[year],
                }
            )
    columns = ["start", "end", "flag", "period", "value", "reference"]
    flags = pd.DataFrame(rows, columns=columns)
    return flags.sort_values("start", ignore_index=True)


def flag_data(code: str, data_source: str) -> pd.DataFrame:
    """
    Flag and save the changes of the cleaned electricity demand.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.

    Returns
    -------
    pandas.DataFrame
        The flagged periods.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, data_source
    )
    cleaned = pd.read_parquet(file_path)["Load (MW)"].sort_index()

    flags = _find_midday_dips(cleaned, _get_longitude(code))

    flags_path = file_path.removesuffix(".parquet") + "_flags.parquet"
    os.makedirs(os.path.dirname(flags_path), exist_ok=True)
    flags.to_parquet(flags_path)
    if not flags.empty:
        logging.warning(
            f"The electricity demand of {code} from {data_source} has a "
            f"midday dip in {', '.join(flags['period'])}, which can be "
            "embedded solar generation that it leaves out. See "
            f"{flags_path}."
        )

    return flags

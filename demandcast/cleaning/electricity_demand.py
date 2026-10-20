"""
License: AGPL-3.0.

Description:

    This module cleans the processed electricity demand of a data source
    for a country or subdivision, and saves it in the folder of cleaned
    electricity demand. The processed data is in MW, at the ends of the
    intervals of the data source in UTC, without missing or zero values
    or duplicated times, at the resolution of the data source.

    The cleaning removes the values that cannot be demand, by general
    rules of what errors look like rather than by the errors of
    particular data sources, at the resolution of the data source, in
    this order:

    - future: the times after the cleaning, which cannot have data.
    - non_positive: values of zero or less.
    - implausible: values above 3 times the median of the 30 days
      around them, such as errors of units.
    - frozen: the same value for 6 hours or more, which the demand of a
      system never keeps: a stuck reading or filled data.
    - copied_day: the days, in local time, whose values repeat those of
      an earlier day exactly, which the demand never does: copied data.
    - spike: a run of values that leaves the level of the values around
      it and comes back to it within 30 minutes. The values change by
      more than 20% below a resolution of 30 minutes, which the demand
      of a system does not do and come back, and by more than 50% at 30
      minutes or more, since the demand of a small system can change
      by 20% within an hour.
    - level_drop: a run of 14 days or more, in local time, whose mean is
      less than half the level of the same days of the two years before
      and after, the median of the 31 days around them in each year and
      then of the years: a part of the system left out, as in Albania
      from 2022-12-11 to 2023-12-04 and in the Netherlands from
      2014-10-20 to 2014-12-19, at about a quarter of their level.
      The level is computed again without the days found, so that an
      error of a year does not hide that of another. The lockdowns of
      2020, from 2020-03-15 to 2020-06-30, are left, since they halved
      the demand of some places, such as Dadra and Nagar Haveli and
      Daman and Diu.

    The values left are then averaged in each hour, at its end, if they
    cover at least half of the hour (low_coverage otherwise): each value
    covers the time since the value before it, at most its resolution.
    The resolution is that around each value, the median time between
    the 25 values around it, since it can change within a data source,
    such as from 30 to 5 minutes in the NEM of Australia in October
    2021. The removed values are saved next to the cleaned data, as the
    periods of each rule.
"""

import logging
import os

import numpy as np
import pandas as pd
import utils.config
import utils.entities

# The rules, in the order in which they are applied.
RULES = [
    "future",
    "non_positive",
    "implausible",
    "frozen",
    "copied_day",
    "spike",
    "level_drop",
    "low_coverage",
]

# The factor above the median of the days around a value that makes it
# implausible, and the days of the median.
IMPLAUSIBLE_FACTOR = 3
IMPLAUSIBLE_WINDOW = "30D"

# The duration of the same value that makes it frozen.
FROZEN_DURATION = pd.Timedelta(hours=6)

# The values that a day needs to be compared with the other days.
MIN_VALUES_OF_DAY = 12

# The longest duration of a spike, and the changes of a spike below and
# from a resolution of 30 minutes.
SPIKE_DURATION = pd.Timedelta(minutes=30)
SPIKE_CHANGE_SUBHOURLY = 0.2
SPIKE_CHANGE_HOURLY = 0.5

# The share of the level of the same days of the neighbouring years
# below which a run of days drops, the days of the run, the days around
# each day and the years around each year of the level, and the
# lockdowns of 2020, whose drops are real.
LEVEL_DROP_SHARE = 0.5
LEVEL_DROP_DAYS = 14
LEVEL_DAYS = 15
LEVEL_YEARS = (-2, -1, 1, 2)
LOCKDOWNS = (pd.Timestamp("2020-03-15"), pd.Timestamp("2020-06-30"))

# The share of an hour that its values need to cover for its average.
MIN_COVERAGE = 0.5

# The values around a value whose median time apart is its resolution.
RESOLUTION_VALUES = 25


def _get_resolutions(values: pd.Series) -> pd.Series:
    """
    Get the resolution of the time series around each value.

    The resolution of a data source can change, such as from 30 to 5
    minutes in the NEM of Australia in October 2021, or from an hour to
    15 minutes in some countries of ENTSO-E, so each value has the
    resolution of the values around it.

    Parameters
    ----------
    values : pandas.Series
        The time series.

    Returns
    -------
    pandas.Series
        The median time between the values around each value, or one
        hour if the time series has less than two values.
    """
    seconds = values.index.to_series().diff().dt.total_seconds()
    median = seconds.rolling(
        RESOLUTION_VALUES, center=True, min_periods=1
    ).median()
    return pd.to_timedelta(median.fillna(3600), unit="s")


def _find_implausible(values: pd.Series) -> pd.Series:
    """
    Find the values far above the median of the days around them.

    Parameters
    ----------
    values : pandas.Series
        The demand, with positive values.

    Returns
    -------
    pandas.Series
        True for the implausible values.
    """
    median = values.rolling(
        IMPLAUSIBLE_WINDOW, center=True, min_periods=1
    ).median()
    return values > IMPLAUSIBLE_FACTOR * median


def _find_frozen(values: pd.Series) -> pd.Series:
    """
    Find the runs of the same value that last too long.

    Parameters
    ----------
    values : pandas.Series
        The demand.

    Returns
    -------
    pandas.Series
        True for the values of the runs.
    """
    runs = (values != values.shift()).cumsum().to_numpy()
    times = values.index.to_series()
    duration = (
        times.groupby(runs).transform("max")
        - times.groupby(runs).transform("min")
        + _get_resolutions(values).groupby(runs).transform("first")
    )
    return pd.Series(
        (duration >= FROZEN_DURATION).to_numpy(), index=values.index
    )


def _find_copied_days(values: pd.Series, time_zone: str) -> pd.Series:
    """
    Find the days whose values repeat those of an earlier day.

    Parameters
    ----------
    values : pandas.Series
        The demand, at times in UTC.
    time_zone : str
        The time zone of the days.

    Returns
    -------
    pandas.Series
        True for the values of the copied days.
    """
    days = (
        pd.DatetimeIndex(values.index)
        .tz_localize("UTC")
        .tz_convert(time_zone)
        .date
    )
    seen = set()
    copied = set()
    for day, day_values in values.round(2).groupby(days):
        if len(day_values) < MIN_VALUES_OF_DAY:
            continue
        fingerprint = tuple(day_values.to_numpy())
        if fingerprint in seen:
            copied.add(day)
        else:
            seen.add(fingerprint)
    return pd.Series(pd.Index(days).isin(list(copied)), index=values.index)


def _find_spikes(values: pd.Series) -> pd.Series:
    """
    Find the short runs of values that leave the level around them.

    Parameters
    ----------
    values : pandas.Series
        The demand, without the values of the other rules.

    Returns
    -------
    pandas.Series
        True for the values of the spikes.
    """
    # The change and the longest run of a spike at the resolution of
    # each value.
    resolutions = _get_resolutions(values)
    changes = np.where(
        resolutions < pd.Timedelta(minutes=30),
        SPIKE_CHANGE_SUBHOURLY,
        SPIKE_CHANGE_HOURLY,
    )
    longest = np.clip(
        (SPIKE_DURATION / resolutions).to_numpy().astype(int), 1, 3
    )
    x = values.to_numpy()
    spikes = np.zeros(len(x), dtype=bool)
    for length in range(1, 4):
        if len(x) < length + 2:
            break
        # The values before and after the run, which must be at the same
        # level, and the run, which must leave it in one direction, at
        # the resolution of its first value.
        before = x[: len(x) - length - 1]
        after = x[length + 1 :]
        change = changes[1 : len(x) - length]
        level = (before + after) / 2
        same_level = (np.abs(before - after) < change / 2 * level) & (
            longest[1 : len(x) - length] >= length
        )
        up = np.ones(len(before), dtype=bool)
        down = np.ones(len(before), dtype=bool)
        for position in range(length):
            run = x[1 + position : len(x) - length + position]
            up &= (run > before * (1 + change)) & (run > after * (1 + change))
            down &= (run < before * (1 - change)) & (
                run < after * (1 - change)
            )
        found = same_level & (up | down)
        for position in range(length):
            spikes[1 + position : len(x) - length + position] |= found
    return pd.Series(spikes, index=values.index)


def _get_daily_ratios(daily: pd.Series, reference: pd.Series) -> pd.Series:
    """
    Get the ratio of each day to the level of the neighbouring years.

    Parameters
    ----------
    daily : pandas.Series
        The mean demand of each day.
    reference : pandas.Series
        The mean demand of the days that give the level.

    Returns
    -------
    pandas.Series
        The ratio of each day to the median, over the neighbouring
        years, of the median of the same days in each year.
    """
    days = reference.asfreq("D")
    levels = [
        days.shift(round(365.25 * years), freq="D")
        .rolling(2 * LEVEL_DAYS + 1, center=True, min_periods=LEVEL_DAYS)
        .median()
        for years in LEVEL_YEARS
    ]
    level = pd.concat(levels, axis=1).median(axis=1)
    return daily / level.reindex(daily.index)


def _find_drop_days(daily: pd.Series, reference: pd.Series) -> pd.Index:
    """
    Find the runs of days far below the level of the neighbouring years.

    Parameters
    ----------
    daily : pandas.Series
        The mean demand of each day.
    reference : pandas.Series
        The mean demand of the days that give the level.

    Returns
    -------
    pandas.Index
        The days of the runs.
    """
    ratios = _get_daily_ratios(daily, reference)
    in_lockdowns = (daily.index >= LOCKDOWNS[0]) & (
        daily.index <= LOCKDOWNS[1]
    )
    low = (ratios < LEVEL_DROP_SHARE) & ~in_lockdowns
    runs = (low != low.shift()).cumsum()
    lengths = low.groupby(runs).transform("size")
    return daily.index[low & (lengths >= LEVEL_DROP_DAYS)]


def _find_level_drops(values: pd.Series, time_zone: str) -> pd.Series:
    """
    Find the runs of days whose level drops far below the usual one.

    Parameters
    ----------
    values : pandas.Series
        The demand, without the values of the other rules, at times in
        UTC.
    time_zone : str
        The time zone of the days.

    Returns
    -------
    pandas.Series
        True for the values of the days of the drops.
    """
    days = (
        pd.DatetimeIndex(values.index)
        .tz_localize("UTC")
        .tz_convert(time_zone)
        .tz_localize(None)
        .normalize()
    )
    daily = values.groupby(days).mean()
    dropped = _find_drop_days(daily, daily)
    dropped = dropped.union(_find_drop_days(daily, daily.drop(dropped)))
    return pd.Series(days.isin(dropped), index=values.index)


def _find_removed(values: pd.Series, time_zone: str) -> pd.Series:
    """
    Find the rule that removes each value, if any.

    Parameters
    ----------
    values : pandas.Series
        The processed demand, at times in UTC.
    time_zone : str
        The time zone of the country or subdivision.

    Returns
    -------
    pandas.Series
        The first rule that removes each value, or an empty string.
    """
    removed = pd.Series("", index=values.index)

    def remove(rule: str, found: pd.Series) -> None:
        found = found.reindex(removed.index, fill_value=False)
        removed[found & (removed == "")] = rule

    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    remove("future", pd.Series(values.index > now, index=values.index))
    remove("non_positive", values <= 0)
    remove("implausible", _find_implausible(values[removed == ""]))
    remove("frozen", _find_frozen(values[removed == ""]))
    remove("copied_day", _find_copied_days(values[removed == ""], time_zone))
    remove("spike", _find_spikes(values[removed == ""]))
    remove("level_drop", _find_level_drops(values[removed == ""], time_zone))
    return removed


def _resample_hourly(values: pd.Series) -> pd.DataFrame:
    """
    Average the values of each hour, at its end.

    Each value covers the time since the value before it, at most its
    resolution, so that a value after a gap does not cover the gap.

    Parameters
    ----------
    values : pandas.Series
        The demand, at the resolution of the data source.

    Returns
    -------
    pandas.DataFrame
        The average ("Load (MW)"), the number of values ("count") and
        whether they cover enough of the hour ("covered"), for each hour
        with values.
    """
    resolutions = _get_resolutions(values)
    gaps = values.index.to_series().diff()
    covered = gaps.where(gaps < resolutions, resolutions).dt.total_seconds()
    hours = values.resample("1h", label="right", closed="right")
    hourly = pd.DataFrame({"Load (MW)": hours.mean(), "count": hours.count()})
    seconds = covered.resample("1h", label="right", closed="right").sum()
    hourly["covered"] = seconds >= MIN_COVERAGE * 3600
    return hourly[hourly["count"] > 0]


def _periods(times: pd.Series, rule: str, step: pd.Timedelta) -> pd.DataFrame:
    """
    Group the removed times of a rule into periods.

    Parameters
    ----------
    times : pandas.Series
        The removed times, in order.
    rule : str
        The rule.
    step : pandas.Timedelta
        The resolution of the times, within which they are consecutive.

    Returns
    -------
    pandas.DataFrame
        The first and last time ("start" and "end"), the rule ("rule")
        and the number of values ("values") of each period.
    """
    new_period = times.diff() > step
    periods = times.groupby(new_period.cumsum().to_numpy()).agg(
        ["min", "max", "count"]
    )
    return pd.DataFrame(
        {
            "start": pd.to_datetime(periods["min"].to_numpy()),
            "end": pd.to_datetime(periods["max"].to_numpy()),
            "rule": rule,
            "values": periods["count"].to_numpy(dtype="int64"),
        }
    )


def clean_data(code: str, data_source: str) -> pd.Series:
    """
    Clean and save the processed electricity demand of a data source.

    Parameters
    ----------
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.

    Returns
    -------
    pandas.Series
        The hourly electricity demand in MW, at the ends of the hours in
        UTC.
    """
    processed = pd.read_parquet(
        utils.config.get_electricity_demand_file_path(
            "processed", code, data_source
        )
    )["Load (MW)"].sort_index()
    step = (
        _get_resolutions(processed).max()
        if len(processed)
        else pd.Timedelta(hours=1)
    )

    # Remove the values of the rules, at the resolution of the data
    # source, and average the others in each hour.
    removed = _find_removed(processed, str(utils.entities.get_time_zone(code)))
    hourly = _resample_hourly(processed[removed == ""])
    cleaned = hourly.loc[hourly["covered"], "Load (MW)"]
    cleaned.index.name = processed.index.name
    cleaned.name = processed.name

    # Save the periods of the removed values, with the hours without
    # enough values.
    periods = [
        _periods(processed.index[removed == rule].to_series(), rule, step)
        for rule in RULES[:-1]
    ]
    periods.append(
        _periods(
            hourly.index[~hourly["covered"]].to_series(),
            "low_coverage",
            pd.Timedelta(hours=1),
        )
    )
    removed_periods = pd.concat(periods, ignore_index=True)

    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, data_source
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    cleaned.to_frame().to_parquet(file_path)
    removed_periods.to_parquet(
        file_path.removesuffix(".parquet") + "_removed.parquet"
    )
    logging.info(
        f"Saved the cleaned electricity demand to {file_path}, without "
        f"{int((removed != '').sum())} values of the data source and "
        f"{int((~hourly['covered']).sum())} hours with too few values."
    )

    return cleaned

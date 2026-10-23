"""
License: AGPL-3.0.

Description:

    This module cleans the processed electricity demand of a data source
    for a country or subdivision, and saves it in the folder of cleaned
    electricity demand. The processed data is in MW, at the ends of the
    intervals of the data source in UTC, without missing or zero values
    or duplicated times, at the resolution of the data source.

    Each value is taken as the average demand of its interval, which
    covers the time since the value before it, at most its resolution,
    so that a value after a gap does not cover the gap. The resolution
    is that around each value, the median time between the 25 values
    around it, since it can change within a data source, such as from 30
    to 5 minutes in the NEM of Australia in October 2021. The intervals
    are computed once, before any value is removed, so that removing a
    value does not lengthen the interval of the next one. A value
    follows the one before it if the time between them is its interval:
    the rules below that look at runs of values never bridge a gap,
    whether the data source misses the values or an earlier rule removed
    them. The day of
    a value is the local day of the start of its interval, so that the
    value at midnight belongs to the day that it ends, except for the
    copied days below.

    The cleaning screens the values with statistical rules, which look
    for what errors usually look like rather than for the errors of
    particular data sources, at the resolution of the data source. A
    value that a rule removes is unlikely to be the demand of the
    system, but can be, such as a rounded reading or the reconstructed
    profile of a data source. The rules, in this order, are:

    - future: the times after the cleaning, which cannot have data.
    - non_positive: values of zero or less.
    - implausible: values above 3 times the median of the 30 days
      around them, such as errors of units.
    - frozen: the same value for 6 hours or more, without gaps, which
      is more likely a stuck reading or filled data than the demand.
    - copied_day: the days, in local time, whose values repeat those of
      an earlier day at the same times of the day, once rounded to 0.01
      MW, which is more likely copied data than the demand. The days
      are taken from the starts of the intervals and from their ends,
      since a data source copies its days by whichever its times mark,
      such as Taipower on 2017-09-24 by the ends.
    - spike: a run of values that leaves the level of the values just
      before and after it, without gaps, and comes back to it within 30
      minutes. The values change by more than 20% below a resolution of
      30 minutes, which the demand of a system rarely does and comes
      back, and by more than 50% at 30 minutes or more, since the demand
      of a small system can change by 20% within an hour. At those
      resolutions, a single value is a run, although its interval lasts
      30 minutes or more.
    - level_drop: a run of 14 days or more, in local time, whose mean
      is less than half the level of the same days of the two years
      before and after, the median of the 31 days around them in each
      year and then of the years: a part of the system left out, as in
      Albania from 2022-12-11 to 2023-12-04 and in the Netherlands from
      2014-10-20 to 2014-12-19, at about a quarter of their level. A day
      whose values cover less than half of it has no mean. A run goes on
      over a gap of up to 3 such days, as within the drop of Albania,
      which misses a day every week or so, but not over a longer gap,
      and only its days with a mean count. The level is computed again
      without the days found, so that an error of a year does not hide
      that of another. The lockdowns of 2020, from 2020-03-15 to
      2020-06-30, are left, since they halved the demand of some places,
      such as Dadra and Nagar Haveli and Daman and Diu.

    The values left are then averaged in each hour, at its end, if they
    cover at least half of the hour (low_coverage otherwise). Each value
    counts for the part of its interval within the hour, so that the
    energy of the values is kept, and an interval that crosses the start
    of an hour, such as the hours of India, which end on the half hour
    in UTC, is shared between the two hours. The removed values are
    saved next to the cleaned data, as the periods of each rule.
"""

import logging
import os

import numpy as np
import pandas as pd
import utils.entities
import utils.paths

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

# The values that a day needs to be compared with the other days, and
# the decimals of the values compared, so that a copy converted between
# units still matches.
MIN_VALUES_OF_DAY = 12
COPIED_DAY_DECIMALS = 2

# The longest duration of a spike, and the changes of a spike below and
# from a resolution of 30 minutes.
SPIKE_DURATION = pd.Timedelta(minutes=30)
SPIKE_CHANGE_SUBHOURLY = 0.2
SPIKE_CHANGE_HOURLY = 0.5

# The share of the level of the same days of the neighbouring years
# below which a run of days drops, the days of the run, the longest gap
# of days without data within it, the days around each day and the
# years around each year of the level, and the lockdowns of 2020, whose
# drops are real.
LEVEL_DROP_SHARE = 0.5
LEVEL_DROP_DAYS = 14
LEVEL_DROP_GAP_DAYS = 3
LEVEL_DAYS = 15
LEVEL_YEARS = (-2, -1, 1, 2)
LOCKDOWNS = (pd.Timestamp("2020-03-15"), pd.Timestamp("2020-06-30"))

# The share of an hour, or of a day, that its values need to cover for
# its average.
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


def _get_durations(values: pd.Series, resolutions: pd.Series) -> pd.Series:
    """
    Get the duration of the interval of each value.

    Parameters
    ----------
    values : pandas.Series
        The whole time series, at the ends of the intervals, before any
        value is removed.
    resolutions : pandas.Series
        The resolution of each value.

    Returns
    -------
    pandas.Series
        The time since the value before it, at most its resolution.
    """
    gaps = values.index.to_series().diff()
    return gaps.where(gaps <= resolutions, resolutions)


def _get_intervals(
    values: pd.Series, durations: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """
    Get the interval of each value, and whether it follows the last one.

    Parameters
    ----------
    values : pandas.Series
        The time series, at the ends of the intervals, without the
        values removed so far.
    durations : pandas.Series
        The duration of the interval of each value of the whole time
        series, before any value is removed.

    Returns
    -------
    tuple[pandas.Series, pandas.Series]
        The duration of the interval of each value, and whether the
        value follows the one before it without a gap: whether the
        interval starts at the value before it.
    """
    durations = durations.reindex(values.index)
    follows = values.index.to_series().diff() <= durations
    return durations, follows


def _get_local_starts(
    values: pd.Series, durations: pd.Series, time_zone: str
) -> pd.DatetimeIndex:
    """
    Get the start of the interval of each value, in local time.

    Parameters
    ----------
    values : pandas.Series
        The time series, at the ends of the intervals in UTC.
    durations : pandas.Series
        The duration of the interval of each value.
    time_zone : str
        The local time zone.

    Returns
    -------
    pandas.DatetimeIndex
        The start of the interval of each value, in local time and
        without time zone.
    """
    return (
        pd.DatetimeIndex(values.index - durations.to_numpy())
        .tz_localize("UTC")
        .tz_convert(time_zone)
        .tz_localize(None)
    )


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


def _find_frozen(values: pd.Series, durations: pd.Series) -> pd.Series:
    """
    Find the runs of the same value that last too long.

    Parameters
    ----------
    values : pandas.Series
        The demand.
    durations : pandas.Series
        The duration of the interval of each value, before any value is
        removed.

    Returns
    -------
    pandas.Series
        True for the values of the runs.
    """
    durations, follows = _get_intervals(values, durations)
    runs = ((values != values.shift()) | ~follows).cumsum().to_numpy()
    duration = durations.groupby(runs).transform("sum")
    return pd.Series(
        (duration >= FROZEN_DURATION).to_numpy(), index=values.index
    )


def _find_repeated_days(
    values: pd.Series, local_times: pd.DatetimeIndex
) -> np.ndarray:
    """
    Find the days whose values repeat those of an earlier day.

    Parameters
    ----------
    values : pandas.Series
        The demand.
    local_times : pandas.DatetimeIndex
        The local time of each value, without time zone, whose day is
        the day of the value.

    Returns
    -------
    numpy.ndarray
        True for the values of the repeated days.
    """
    days = local_times.normalize()
    # Each day is compared by its values at their times of the day, so
    # that days missing other values differ.
    fingerprints = pd.Series(
        list(
            zip(
                local_times - days,
                values.round(COPIED_DAY_DECIMALS).to_numpy(),
                strict=True,
            )
        ),
        index=days,
    )
    seen = set()
    copied = set()
    for day, day_values in fingerprints.groupby(level=0):
        if len(day_values) < MIN_VALUES_OF_DAY:
            continue
        fingerprint = tuple(day_values)
        if fingerprint in seen:
            copied.add(day)
        else:
            seen.add(fingerprint)
    return days.isin(list(copied))


def _find_copied_days(
    values: pd.Series, durations: pd.Series, time_zone: str
) -> pd.Series:
    """
    Find the days whose values repeat those of an earlier day.

    A data source can copy its days by the starts or by the ends of its
    intervals, whichever its times mark, so the days are taken both
    ways.

    Parameters
    ----------
    values : pandas.Series
        The demand, at times in UTC.
    durations : pandas.Series
        The duration of the interval of each value, before any value is
        removed.
    time_zone : str
        The time zone of the days.

    Returns
    -------
    pandas.Series
        True for the values of the copied days.
    """
    durations, _ = _get_intervals(values, durations)
    starts = _get_local_starts(values, durations, time_zone)
    ends = (
        pd.DatetimeIndex(values.index)
        .tz_localize("UTC")
        .tz_convert(time_zone)
        .tz_localize(None)
    )
    return pd.Series(
        _find_repeated_days(values, starts)
        | _find_repeated_days(values, ends),
        index=values.index,
    )


def _find_spikes(
    values: pd.Series, resolutions: pd.Series, durations: pd.Series
) -> pd.Series:
    """
    Find the short runs of values that leave the level around them.

    Parameters
    ----------
    values : pandas.Series
        The demand, without the values of the other rules.
    resolutions : pandas.Series
        The resolution of each value, before any value is removed.
    durations : pandas.Series
        The duration of the interval of each value, before any value is
        removed.

    Returns
    -------
    pandas.Series
        True for the values of the spikes.
    """
    if len(values) < 3:
        return pd.Series(False, index=values.index)
    durations, follows = _get_intervals(values, durations)
    x = values.to_numpy()
    # The number of runs found that start at or before each value, minus
    # those that end before it.
    runs = np.zeros(len(x) + 1, dtype=int)

    # The change of a spike at the resolution of each value, and the
    # longest run to look for, at the finest resolution.
    changes = np.where(
        resolutions.reindex(values.index) < pd.Timedelta(minutes=30),
        SPIKE_CHANGE_SUBHOURLY,
        SPIKE_CHANGE_HOURLY,
    )
    longest = max(1, int(SPIKE_DURATION / resolutions.min()))
    seconds = pd.Series(durations.dt.total_seconds().to_numpy())
    gaps = pd.Series((~follows).to_numpy(dtype=float))
    for length in range(1, min(longest, len(x) - 2) + 1):
        # The values before and after the run, which must be at the same
        # level, and the run, which must leave it in one direction, at
        # the resolution of its first value. The run and the value after
        # it must follow each other without gaps, and the run must last
        # at most the duration of a spike, unless it is a single value.
        before = x[: len(x) - length - 1]
        after = x[length + 1 :]
        change = changes[1 : len(x) - length]
        level = (before + after) / 2
        run = pd.Series(x[1 : len(x) - 1]).rolling(length)
        lowest = run.min().to_numpy()[length - 1 :]
        highest = run.max().to_numpy()[length - 1 :]
        without_gaps = (
            gaps.rolling(length + 1).sum().to_numpy()[length + 1 :] == 0
        )
        short = (
            seconds.rolling(length).sum().to_numpy()[length : len(x) - 1]
            <= SPIKE_DURATION.total_seconds()
        )
        up = (lowest > before * (1 + change)) & (lowest > after * (1 + change))
        down = (highest < before * (1 - change)) & (
            highest < after * (1 - change)
        )
        found = (
            (np.abs(before - after) < change / 2 * level)
            & without_gaps
            & (short | (length == 1))
            & (up | down)
        )
        starts = np.flatnonzero(found) + 1
        np.add.at(runs, starts, 1)
        np.add.at(runs, starts + length, -1)
    return pd.Series(np.cumsum(runs)[:-1] > 0, index=values.index)


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
        The mean demand of every day, missing for the days without
        enough values, whose gaps break the runs if they are long.
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
    # A run is broken by a day that is not low, or by a gap of missing
    # days longer than a few, and needs enough low days.
    observed = daily.notna()
    gaps = (observed != observed.shift()).cumsum()
    gap_lengths = (~observed).groupby(gaps).transform("sum")
    breaks = (observed & ~low) | (gap_lengths > LEVEL_DROP_GAP_DAYS)
    lengths = low.groupby(breaks.cumsum()).transform("sum")
    return daily.index[low & (lengths >= LEVEL_DROP_DAYS)]


def _find_level_drops(
    values: pd.Series, durations: pd.Series, time_zone: str
) -> pd.Series:
    """
    Find the runs of days whose level drops far below the usual one.

    Parameters
    ----------
    values : pandas.Series
        The demand, without the values of the other rules, at times in
        UTC.
    durations : pandas.Series
        The duration of the interval of each value, before any value is
        removed.
    time_zone : str
        The time zone of the days.

    Returns
    -------
    pandas.Series
        True for the values of the days of the drops.
    """
    if values.empty:
        return pd.Series(False, index=values.index)

    # The mean of each day whose values cover enough of it, weighted by
    # their intervals, and of every day from the first to the last.
    durations, _ = _get_intervals(values, durations)
    days = _get_local_starts(values, durations, time_zone).normalize()
    seconds = pd.Series(durations.dt.total_seconds().to_numpy(), index=days)
    covered = seconds.groupby(level=0).sum()
    energy = (seconds * values.to_numpy()).groupby(level=0).sum()
    daily = (energy / covered).where(covered >= MIN_COVERAGE * 24 * 3600)
    daily = daily.asfreq("D")

    dropped = _find_drop_days(daily, daily)
    dropped = dropped.union(_find_drop_days(daily, daily.drop(dropped)))
    return pd.Series(days.isin(dropped), index=values.index)


def _find_removed(
    values: pd.Series,
    resolutions: pd.Series,
    durations: pd.Series,
    time_zone: str,
) -> pd.Series:
    """
    Find the rule that removes each value, if any.

    Parameters
    ----------
    values : pandas.Series
        The processed demand, at times in UTC.
    resolutions : pandas.Series
        The resolution of each value.
    durations : pandas.Series
        The duration of the interval of each value.
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
    remove("frozen", _find_frozen(values[removed == ""], durations))
    remove(
        "copied_day",
        _find_copied_days(values[removed == ""], durations, time_zone),
    )
    remove(
        "spike", _find_spikes(values[removed == ""], resolutions, durations)
    )
    remove(
        "level_drop",
        _find_level_drops(values[removed == ""], durations, time_zone),
    )
    return removed


def _resample_hourly(values: pd.Series, durations: pd.Series) -> pd.DataFrame:
    """
    Average the values of each hour, at its end.

    Each value is the average of its interval, and counts in each hour
    for the part of its interval within the hour, so that the energy of
    the values is kept.

    Parameters
    ----------
    values : pandas.Series
        The demand, at the resolution of the data source.
    durations : pandas.Series
        The duration of the interval of each value, before any value is
        removed.

    Returns
    -------
    pandas.DataFrame
        The average ("Load (MW)") and whether the values cover enough of
        the hour ("covered"), for each hour with values.
    """
    if values.empty:
        return pd.DataFrame(
            {"Load (MW)": pd.Series(dtype="float64"), "covered": False},
            index=values.index,
        )
    durations, _ = _get_intervals(values, durations)
    ends = pd.DatetimeIndex(values.index)
    first_hour = (ends - durations.to_numpy()).min().floor("h")
    hours = pd.date_range(first_hour, ends.max().ceil("h"), freq="h")

    # The time covered and the energy since the first hour, at the start
    # and the end of each interval. They grow linearly within the
    # intervals and stay the same between them, so they are interpolated
    # at the starts of the hours.
    seconds = durations.dt.total_seconds().to_numpy()
    end_seconds = (ends - first_hour).total_seconds().to_numpy()
    times = np.column_stack([end_seconds - seconds, end_seconds]).ravel()
    hour_seconds = (hours - first_hour).total_seconds().to_numpy()
    in_hours = {}
    for name, amounts in (
        ("covered", seconds),
        ("energy", seconds * values.to_numpy()),
    ):
        totals = np.cumsum(amounts)
        in_hours[name] = np.diff(
            np.interp(
                hour_seconds,
                times,
                np.column_stack([totals - amounts, totals]).ravel(),
            )
        )

    with_values = in_hours["covered"] > 0
    covered = in_hours["covered"][with_values]
    hourly = pd.DataFrame(
        {
            "Load (MW)": in_hours["energy"][with_values] / covered,
            "covered": covered >= MIN_COVERAGE * 3600,
        },
        index=hours[1:][with_values],
    )
    hourly.index.name = values.index.name
    return hourly


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
        utils.paths.get_electricity_demand_file("processed", code, data_source)
    )["Load (MW)"].sort_index()
    resolutions = _get_resolutions(processed)
    durations = _get_durations(processed, resolutions)
    step = resolutions.max() if len(processed) else pd.Timedelta(hours=1)

    # Remove the values of the rules, at the resolution of the data
    # source, and average the others in each hour.
    removed = _find_removed(
        processed,
        resolutions,
        durations,
        str(utils.entities.get_time_zone(code)),
    )
    hourly = _resample_hourly(processed[removed == ""], durations)
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

    file_path = utils.paths.get_electricity_demand_file(
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

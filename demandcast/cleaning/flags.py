"""
License: AGPL-3.0.

Description:

    This module flags the changes in the cleaned electricity demand of a
    data source that need a review, without removing any value, and
    saves them next to the cleaned electricity demand. The flags are:

    - midday_dip: the demand around solar noon falls, compared with the
      morning and afternoon, below what it was in the same quarter of
      earlier years.
    - time_lag: the daily profile of a quarter, in local time, is
      shifted by whole hours from that of the same quarter of the other
      years.
    - daylight_saving: the daily profile, in local time, shifts across
      a change of the clocks.
    - annual_total: the demand of a year of a country is more than a
      third away from its annual demand per capita times its population.
    - annual_change: the ratio of the demand of a year to its annual
      demand per capita times its population changes by more than 10%
      from the year before.

    The midday dip is the sign of a demand that leaves out the
    generation embedded in the distribution networks, such as rooftop
    solar, whose growth over the years hides more and more of the
    demand at midday. DemandCast models the gross demand, with the
    demand that this generation supplies, so the flag marks the series
    that do not have it, or a change of what a series has. The midday
    index of a day is the mean demand of the three hours around solar
    noon (10:30 to 13:30 in solar time, from the longitude of the
    country or subdivision), divided by the mean of the two hours from
    7:00 and the two hours from 15:00. Its median over the days of a
    quarter (December to February, March to May, June to August and
    September to November) is compared with the highest median of the
    same quarter in the earlier years, since the sunny season is not
    the same everywhere. A drop of more than 0.05 is flagged: the demand
    of a system without solar keeps its midday index within about 0.02
    from year to year, while the national demand of Great Britain,
    without the embedded solar, drops from about 1.02 in 2011 to 0.87
    in 2026 in summer. The flag does not prove that solar is missing:
    the index also drops when the demand changes at midday, such as
    during the lockdowns of 2020, and it cannot see the solar that was
    already there when the series starts.

    The demand follows the clocks, so its daily profile in local time
    stays at the same hours from year to year and across the changes of
    the clocks, even when a country changes its rules of daylight
    saving time. A profile that has to move by whole hours to match the
    others shows times that are read in the wrong time zone, without or
    with a wrong daylight saving time, or at the wrong end of the
    intervals. The profiles are the mean demand of each hour, divided
    by their mean, and the move of up to 3 hours that gives the
    smallest squared difference is flagged if it halves the squared
    difference without a move. The profile of a quarter with at least
    60 days is compared with the median profile of the same quarter
    over the years, if there are at least 3, and the profile of the 14
    days after a change of the clocks with that of the 14 days before
    it, without the day of the change. The flags give the hours by
    which the profile has to move later.

    The annual demand per capita and the population are those that
    DemandCast retrieves, and the annual flags are skipped if they have
    not been retrieved. The demand of a year, with at least 90% of its
    hours, is its mean demand times its hours. The demand that the
    system operators measure differs from that of the statistics by the
    demand of the consumers that are not on their networks, such as
    with their own generation, and by the losses and the use of the
    power plants: the demand of the countries is between 0.87 and 1.08
    times that of the statistics, and the flag catches the errors of
    units, of a series that covers only part of a country, or of the
    wrong country. The subdivisions have the annual demand per capita of
    their country, which can be from 0.2 to 3 times theirs, so only
    their changes are flagged. A change of more than 10% is not the
    growth of the demand, which the annual demand per capita and the
    population follow, but a change of what the series covers or of its
    definition: the ratio of the countries changes by at most about 7%
    from a year to the next.
"""

import logging
import os
from typing import cast

import numpy as np
import pandas as pd
import utils.config
import utils.entities
import utils.shapes

# The columns of the flags.
COLUMNS = ["start", "end", "flag", "period", "value", "reference"]

# The names of the quarters, from December to February.
QUARTERS = ["DJF", "MAM", "JJA", "SON"]

# The days that a quarter needs.
MIN_DAYS_OF_QUARTER = 60

# The hours of the midday and of the morning and afternoon around it,
# from and to, in solar time, and the drop of the midday index that is
# flagged.
MIDDAY_HOURS = (10.5, 13.5)
MORNING_HOURS = (7.0, 9.0)
AFTERNOON_HOURS = (15.0, 17.0)
MIDDAY_DIP_DROP = 0.05

# The largest move of a profile, the share of the squared difference
# without a move that the move needs to be flagged, and the years that
# a quarter is compared with.
MAX_LAG = 3
LAG_SHARE = 0.5
MIN_YEARS_OF_QUARTER = 3

# The days before and after a change of the clocks, and the days that
# each of them needs.
DAYS_AROUND_CHANGE = 14
MIN_DAYS_AROUND_CHANGE = 12

# The share of the hours that a year needs, the factor away from the
# annual demand per capita times the population that is flagged, and
# the change of the ratio to it from a year to the next.
MIN_HOURS_OF_YEAR = 0.9
ANNUAL_TOTAL_FACTOR = 4 / 3
ANNUAL_CHANGE = 0.1


def _get_years_and_quarters(
    times: pd.DatetimeIndex,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Get the year and quarter of each time.

    Parameters
    ----------
    times : pandas.DatetimeIndex
        The times.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        The year, in which December goes with the next year, and the
        quarter, from 0 for December to February.
    """
    years = times.year + (times.month == 12)
    quarters = (times.month % 12) // 3
    return np.asarray(years), np.asarray(quarters)


def _get_quarter_days(
    year: int, quarter: int
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Get the first and last day of a quarter.

    Parameters
    ----------
    year : int
        The year, in which December goes with the next year.
    quarter : int
        The quarter, from 0 for December to February.

    Returns
    -------
    tuple[pandas.Timestamp, pandas.Timestamp]
        The first and last day.
    """
    start = pd.Timestamp(year=year, month=3 * quarter or 12, day=1)
    if quarter == 0:
        start -= pd.DateOffset(years=1)
    return start, start + pd.DateOffset(months=3, days=-1)


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
    shape = utils.shapes.get_entity_shape(code, make_plot=False)
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
        The median by year (rows) and quarter (columns), with no value
        for the quarters with too few days.
    """
    years, quarters = _get_years_and_quarters(pd.DatetimeIndex(daily.index))
    frame = pd.DataFrame(
        {"year": years, "quarter": quarters, "index": daily.to_numpy()}
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
        The flagged quarters, with their midday index ("value") and the
        highest one of earlier years ("reference").
    """
    quarterly = _get_quarterly_index(_get_midday_index(cleaned, longitude))
    rows = []
    for quarter in range(4):
        index = quarterly[quarter].dropna()
        reference = index.cummax().shift()
        for year in index.index[index < reference - MIDDAY_DIP_DROP]:
            start, end = _get_quarter_days(int(year), quarter)
            rows.append(
                {
                    "start": start,
                    "end": end,
                    "flag": "midday_dip",
                    "period": f"{QUARTERS[quarter]} {year}",
                    "value": index[year],
                    "reference": reference[year],
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


def _to_local_time(values: pd.Series, time_zone: str) -> pd.Series:
    """
    Put the hourly demand at the local times of the starts of the hours.

    Parameters
    ----------
    values : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    time_zone : str
        The time zone of the country or subdivision.

    Returns
    -------
    pandas.Series
        The demand, at the local times of the starts of the hours.
    """
    starts = pd.DatetimeIndex(values.index) - pd.Timedelta(hours=1)
    local = starts.tz_localize("UTC").tz_convert(time_zone).tz_localize(None)
    return pd.Series(values.to_numpy(), index=local)


def _get_profile(values: pd.Series) -> np.ndarray | None:
    """
    Get the daily profile of the demand.

    Parameters
    ----------
    values : pandas.Series
        The hourly demand, at the local times of the starts of the
        hours.

    Returns
    -------
    numpy.ndarray | None
        The mean demand of each hour of the day divided by their mean,
        or None if an hour has no value.
    """
    hours = pd.DatetimeIndex(values.index).hour
    profile = values.groupby(hours).mean().reindex(range(24))
    if profile.isna().any():
        return None
    return (profile / profile.mean()).to_numpy()


def _get_lag(profile: np.ndarray, reference: np.ndarray) -> int:
    """
    Get the hours by which a profile has to move to match another.

    Parameters
    ----------
    profile : numpy.ndarray
        The daily profile.
    reference : numpy.ndarray
        The daily profile to match.

    Returns
    -------
    int
        The hours by which the profile has to move later, or 0 if no
        move halves its squared difference with the reference.
    """
    errors = {
        lag: float(((np.roll(profile, lag) - reference) ** 2).sum())
        for lag in range(-MAX_LAG, MAX_LAG + 1)
    }
    lag = min(errors, key=errors.__getitem__)
    return lag if errors[lag] < LAG_SHARE * errors[0] else 0


def _find_time_lags(cleaned: pd.Series, time_zone: str) -> pd.DataFrame:
    """
    Find the quarters whose profile is shifted from the other years.

    Parameters
    ----------
    cleaned : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    time_zone : str
        The time zone of the country or subdivision.

    Returns
    -------
    pandas.DataFrame
        The flagged quarters, with the hours by which their profile has
        to move later ("value") and none ("reference").
    """
    local = _to_local_time(cleaned, time_zone)
    times = pd.DatetimeIndex(local.index)
    profiles = {}
    for key, values in local.groupby(list(_get_years_and_quarters(times))):
        days = pd.DatetimeIndex(values.index).normalize().nunique()
        profile = _get_profile(values)
        if days >= MIN_DAYS_OF_QUARTER and profile is not None:
            profiles[cast(tuple[int, int], key)] = profile

    rows = []
    for (year, quarter), profile in profiles.items():
        same_quarter = [p for (_, q), p in profiles.items() if q == quarter]
        if len(same_quarter) < MIN_YEARS_OF_QUARTER:
            continue
        lag = _get_lag(profile, np.median(same_quarter, axis=0))
        if lag:
            start, end = _get_quarter_days(int(year), int(quarter))
            rows.append(
                {
                    "start": start,
                    "end": end,
                    "flag": "time_lag",
                    "period": f"{QUARTERS[quarter]} {year}",
                    "value": float(lag),
                    "reference": 0.0,
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


def _find_daylight_saving_errors(
    cleaned: pd.Series, time_zone: str
) -> pd.DataFrame:
    """
    Find the changes of the clocks across which the profile shifts.

    Parameters
    ----------
    cleaned : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    time_zone : str
        The time zone of the country or subdivision.

    Returns
    -------
    pandas.DataFrame
        The flagged changes, from the days before to the days after,
        with the hours by which the profile after has to move later
        ("value") and none ("reference").
    """
    if cleaned.empty:
        return pd.DataFrame(columns=COLUMNS)
    times = pd.DatetimeIndex(cleaned.index)
    hours = pd.date_range(
        times.min().floor("D"), times.max().ceil("D"), freq="1h"
    )
    offsets = (
        hours.tz_localize("UTC").tz_convert(time_zone).tz_localize(None)
        - hours
    )
    changes = hours[1:][offsets[1:] != offsets[:-1]]

    rows = []
    period = pd.Timedelta(days=DAYS_AROUND_CHANGE)
    for change in changes:
        before = cleaned[(times > change - period) & (times <= change)]
        after = cleaned[
            (times > change + pd.Timedelta(days=1))
            & (times <= change + pd.Timedelta(days=1) + period)
        ]
        profile_before = _get_profile(_to_local_time(before, time_zone))
        profile_after = _get_profile(_to_local_time(after, time_zone))
        if (
            min(len(before), len(after)) < 24 * MIN_DAYS_AROUND_CHANGE
            or profile_before is None
            or profile_after is None
        ):
            continue
        lag = _get_lag(profile_after, profile_before)
        if lag:
            day = (
                pd.Timestamp(change)
                .tz_localize("UTC")
                .tz_convert(time_zone)
                .tz_localize(None)
                .normalize()
            )
            rows.append(
                {
                    "start": day - period,
                    "end": day + period,
                    "flag": "daylight_saving",
                    "period": f"{day:%Y-%m-%d}",
                    "value": float(lag),
                    "reference": 0.0,
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


def _read_annual_values(
    folder: str, column: str, code: str
) -> pd.Series | None:
    """
    Read the yearly values of a variable of a country or subdivision.

    Parameters
    ----------
    folder : str
        The name of the folder of the variable.
    column : str
        The column of the variable.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    pandas.Series | None
        The value of each year, or None if it has not been retrieved.
    """
    file_path = os.path.join(
        utils.config.read_folders_structure()[folder], f"{code}.parquet"
    )
    if not os.path.exists(file_path):
        return None
    values = pd.read_parquet(file_path)[column]
    return values.groupby(pd.DatetimeIndex(values.index).year).median()


def _find_annual_errors(cleaned: pd.Series, code: str) -> pd.DataFrame:
    """
    Find the years whose demand is far from or changes from expected.

    Parameters
    ----------
    cleaned : pandas.Series
        The hourly demand, at the ends of the hours in UTC.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    pandas.DataFrame
        The flagged years, with their demand and expected demand in TWh
        ("value" and "reference") for the annual totals, and their ratio
        to the expected demand and that of the year before for the
        annual changes.
    """
    per_capita = _read_annual_values(
        "annual_electricity_demand_per_capita_folder",
        "Annual electricity demand per capita (kWh)",
        code,
    )
    population = _read_annual_values("population_folder", "Population", code)
    if per_capita is None or population is None:
        logging.info(
            f"The annual demand per capita or the population of {code} "
            "have not been retrieved, so the annual demand is not checked."
        )
        return pd.DataFrame(columns=COLUMNS)

    # The demand of the years with enough hours, in TWh.
    starts = pd.DatetimeIndex(cleaned.index) - pd.Timedelta(hours=1)
    by_year = cleaned.groupby(starts.year)
    years = by_year.size().index
    hours_of_years = pd.Series(
        [
            (pd.Timestamp(year + 1, 1, 1) - pd.Timestamp(year, 1, 1))
            / pd.Timedelta(hours=1)
            for year in years
        ],
        index=years,
    )
    enough = by_year.size() >= MIN_HOURS_OF_YEAR * hours_of_years
    annual = pd.DataFrame(
        {
            "total": (by_year.mean() * hours_of_years / 1e6)[enough],
            "expected": per_capita * population / 1e9,
        }
    ).dropna()
    annual["ratio"] = annual["total"] / annual["expected"]

    annual_years = annual.index.to_numpy(dtype=int).tolist()
    ratios = dict(zip(annual_years, annual["ratio"].tolist(), strict=True))
    rows = []
    for year, total, expected in zip(
        annual_years,
        annual["total"].tolist(),
        annual["expected"].tolist(),
        strict=True,
    ):
        days = (pd.Timestamp(year, 1, 1), pd.Timestamp(year, 12, 31))
        if "_" not in code and not (
            1 / ANNUAL_TOTAL_FACTOR <= ratios[year] <= ANNUAL_TOTAL_FACTOR
        ):
            rows.append(
                {
                    "start": days[0],
                    "end": days[1],
                    "flag": "annual_total",
                    "period": str(year),
                    "value": total,
                    "reference": expected,
                }
            )
        before = ratios.get(year - 1)
        if before and abs(ratios[year] / before - 1) > ANNUAL_CHANGE:
            rows.append(
                {
                    "start": days[0],
                    "end": days[1],
                    "flag": "annual_change",
                    "period": str(year),
                    "value": ratios[year],
                    "reference": before,
                }
            )
    return pd.DataFrame(rows, columns=COLUMNS)


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
        The first and last day ("start" and "end"), the flag ("flag"),
        the name of the period ("period"), and the value and reference
        of the flag ("value" and "reference") of each flagged period.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "cleaned", code, data_source
    )
    cleaned = pd.read_parquet(file_path)["Load (MW)"].sort_index()
    time_zone = str(utils.entities.get_time_zone(code))

    found = [
        _find_midday_dips(cleaned, _get_longitude(code)),
        _find_time_lags(cleaned, time_zone),
        _find_daylight_saving_errors(cleaned, time_zone),
        _find_annual_errors(cleaned, code),
    ]
    flags = pd.concat(
        [flags for flags in found if not flags.empty] or found[:1],
        ignore_index=True,
    ).sort_values(["start", "flag"], ignore_index=True)

    flags_path = file_path.removesuffix(".parquet") + "_flags.parquet"
    os.makedirs(os.path.dirname(flags_path), exist_ok=True)
    flags.to_parquet(flags_path)
    for flag, periods in flags.groupby("flag")["period"]:
        logging.warning(
            f"The electricity demand of {code} from {data_source} is "
            f"flagged with {flag} in {', '.join(periods)}. See "
            f"{flags_path}."
        )

    return flags

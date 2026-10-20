"""
License: AGPL-3.0.

Description:

    This module flags the changes in the cleaned electricity demand of a
    data source that need a review, without removing any value, and
    saves them next to the cleaned electricity demand. The flags are:

    - midday_dip: the demand around solar noon falls, compared with the
      morning and afternoon, below what it was in the same quarter of
      earlier years.
    - midday_rise: the same, when it rises above, and above the year
      before.
    - time_lag: the daily profile of a quarter, in local time, is
      shifted by whole hours from that of the same quarter of the other
      years.
    - daylight_saving: the daily profile, in local time, shifts across
      a change of the clocks with the clocks, or against them unlike
      the same changes of the other years.
    - annual_total: the demand of a year of a country is more than a
      third away from its annual demand per capita times its population.
    - annual_change: the demand of a year, and its ratio to its annual
      demand per capita times its population, change by more than 10%
      (20% for a subdivision) from the year before.

    The midday dip is the sign of a demand that leaves out the
    generation embedded in the distribution networks, such as rooftop
    solar, whose growth over the years hides more and more of the
    demand at midday. DemandCast models the gross demand, with the
    demand that this generation supplies, so the flag marks the series
    that do not have it. A midday rise marks a change of what a series
    has, such as when a system operator starts to add the embedded
    generation, as EPIAS from 2020-12-30 and ONS from 2023-04-29, or
    the charging of batteries. The midday index of a day is the mean
    demand of the three hours around solar noon (10:30 to 13:30 in
    solar time, from the longitude of the country or subdivision),
    divided by the mean of the two hours from 7:00 and the two hours
    from 15:00. Its median over the days of a quarter (December to
    February, March to May, June to August and September to November)
    is compared with the median of the same quarter in the earlier
    years, since the sunny season is not the same everywhere, and a
    change of more than 0.05 is flagged. The demand of a system without
    solar keeps its midday index within about 0.02 from year to year,
    while the national demand of Great Britain, without the embedded
    solar, drops from about 1.02 in 2011 to 0.87 in 2026 in summer. The
    median of the earlier years, rather than their highest index, keeps
    a single unusual year, such as a drought, from flagging all the
    years after it. The flags do not prove that solar is missing: the
    index also changes when the demand changes at midday, such as
    during the lockdowns of 2020 or with the agricultural supply moved
    to the day in India, and it cannot see the solar that was already
    there when the series starts, as in California. A rise has to be
    above the year before too, since a change of what a series has is
    sudden, while the midday demand of some states of India grows
    slowly over the years as their agricultural supply moves to the
    day.

    The demand follows the clocks, so its daily profile in local time
    stays at the same hours from year to year and across the changes of
    the clocks, even when a country changes its rules of daylight
    saving time. A profile that has to move by whole hours to match the
    others shows times that are read in the wrong time zone, without or
    with a wrong daylight saving time, at the wrong end of the
    intervals, or values that slip against their times. The profiles
    are the mean demand of each hour, divided by their mean, and the
    move of up to 3 hours that gives the smallest squared difference is
    flagged if it leaves less than 40% of the squared difference without
    a move. The real errors leave from 5% to 31%, while a change of the
    shape of the profile, such as a growing midday dip, can leave about
    half. The profile of a quarter with at least 60 days is compared
    with the median profile of the same quarter over the years, if
    there are at least 3, and the profile of the 14 days after a change
    of the clocks with that of the 14 days before it, without the day
    of the change, with the median demand of each hour, so that a few
    holidays, such as the carnival in Brazil, do not shift it. The
    flags give the hours by which the profile has to move later.

    Some demand follows the sun more than the clocks, such as in the hot
    regions of Mexico, in the north-east of Brazil, or on the network
    of South Australia with its rooftop solar: its profile moves an hour
    against a change of the clocks, later after the clocks go forward
    and earlier after they go back, by a part of an hour that is about
    the same in most years. So a shift against the change is flagged
    only if it differs by 0.75 hours or more from the median shift of
    the same changes (forward or back) of the other years, if there are
    at least 2, such as when the times of a year leave out daylight
    saving time. These shifts are found in steps of 0.1 hours, between
    the hours of the profiles. A shift with the change cannot come
    from the demand, so it is always flagged: the times of that part of
    the year are wrong, such as the winters of Northern Ireland on
    ENTSO-E, an hour late in every year. A sudden change of the weather
    after a change of the clocks, such as in New Brunswick on
    2026-03-08, can still shift the profile of the heating.

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
    their changes are flagged. A change of the ratio is not the growth
    of the demand, which the annual demand per capita and the
    population follow, but a change of what the series covers or of its
    definition: the ratio of the countries changes by at most about 7%
    from a year to the next. The demand itself has to change as much,
    since the annual demand per capita jumps when one of its sources is
    missing for a year. The demand of a small subdivision changes more,
    such as with the national shocks that hit the regions unequally, so
    their changes are flagged from 20%.
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
# from and to, in solar time, and the change of the midday index that is
# flagged.
MIDDAY_HOURS = (10.5, 13.5)
MORNING_HOURS = (7.0, 9.0)
AFTERNOON_HOURS = (15.0, 17.0)
MIDDAY_CHANGE = 0.05

# The largest move of a profile, the share of the squared difference
# without a move that the move needs to be flagged, and the years that
# a quarter is compared with.
MAX_LAG = 3
LAG_SHARE = 0.4
MIN_YEARS_OF_QUARTER = 3

# The days before and after a change of the clocks, the days that each
# of them needs, and the changes of the other years that give the usual
# shift of a change.
DAYS_AROUND_CHANGE = 14
MIN_DAYS_AROUND_CHANGE = 12
MIN_OTHER_CHANGES = 2

# The difference from the usual shift of the same changes of the other
# years, in hours, that is flagged, and the step of the shifts.
SHIFT_DIFFERENCE = 0.75
SHIFT_STEP = 0.1

# The share of the hours that a year needs, the factor away from the
# annual demand per capita times the population that is flagged, and
# the change from a year to the next of the demand and of its ratio to
# it that is flagged, for the countries and for the subdivisions.
MIN_HOURS_OF_YEAR = 0.9
ANNUAL_TOTAL_FACTOR = 4 / 3
ANNUAL_CHANGE_OF_COUNTRY = 0.1
ANNUAL_CHANGE_OF_SUBDIVISION = 0.2


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


def _find_midday_changes(cleaned: pd.Series, longitude: float) -> pd.DataFrame:
    """
    Find the quarters whose midday index moves away from earlier years.

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
        median of earlier years ("reference").
    """
    quarterly = _get_quarterly_index(_get_midday_index(cleaned, longitude))
    rows = []
    for quarter in range(4):
        index = quarterly[quarter].dropna()
        reference = index.expanding().median().shift()
        change = index - reference
        rise = (change > MIDDAY_CHANGE) & (
            index - index.shift() > MIDDAY_CHANGE
        )
        for flag, years in [
            ("midday_dip", index.index[change < -MIDDAY_CHANGE]),
            ("midday_rise", index.index[rise]),
        ]:
            for year in years:
                start, end = _get_quarter_days(int(year), quarter)
                rows.append(
                    {
                        "start": start,
                        "end": end,
                        "flag": flag,
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


def _get_profile(
    values: pd.Series, statistic: str = "mean"
) -> np.ndarray | None:
    """
    Get the daily profile of the demand.

    Parameters
    ----------
    values : pandas.Series
        The hourly demand, at the local times of the starts of the
        hours.
    statistic : str, optional
        The statistic of the demand of each hour, "mean" or "median".

    Returns
    -------
    numpy.ndarray | None
        The statistic of the demand of each hour of the day divided by
        their mean, or None if an hour has no value.
    """
    hours = pd.DatetimeIndex(values.index).hour
    profile = values.groupby(hours).agg(statistic).reindex(range(24))
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


def _get_shift(profile: np.ndarray, reference: np.ndarray) -> float:
    """
    Get the hours, in steps of 0.1, by which a profile moves to match.

    Parameters
    ----------
    profile : numpy.ndarray
        The daily profile.
    reference : numpy.ndarray
        The daily profile to match.

    Returns
    -------
    float
        The hours by which the profile, between its hours, has to move
        later to have the smallest squared difference with the
        reference.
    """
    hours = np.arange(24)
    closed = np.append(profile, profile[0])
    shifts = np.arange(-MAX_LAG, MAX_LAG + SHIFT_STEP / 2, SHIFT_STEP)
    errors = [
        float(
            (
                (
                    np.interp((hours - shift) % 24, np.arange(25), closed)
                    - reference
                )
                ** 2
            ).sum()
        )
        for shift in shifts
    ]
    return round(float(shifts[int(np.argmin(errors))]), 1)


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
        ("value") and the usual hours of the same changes of the other
        years ("reference").
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
    changed = offsets[1:] != offsets[:-1]
    changes = hours[1:][changed]
    # The direction of each change: 1 when the clocks go forward, -1
    # when they go back.
    directions = np.sign((offsets[1:] - offsets[:-1])[changed].total_seconds())

    shifts = []
    period = pd.Timedelta(days=DAYS_AROUND_CHANGE)
    for change, direction in zip(changes, directions, strict=True):
        before = cleaned[(times > change - period) & (times <= change)]
        after = cleaned[
            (times > change + pd.Timedelta(days=1))
            & (times <= change + pd.Timedelta(days=1) + period)
        ]
        profile_before = _get_profile(
            _to_local_time(before, time_zone), "median"
        )
        profile_after = _get_profile(
            _to_local_time(after, time_zone), "median"
        )
        if (
            min(len(before), len(after)) < 24 * MIN_DAYS_AROUND_CHANGE
            or profile_before is None
            or profile_after is None
        ):
            continue
        shifts.append(
            (
                change,
                direction,
                _get_lag(profile_after, profile_before),
                _get_shift(profile_after, profile_before),
            )
        )

    rows = []
    for change, direction, lag, shift in shifts:
        # The usual shift of the same changes of the other years, and
        # whether the profile moves with the clocks, against a demand
        # that follows the sun more than the clocks.
        others = [
            other_shift
            for other_change, other_direction, _, other_shift in shifts
            if other_direction == direction and other_change != change
        ]
        usual = (
            float(np.median(others))
            if len(others) >= MIN_OTHER_CHANGES
            else 0.0
        )
        if lag == 0 or (
            lag * direction < 0 and abs(shift - usual) < SHIFT_DIFFERENCE
        ):
            continue
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
                "reference": round(usual, 1),
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
    totals = dict(zip(annual_years, annual["total"].tolist(), strict=True))
    ratios = dict(zip(annual_years, annual["ratio"].tolist(), strict=True))
    change = (
        ANNUAL_CHANGE_OF_SUBDIVISION
        if "_" in code
        else ANNUAL_CHANGE_OF_COUNTRY
    )
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
        if (
            year - 1 in ratios
            and abs(ratios[year] / ratios[year - 1] - 1) > change
            and abs(total / totals[year - 1] - 1) > change
        ):
            rows.append(
                {
                    "start": days[0],
                    "end": days[1],
                    "flag": "annual_change",
                    "period": str(year),
                    "value": ratios[year],
                    "reference": ratios[year - 1],
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
        _find_midday_changes(cleaned, _get_longitude(code)),
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

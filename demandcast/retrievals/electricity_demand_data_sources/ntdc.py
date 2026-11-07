"""
License: AGPL-3.0.

Description:

    This module provides functions to retrieve the electricity demand
    data of the National Transmission & Despatch Company (NTDC) in
    Pakistan, from the copy on Zenodo of a dataset published on Kaggle
    under the CC0 licence. The data is retrieved all at once, from a
    single CSV file.

    The dataset has not been on Kaggle since October 2026 at the
    latest: the Wayback Machine keeps its page of 2026-08-04, and Zenodo
    its file. The file gives the hourly system load (SYSLOAD) in MW,
    with thousands separators, by date and hour ending from 1 to 24 in
    the time of Pakistan, which has no daylight saving time. Where an
    hour appears twice once the days of the rows are corrected (see
    below), its first value is kept.

    About 170 rows around midnight have the date of the day before or
    after, such as the hour 24 of 06/01/2015 between the hours 23 of
    07/01/2015 and 2 of 08/01/2015, so that 51 dates and hours appear
    twice. The module moves each of them by that day, which leaves every
    day with 24 hours, except for 9 days with gaps, and the values in
    line with their new neighbours.

    Some days have the same values as the same days of the year before:
    2 days of 2016, about 20 days of February and March 2018, and about
    20 days of May and September to November 2019. They are kept for
    the later cleaning.

    The values of 2019 slip against their hours, as their daily profile
    against that of the same month of the other years shows: most days
    from January to March are an hour early, and most days of August
    and September, and some of October to December, an hour late, from
    31 July, whose hour 24 has the same value as the hour 1 of 1 August
    (19,741 MW). The days in between are at their hours, and the shifts
    change from day to day, as in January 2020, the last month whose
    days slip. So each day from 2019-01-01 to 2020-01-31 is compared
    with the usual profile of its time of year, the median of the
    profiles of the days of the other years within 15 days of it, each
    divided by its mean. A day moves by the shift of up to 2 hours that
    makes it closest to the usual profile, if that halves its squared
    difference from it, over the hours that stay within the day for all
    shifts. A value that a move brings onto the hour of another value is
    left out, and the hour that it leaves has no value.

    ISMO, which took over the system operation of NTDC, publishes the
    hourly demand from July 2024 (see ismo.py).

    The load leaves out K-Electric, so its data has same_area false in
    the yaml file: it does not cover the whole shape of Pakistan.

    Source: https://www.kaggle.com/datasets/tentative/ntdc-dataset
    Source: https://web.archive.org/web/20260804193104/https://www.kaggle.com/datasets/tentative/ntdc-dataset
    Source: https://doi.org/10.5281/zenodo.24023127
"""

import datetime as dt
import logging

import numpy as np
import pandas as pd

import utils.fetcher
import utils.time_series


def _correct_days(starts: pd.Series) -> pd.Series:
    """
    Correct the times of the rows with the date of another day.

    A row whose time is out of order with the rows before or after it
    moves by the day, before or after, that brings it closest to the
    times that the three rows on each side give for it. The rows next to
    gaps in the data are in order, so they do not move.

    Parameters
    ----------
    starts : pandas.Series
        The starts of the hours of the rows, in the order of the file.

    Returns
    -------
    pandas.Series
        The starts of the hours, with the days corrected.
    """
    hours = pd.Series(
        ((starts - starts.iloc[0]) / pd.Timedelta(hours=1)).to_numpy()
    )
    out_of_order = (hours <= hours.cummax().shift(1)) | (
        hours >= hours[::-1].cummin()[::-1].shift(-1)
    )
    expected_hours = pd.concat(
        [hours.shift(rows) + rows for rows in (-3, -2, -1, 1, 2, 3)], axis=1
    ).median(axis=1)
    days = ((expected_hours - hours) / 24).round()
    days = days.where(out_of_order & days.abs().eq(1), 0)
    return starts + pd.to_timedelta(days.to_numpy(), unit="D")


# The days whose values slip against their hours, the largest slip in
# hours, the share of the squared difference from the usual profile
# that a slip needs to leave, the days around a day of the year of its
# usual profile, and the days of the other years that it needs.
SLIPPED_DAYS = (pd.Timestamp("2019-01-01"), pd.Timestamp("2020-01-31"))
MAX_SLIP = 2
SLIP_SHARE = 0.5
PROFILE_DAYS = 15
MIN_PROFILE_DAYS = 10


def _get_slip(profile: np.ndarray, usual: np.ndarray) -> int:
    """
    Get the slip of a daily profile against the usual profile.

    Parameters
    ----------
    profile : numpy.ndarray
        The 24 hourly values of the day, divided by their mean.
    usual : numpy.ndarray
        The usual 24 hourly values, divided by their mean.

    Returns
    -------
    int
        The hours by which the day is late, negative if it is early, or
        0 if no slip halves its squared difference from the usual one.
    """
    hours = slice(MAX_SLIP, 24 - MAX_SLIP)
    differences = {
        slip: float(
            ((profile[hours] - np.roll(usual, slip)[hours]) ** 2).sum()
        )
        for slip in range(-MAX_SLIP, MAX_SLIP + 1)
    }
    slip = min(differences, key=lambda key: differences[key])
    if slip != 0 and differences[slip] < SLIP_SHARE * differences[0]:
        return slip
    return 0


def _correct_slipped_days(load: pd.Series) -> pd.Series:
    """
    Move the days that slip against their hours back to them.

    Parameters
    ----------
    load : pandas.Series
        The load at the starts of the hours, in local time.

    Returns
    -------
    pandas.Series
        The load with the slipped days moved, without the values that
        they bring onto the hours of the days that do not move.
    """
    starts = pd.DatetimeIndex(load.index)
    table = pd.DataFrame(
        {
            "day": starts.normalize(),
            "hour": starts.hour,
            "load": load.to_numpy(),
        }
    ).pivot_table(index="day", columns="hour", values="load")
    table = table.dropna()
    profiles = table.div(table.mean(axis=1), axis=0)
    days = pd.DatetimeIndex(profiles.index)
    slipping = (days >= SLIPPED_DAYS[0]) & (days <= SLIPPED_DAYS[1])
    others = profiles[~slipping]
    other_days = pd.DatetimeIndex(others.index)
    moves: dict[pd.Timestamp, int] = {}
    for day in days[slipping]:
        apart = (other_days.day_of_year - day.day_of_year + 182) % 365 - 182
        usual = others[np.abs(apart) <= PROFILE_DAYS]
        if len(usual) >= MIN_PROFILE_DAYS:
            moves[day] = -_get_slip(
                profiles.loc[day].to_numpy(), usual.median().to_numpy()
            )
    hours = (
        pd.Series(moves, dtype="int64")
        .reindex(starts.normalize(), fill_value=0)
        .to_numpy()
    )
    moved = pd.Series(
        load.to_numpy(), index=starts + pd.to_timedelta(hours, unit="h")
    )
    kept = moved[hours == 0]
    brought = moved[hours != 0]
    brought = brought[
        ~brought.index.isin(kept.index) & ~brought.index.duplicated(keep=False)
    ]
    if (hours != 0).any():
        logging.info(
            f"{sum(move != 0 for move in moves.values())} days of NTDC "
            "slip against their hours "
            "and are moved back to them."
        )
    return pd.concat([kept, brought]).sort_index()


def get_available_requests(
    code: str, start_date: dt.date, end_date: dt.date
) -> list[None]:
    """
    Get the available requests.

    The data is downloaded at once from a single file, so there is a
    single request, without parameters.

    Parameters
    ----------
    code : str
        The code of Pakistan.
    start_date : datetime.date
        The first day of the data.
    end_date : datetime.date
        The last day of the data.

    Returns
    -------
    list[None]
        The single request.
    """
    return [None]


def get_url() -> str:
    """
    Get the URL of the electricity demand data for Pakistan.

    Returns
    -------
    str
        The URL of the electricity demand data.
    """
    return "https://zenodo.org/records/24023127/files/NTDC_2015_2020.csv?download=1"


def download_and_extract_data_for_request(
    request: None, code: str
) -> pd.Series:
    """
    Download and extract electricity demand data.

    Parameters
    ----------
    request : None
        The single request of the data, without parameters.
    code : str
        The code of Pakistan.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    dataset = utils.fetcher.fetch_dataframe(get_url(), "csv")

    # Remove the thousands separators and read the values as numbers.
    # The rows without a number are left out.
    load = pd.to_numeric(
        dataset["SYSLOAD"].astype(str).str.replace(",", ""),
        errors="coerce",
    )
    not_numbers = dataset["SYSLOAD"][load.isna() & dataset["SYSLOAD"].notna()]
    if not not_numbers.empty:
        logging.warning(
            f"{len(not_numbers)} values of NTDC are not numbers and are "
            f"left out, such as {not_numbers.iloc[0]!r}."
        )

    has_number = load.notna().to_numpy()
    dataset, load = dataset[has_number], load[has_number]

    # Define the starts of the hours, with the days of the rows labelled
    # with another day corrected, which depends on the order of the
    # rows.
    starts = _correct_days(
        pd.to_datetime(
            dataset["DATE"].astype(str)
            + " "
            + (dataset["HOUR"].astype(str).astype(int) - 1).astype(str),
            format="%d/%m/%Y %H",
        )
    )

    # Keep the first value of each hour, and move the days that slip
    # against their hours back to them.
    load_by_hour = pd.Series(
        load.to_numpy(dtype="float64"), index=pd.DatetimeIndex(starts)
    )
    electricity_demand_time_series = _correct_slipped_days(
        load_by_hour[~load_by_hour.index.duplicated()].sort_index()
    )

    # Move the times to the ends of the hours, in local time.
    electricity_demand_time_series = (
        utils.time_series.localize_interval_starts(
            electricity_demand_time_series,
            "Asia/Karachi",
            pd.Timedelta(hours=1),
        )
    )

    return electricity_demand_time_series

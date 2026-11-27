"""
License: AGPL-3.0.

Description:

    This module tells which hours fall on a public holiday or on a
    weekend day of a country or subdivision, in local time, from the
    holidays package. The models use the holidays to see the days on
    which the demand drops as on a Sunday, which their hour, weekend
    and month features cannot tell. The weekend days are those of the
    country, such as Friday and Saturday in Saudi Arabia since 2013,
    and Saturday and Sunday in a country that the package does not
    know.

    India and its states have only the holidays in SELECTED_HOLIDAYS.
    From 2017 to 2025, the weekday demand of its states dropped by a
    median of 5 to 7% on these six days, against the same weekday one
    and two weeks around them, and by less than 3%, or not at all, on
    its other public holidays. The package has the dates of Holi, Diwali
    and Dussehra, which follow the Hindu lunisolar calendar, only for
    the years of its tables (2001 to 2035 in version 0.107): the other
    years have none of them, and the log says so.
"""

import datetime as dt
import functools
import logging
import unicodedata

import holidays
import numpy as np
import pandas as pd
import pycountry

import utils.codes
import utils.time_zones

# The language of the names of the holidays. The package otherwise
# names them in the language of the system, if it has it.
LANGUAGE = "en_US"

# The weekend days of a country that the holidays package does not
# know, Saturday and Sunday, as numbers of datetime.date.weekday.
DEFAULT_WEEKEND = frozenset({5, 6})

# The only public holidays of some countries, by their ISO alpha-3
# code, as the holidays package names them in the national calendar,
# in LANGUAGE.
SELECTED_HOLIDAYS = {
    "IND": frozenset(
        {
            "Republic Day",
            "Independence Day",
            "Mahatma Gandhi's Birthday",
            "Holi",
            "Diwali",
            "Dussehra",
        }
    ),
}


def _normalize(name: str) -> str:
    """
    Normalize a name to compare it, without accents and case.

    Parameters
    ----------
    name : str
        The name.

    Returns
    -------
    str
        The name in lower case, without accents.
    """
    decomposed = unicodedata.normalize("NFKD", name)
    return "".join(
        c for c in decomposed if not unicodedata.combining(c)
    ).lower()


@functools.cache
def get_holiday_calendar(code: str) -> holidays.HolidayBase | None:
    """
    Get the calendar of the public holidays of a country or subdivision.

    Parameters
    ----------
    code : str
        The code of the country or subdivision, such as "FRA" or
        "IND_PB".

    Returns
    -------
    holidays.HolidayBase | None
        The public holidays of the country, and of the subdivision if it
        is an official subdivision that the package knows and the
        country has not selected holidays, or None if the package does
        not know the country.

    Notes
    -----
    A subdivision is official if it has the code and the name of a
    subdivision of ISO 3166-2. Many subdivisions are regions of system
    operators that use the code of another subdivision, such as New
    England (USA_NE, the code of Nebraska), and have only the holidays
    of their country. A country that the package does not know is
    reported in the log.
    """
    country_code, _, subdivision_code = code.partition("_")
    try:
        alpha_2 = utils.codes.get_iso_alpha_2_code(country_code)
    except KeyError:
        alpha_2 = None
    supported = holidays.list_supported_countries()
    if alpha_2 not in supported:
        logging.warning(
            f"The public holidays of {code} are not known, so it has none."
        )
        return None

    subdivision = None
    if (
        country_code not in SELECTED_HOLIDAYS
        and subdivision_code in supported[alpha_2]
    ):
        official = pycountry.subdivisions.get(
            code=f"{alpha_2}-{subdivision_code}"
        )
        if official is not None and _normalize(official.name) == _normalize(
            utils.codes.get_name_from_code(code)
        ):
            subdivision = subdivision_code
    return holidays.country_holidays(
        alpha_2, subdiv=subdivision, language=LANGUAGE
    )


def _get_local_days(times: pd.Series, code: str) -> np.ndarray:
    """
    Get the local days of the starts of hours of a code.

    Parameters
    ----------
    times : pandas.Series
        The ends of the hours, in UTC without time zone.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    numpy.ndarray
        The day, as a datetime.date, of the start of each hour in the
        local time of the code.
    """
    return (
        (pd.DatetimeIndex(times) - pd.Timedelta(hours=1))
        .tz_localize("UTC")
        .tz_convert(utils.time_zones.get_time_zone(code))
        .date
    )


def _warn_of_missing_selected_holidays(
    calendar: holidays.HolidayBase,
    selected: frozenset[str],
    years: set[int],
    code: str,
) -> None:
    """
    Log the selected holidays that the calendar lacks in some years.

    Parameters
    ----------
    calendar : holidays.HolidayBase
        The calendar of the code, with the years already populated.
    selected : frozenset[str]
        The selected holidays of the country of the code.
    years : set[int]
        The years of the hours.
    code : str
        The code of the country or subdivision.

    Notes
    -----
    The package has the dates of the holidays of lunisolar calendars,
    such as Holi, Diwali and Dussehra, only for the years of its
    tables, and gives no date for the other years.
    """
    missing: dict[str, list[int]] = {}
    for name in sorted(selected):
        holiday_years = {
            day.year for day in calendar.get_named(name, lookup="exact")
        }
        missing_years = sorted(years - holiday_years)
        if missing_years:
            missing[name] = missing_years
    if missing:
        logging.warning(
            f"The holidays package has no date of some public holidays of "
            f"{code}, so these years have none of them: "
            + "; ".join(
                f"{name} in {', '.join(map(str, missing_years))}"
                for name, missing_years in missing.items()
            )
            + "."
        )


def get_holiday_indicator(times: pd.Series, code: str) -> np.ndarray:
    """
    Tell which hours are on a public holiday of a code.

    Parameters
    ----------
    times : pandas.Series
        The ends of the hours, in UTC without time zone.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    numpy.ndarray
        1 for the hours that start on a public holiday in local time,
        only a selected one for a country with selected holidays, 0 for
        the others.

    Notes
    -----
    A selected holiday that the package has no date of in a year of
    the hours is reported in the log.
    """
    calendar = get_holiday_calendar(code)
    selected = SELECTED_HOLIDAYS.get(code.split("_", maxsplit=1)[0])
    if calendar is None:
        return np.zeros(len(times), dtype=int)
    days = _get_local_days(times, code)
    unique_days = pd.unique(days)
    holiday_days = {
        day
        for day in unique_days
        if day in calendar
        and (selected is None or selected & set(calendar.get_list(day)))
    }
    if selected is not None:
        _warn_of_missing_selected_holidays(
            calendar, selected, {day.year for day in unique_days}, code
        )
    return np.fromiter(
        (day in holiday_days for day in days), dtype=int, count=len(days)
    )


def get_weekend_indicator(times: pd.Series, code: str) -> np.ndarray:
    """
    Tell which hours are on a weekend day of a code.

    Parameters
    ----------
    times : pandas.Series
        The ends of the hours, in UTC without time zone.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    numpy.ndarray
        1 for the hours that start on a weekend day in local time, 0 for
        the others.

    Notes
    -----
    The weekend days are those of the calendar of the code (see
    get_holiday_calendar), on the date of each day, since some
    countries changed them, such as the United Arab Emirates from
    Friday and Saturday to Saturday and Sunday in 2022. A subdivision
    with its own calendar has its own weekend, such as the states of
    Malaysia whose weekend is Friday and Saturday. A country that the
    package does not know has DEFAULT_WEEKEND.
    """
    calendar = get_holiday_calendar(code)
    days = _get_local_days(times, code)
    weekend_days: set[dt.date] = {
        day
        for day in pd.unique(days)
        if (
            day.weekday() in DEFAULT_WEEKEND
            if calendar is None
            else calendar.is_weekend(day)
        )
    }
    return np.fromiter(
        (day in weekend_days for day in days), dtype=int, count=len(days)
    )

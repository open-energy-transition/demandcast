"""
License: AGPL-3.0.

Description:

    This module tells which hours fall on a public holiday of a country
    or subdivision, in local time, from the holidays package. The models
    use it to see the days on which the demand drops as on a Sunday,
    which their hour, weekend and month features cannot tell.

    A subdivision also has its own holidays if it is the official
    subdivision (ISO 3166-2) of the same code and name. Many
    subdivisions are regions of system operators that use the code of
    another subdivision, such as New England (USA_NE, the code of
    Nebraska), and have only the holidays of their country. A country
    that the package does not know has none, which the log reports.

    India and its states have only the holidays in SELECTED_HOLIDAYS.
    From 2017 to 2025, the weekday demand of its states dropped by a
    median of 5 to 7% on these six days, against the same weekday one
    and two weeks around them, and by less than 3%, or not at all, on
    its other public holidays.
"""

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


def get_holiday_indicator(times: pd.Series, code: str) -> np.ndarray:
    """
    Tell which hours are on a public holiday of a country or region.

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
    """
    calendar = get_holiday_calendar(code)
    selected = SELECTED_HOLIDAYS.get(code.split("_", maxsplit=1)[0])
    if calendar is None:
        return np.zeros(len(times), dtype=int)
    days = (
        (pd.DatetimeIndex(times) - pd.Timedelta(hours=1))
        .tz_localize("UTC")
        .tz_convert(utils.time_zones.get_time_zone(code))
        .date
    )
    unique_days = pd.unique(days)
    holiday_days = {
        day
        for day in unique_days
        if day in calendar
        and (selected is None or selected & set(calendar.get_list(day)))
    }
    return np.fromiter(
        (day in holiday_days for day in days), dtype=int, count=len(days)
    )

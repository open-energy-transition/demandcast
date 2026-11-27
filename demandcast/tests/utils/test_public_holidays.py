"""
License: AGPL-3.0.

Description:

    Tests of the public holidays of the countries and subdivisions.
"""

import datetime as dt

import pandas as pd
import pytest

import utils.public_holidays


def test_holiday_indicator_in_local_time():
    """
    Test that an hour is on a holiday by its start in local time.

    In Paris (UTC+1 in winter), the hour that ends at 23:00 UTC on 24
    December starts at 23:00 local time, before Christmas; the next one
    starts at midnight, on Christmas.
    """
    times = pd.Series(
        pd.to_datetime(
            ["2025-12-24 23:00", "2025-12-25 00:00", "2025-12-26 12:00"]
        )
    )

    assert utils.public_holidays.get_holiday_indicator(
        times, "FRA"
    ).tolist() == [0, 1, 0]


def test_holidays_of_subdivisions():
    """
    Test that only official subdivisions have their own holidays.

    Ontario and New South Wales are the provinces and states of the
    same codes, while New England (USA_NE) has the code of Nebraska, and
    only has the holidays of the United States. Punjab (IND_PB) is a
    state of India, which has only selected national holidays.
    """
    subdivisions = {
        code: getattr(
            utils.public_holidays.get_holiday_calendar(code), "subdiv", "none"
        )
        for code in ("CAN_ON", "AUS_NSW", "USA_NE", "IND_PB")
    }

    assert subdivisions == {
        "CAN_ON": "ON",
        "AUS_NSW": "NSW",
        "USA_NE": None,
        "IND_PB": None,
    }


def test_selected_holidays_of_india():
    """
    Test that India and its states have only the selected holidays.

    In 2024, Republic Day (26 January) and Diwali (31 October) are
    holidays, but not Christmas, of the central list, nor the birthday
    of Guru Gobind Singh (17 January), of Punjab.
    """
    times = pd.Series(
        pd.to_datetime(
            [
                "2024-01-26 12:00",
                "2024-10-31 12:00",
                "2024-12-25 12:00",
                "2024-01-17 12:00",
            ]
        )
    )

    for code in ("IND", "IND_PB"):
        assert utils.public_holidays.get_holiday_indicator(
            times, code
        ).tolist() == [1, 1, 0, 0]


def test_names_of_holidays_in_any_language_of_the_system(monkeypatch):
    """
    Test that the holidays have the same names in any system.

    Without a language, the package names the holidays of India in the
    language of the system: "Diwali" in American English, and "Diwali
    (Deepavali)" in Indian English, which the selection would miss.
    """
    utils.public_holidays.get_holiday_calendar.cache_clear()
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("LC_ALL", "C.UTF-8")

    calendar = utils.public_holidays.get_holiday_calendar("IND")
    utils.public_holidays.get_holiday_calendar.cache_clear()

    assert calendar is not None
    assert calendar.get_list(dt.date(2024, 10, 31)) == ["Diwali"]


def test_country_without_holidays(caplog):
    """Test that a country that the package does not know has none."""
    times = pd.Series(pd.to_datetime(["2025-12-25 12:00"]))

    with caplog.at_level("WARNING"):
        indicator = utils.public_holidays.get_holiday_indicator(times, "XXX")

    assert indicator.tolist() == [0]
    assert "public holidays of XXX are not known" in caplog.text


# The package warns that it has the holidays of India only for some
# years, which the test checks in the log of DemandCast.
@pytest.mark.filterwarnings("ignore:Requested Holidays are available only")
def test_selected_holidays_without_dates_are_logged(caplog):
    """
    Test that the years without dates of selected holidays are logged.

    The package has the dates of Holi, Diwali and Dussehra only for the
    years of its tables, which end before 2040: India then has only its
    three other selected holidays, such as Republic Day.
    """
    times = pd.Series(pd.to_datetime(["2024-01-26 12:00", "2040-01-26 12:00"]))

    with caplog.at_level("WARNING"):
        indicator = utils.public_holidays.get_holiday_indicator(times, "IND")

    assert indicator.tolist() == [1, 1]
    assert caplog.messages == [
        (
            "The holidays package has no date of some public holidays of "
            "IND, so these years have none of them: Diwali in 2040; "
            "Dussehra in 2040; Holi in 2040."
        )
    ]


def test_weekend_of_the_country_in_local_time():
    """
    Test that the weekend days are those of the country, in local time.

    Saudi Arabia (UTC+3) moved its weekend from Thursday and Friday to
    Friday and Saturday in 2013, and the United Arab Emirates from
    Friday and Saturday to Saturday and Sunday in 2022. The hour that
    ends at 21:00 UTC on Wednesday 6 June 2012 starts at 23:00 in
    Riyadh, on Wednesday; the next one starts on Thursday.
    """
    # The Thursday to Sunday of a week of June of each year.
    first_days = {2012: 7, 2021: 10, 2023: 8, 2024: 6}
    times = {
        year: pd.Series(
            pd.date_range(f"{year}-06-{first_day} 12:00", periods=4, freq="D")
        )
        for year, first_day in first_days.items()
    }
    weekend = utils.public_holidays.get_weekend_indicator

    assert weekend(times[2012], "SAU").tolist() == [1, 1, 0, 0]
    assert weekend(times[2024], "SAU").tolist() == [0, 1, 1, 0]
    assert weekend(times[2021], "ARE").tolist() == [0, 1, 1, 0]
    assert weekend(times[2023], "ARE").tolist() == [0, 0, 1, 1]
    assert weekend(times[2024], "FRA").tolist() == [0, 0, 1, 1]
    assert weekend(
        pd.Series(pd.to_datetime(["2012-06-06 21:00", "2012-06-06 22:00"])),
        "SAU",
    ).tolist() == [0, 1]


def test_weekend_of_a_country_without_holidays(monkeypatch):
    """
    Test that a country that the package does not know has a weekend.

    Its weekend is Saturday and Sunday: 7 to 10 June 2024 are Friday to
    Monday.
    """
    monkeypatch.setattr(
        utils.public_holidays, "get_holiday_calendar", lambda _code: None
    )
    times = pd.Series(
        pd.to_datetime([f"2024-06-{day} 12:00" for day in range(7, 11)])
    )

    assert utils.public_holidays.get_weekend_indicator(
        times, "SAU"
    ).tolist() == [0, 1, 1, 0]

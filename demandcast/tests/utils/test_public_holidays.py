"""
License: AGPL-3.0.

Description:

    Tests of the public holidays of the countries and subdivisions.
"""

import datetime

import pandas as pd

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
    assert calendar.get_list(datetime.date(2024, 10, 31)) == ["Diwali"]


def test_country_without_holidays(caplog):
    """Test that a country that the package does not know has none."""
    times = pd.Series(pd.to_datetime(["2025-12-25 12:00"]))

    with caplog.at_level("WARNING"):
        indicator = utils.public_holidays.get_holiday_indicator(times, "XXX")

    assert indicator.tolist() == [0]
    assert "public holidays of XXX are not known" in caplog.text

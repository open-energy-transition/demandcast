"""
License: AGPL-3.0.

Description:

    Tests for the classes of the years of data of the map of the
    countries and subdivisions with electricity demand data.
"""

import datetime as dt

from figures import map_of_available_entities


def test_get_classes_of_years():
    """
    Test that each code is in the class of its years of data.

    The years of a code are those of all its periods: "I" has two
    periods of 3 years, so 6 years.
    """
    start = dt.date(2000, 1, 1)
    periods = {
        code: [(start, start + dt.timedelta(days=round(365 * years) - 1))]
        for code, years in {
            "A": 0.1,
            "B": 4.9,
            "C": 5,
            "D": 9.9,
            "E": 10,
            "F": 19.9,
            "G": 20,
            "H": 40,
        }.items()
    }
    periods["I"] = [
        (dt.date(2000, 1, 1), dt.date(2002, 12, 31)),
        (dt.date(2010, 1, 1), dt.date(2012, 12, 31)),
    ]

    assert map_of_available_entities.get_classes_of_years(periods) == {
        "A": 0,
        "B": 0,
        "C": 1,
        "D": 1,
        "E": 2,
        "F": 2,
        "G": 3,
        "H": 3,
        "I": 1,
    }

"""
License: AGPL-3.0.

Description:

    Tests for the classes of the years of data of the map of the
    countries and subdivisions with electricity demand data.
"""

import pandas as pd

from figures import map_of_available_entities


def test_get_classes_of_years():
    """Test that each code is in the class of its years of data."""
    start = pd.Timestamp("2000-01-01")
    date_ranges = {
        code: (start, start + pd.Timedelta(days=365 * years))
        for code, years in {
            "A": 0,
            "B": 4.9,
            "C": 5,
            "D": 9.9,
            "E": 10,
            "F": 19.9,
            "G": 20,
            "H": 40,
        }.items()
    }

    assert map_of_available_entities.get_classes_of_years(date_ranges) == {
        "A": 0,
        "B": 0,
        "C": 1,
        "D": 1,
        "E": 2,
        "F": 2,
        "G": 3,
        "H": 3,
    }

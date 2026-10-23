"""
License: AGPL-3.0.

Description:

    Tests of the figures and numbers of the "Current state" page of the
    documentation.
"""

import datetime
import os
from unittest.mock import patch

import pytest

from figures import status

DATE_RANGES = {
    "FRA": (datetime.date(2015, 1, 1), datetime.date(2024, 12, 31)),
    "USA_TEX": (datetime.date(2019, 1, 1), datetime.date(2024, 12, 31)),
    "USA_CAL": (datetime.date(2019, 1, 1), datetime.date(2024, 12, 31)),
    "DEU": (datetime.date(2010, 1, 1), datetime.date(2010, 12, 31)),
}

NUMBERS = status.Numbers(
    date=datetime.date(2026, 10, 23),
    countries=1,
    subdivisions=2,
    countries_covered=2,
    data_sources=3,
    years=1234,
    first_year=2015,
)


def test_get_numbers():
    """Test that the codes of the data sources are counted."""
    with (
        patch.object(
            status.utils.data_sources,
            "read_all_date_ranges",
            return_value=DATE_RANGES,
        ),
        patch.object(
            status.utils.data_sources,
            "read_all_codes_with_electricity_demand_data",
            return_value=["FRA", "USA_CAL", "USA_TEX"],
        ),
        patch.object(
            status.utils.data_sources,
            "read_data_sources",
            return_value=["eia", "entsoe", "caiso"],
        ),
    ):
        numbers = status.get_numbers(datetime.date(2026, 10, 23))

    assert numbers == status.Numbers(
        date=datetime.date(2026, 10, 23),
        countries=1,
        subdivisions=2,
        countries_covered=2,
        data_sources=3,
        years=22,
        first_year=2015,
    )


def test_describe():
    """Test the sentence of the numbers."""
    assert status.describe(NUMBERS) == (
        "As of 23 October 2026, DemandCast has retrieval modules for the "
        "hourly electricity demand of **1 countries and 2 subdivisions**, "
        "in 2 countries, from **3 data sources**, with about **1,234 "
        "years of data** in total since 2015, in the periods that the "
        "data sources cover, before the cleaning and the selection of the "
        "complete years for training."
    )


def test_update_readme(tmp_path):
    """Test that only the block between the markers is replaced."""
    readme_file = tmp_path / "README.md"
    readme_file.write_text(
        f"# Title\n\n{status.STATUS_START}\nold\n{status.STATUS_END}\n\nEnd\n",
        encoding="utf-8",
    )

    status.update_readme(str(readme_file), "new")
    status.update_readme(str(readme_file), "newer")

    assert readme_file.read_text(encoding="utf-8") == (
        f"# Title\n\n{status.STATUS_START}\nnewer\n{status.STATUS_END}\n\n"
        "End\n"
    )


def test_update_readme_without_markers(tmp_path):
    """Test that a README without the markers is refused."""
    readme_file = tmp_path / "README.md"
    readme_file.write_text("# Title\n", encoding="utf-8")

    with pytest.raises(ValueError, match="markers"):
        status.update_readme(str(readme_file), "new")


def test_readme_has_the_markers():
    """Test that the README of the repository has the block."""
    with open(status.utils.paths.README_FILE, encoding="utf-8") as file:
        readme = file.read()

    assert readme.index(status.STATUS_START) < readme.index(status.STATUS_END)


def test_plot(tmp_path):
    """Test that the figures and numbers go to the page and README."""
    figure_directory = tmp_path / "figures"
    figure_directory.mkdir()
    status_folder = tmp_path / "status"
    readme_file = tmp_path / "README.md"
    readme_file.write_text(
        f"{status.STATUS_START}\n{status.STATUS_END}\n", encoding="utf-8"
    )

    def draw(folder):
        for file_name in status.FIGURE_FILES:
            with open(os.path.join(folder, file_name), "w") as file:
                file.write(file_name)

    with (
        patch.object(
            status.figures.map_of_available_entities, "plot", side_effect=draw
        ),
        patch.object(status.figures.data_availability, "plot"),
        patch.object(status, "get_numbers", return_value=NUMBERS),
    ):
        status.plot(
            str(figure_directory), str(status_folder), str(readme_file)
        )

    assert sorted(os.listdir(status_folder)) == sorted(
        [*status.FIGURE_FILES, status.NUMBERS_FILE]
    )
    text = status.describe(NUMBERS)
    assert (status_folder / status.NUMBERS_FILE).read_text(
        encoding="utf-8"
    ) == text + "\n"
    assert text in readme_file.read_text(encoding="utf-8")

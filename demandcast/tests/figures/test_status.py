"""
License: AGPL-3.0.

Description:

    Tests of the figures and numbers of the "Current state" page of the
    documentation.
"""

import datetime as dt
import os
from unittest.mock import patch

import pandas as pd
import pytest

import utils.paths
from figures import status

DATE_RANGES = {
    "FRA": (dt.date(2015, 1, 1), dt.date(2024, 12, 31)),
    "USA_TEX": (dt.date(2019, 1, 1), dt.date(2024, 12, 31)),
    "USA_CAL": (dt.date(2019, 1, 1), dt.date(2024, 12, 31)),
    "DEU": (dt.date(2010, 1, 1), dt.date(2010, 12, 31)),
}

NUMBERS = status.Numbers(
    date=dt.date(2026, 10, 23),
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
        numbers = status.get_numbers(dt.date(2026, 10, 23))

    assert numbers == status.Numbers(
        date=dt.date(2026, 10, 23),
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

    # Without results of the models, the page says so.
    assert sorted(os.listdir(status_folder)) == sorted(
        [*status.FIGURE_FILES, status.NUMBERS_FILE, status.ML_RESULTS_FILE]
    )
    assert (status_folder / status.ML_RESULTS_FILE).read_text(
        encoding="utf-8"
    ) == "The models have no results yet.\n"
    text = status.describe(NUMBERS)
    assert (status_folder / status.NUMBERS_FILE).read_text(
        encoding="utf-8"
    ) == text + "\n"
    assert text in readme_file.read_text(encoding="utf-8")


def _summary(medians: dict[tuple[str, str], float]) -> pd.DataFrame:
    """
    Make a summary of results with the median WAPE of some groups.

    Returns
    -------
    pandas.DataFrame
        The summary, with the columns "Group", "Value" and "Median
        WAPE".
    """
    return pd.DataFrame(
        [
            {"Group": group, "Value": value, "Median WAPE": median}
            for (group, value), median in medians.items()
        ]
    )


def test_describe_ml_results():
    """Test the paragraph of the errors of the models."""
    validation = _summary(
        {
            ("All", "All"): 0.071,
            ("Seen in training", "Yes"): 0.066,
            ("Seen in training", "No"): 0.112,
        }
    )
    cross_validation = _summary({("All", "All"): 0.1})

    assert status.describe_ml_results(
        ("xgboost_model_20261031_212342", validation),
        ("xgboost", cross_validation),
    ) == (
        "In the validation of the XGBoost model 20261031_212342, the "
        "median WAPE of the countries and subdivisions is **7.1%**: 6.6% "
        "for those whose other years the model saw in training, and 11.2% "
        "for those that it never saw. In the cross-validation of XGBoost, "
        "which leaves each country out of the training in turn, it is "
        "**10.0%**, the error to expect for a country without data."
    )
    assert status.describe_ml_results(None, None) == (
        "The models have no results yet."
    )


def test_plot_ml_results(tmp_path):
    """
    Test that the latest results of the models go to the page.

    The figures of the latest validation are copied with fixed names,
    and a case without results, here the cross-validation, has none.
    """
    folder = os.path.join(
        utils.paths.get_results_folder("validation"),
        "with_xgboost_model_1",
        "using_data_1",
    )
    os.makedirs(folder)
    pd.DataFrame(
        {"Entity code": ["FRA"], "Testing MAPE": [0.1], "Testing WAPE": [0.1]}
    ).to_parquet(os.path.join(folder, "all_20261031_000000.parquet"))
    summary = _summary({("All", "All"): 0.1})
    summary.to_csv(
        os.path.join(folder, "summary_20261031_000000.csv"), index=False
    )
    status_folder = tmp_path / "status"
    status_folder.mkdir()

    validation, cross_validation = status._plot_ml_results(
        str(tmp_path), str(status_folder)
    )

    assert validation is not None
    assert validation[0] == "xgboost_model_1"
    pd.testing.assert_frame_equal(validation[1], summary)
    assert cross_validation is None
    assert sorted(os.listdir(status_folder)) == sorted(
        status.ML_FIGURE_FILES["validation"]
    )


def test_latest_results_without_summary():
    """Test that results without a summary are not described."""
    folder = os.path.join(
        utils.paths.get_results_folder("cross_validation"),
        "with_xgboost",
        "using_data_1",
    )
    os.makedirs(folder)
    pd.DataFrame({"Entity code": ["FRA"]}).to_parquet(
        os.path.join(folder, "all_20261031_000000.parquet")
    )

    assert status._find_latest_results("cross_validation") is None

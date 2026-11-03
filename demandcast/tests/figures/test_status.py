"""
License: AGPL-3.0.

Description:

    Tests of the figures and numbers of the "Current state" page of the
    documentation.
"""

import datetime as dt
import os
from typing import Literal
from unittest.mock import patch

import pandas as pd
import pytest

import ml_models.files
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
        [
            *status.FIGURE_FILES,
            status.NUMBERS_FILE,
            *status.ML_RESULTS_FILES.values(),
        ]
    )
    assert [
        (status_folder / status.ML_RESULTS_FILES[case]).read_text(
            encoding="utf-8"
        )
        for case in ("validation", "cross_validation")
    ] == [
        "The models have no validation yet.\n",
        "The models have no cross-validation yet.\n",
    ]
    assert (status_folder / status.ML_RESULTS_FILES["model"]).read_text(
        encoding="utf-8"
    ) == "\n"
    text = status.describe(NUMBERS)
    assert (status_folder / status.NUMBERS_FILE).read_text(
        encoding="utf-8"
    ) == text + "\n"
    assert text in readme_file.read_text(encoding="utf-8")


def _summary(
    medians: dict[tuple[str, str], float], codes: int = 3
) -> pd.DataFrame:
    """
    Make a summary of results with the median WAPE of some groups.

    Returns
    -------
    pandas.DataFrame
        The summary, with the columns "Group", "Value", "Codes" and
        "Median WAPE".
    """
    return pd.DataFrame(
        [
            {
                "Group": group,
                "Value": value,
                "Codes": codes,
                "Median WAPE": median,
            }
            for (group, value), median in medians.items()
        ]
    )


def _results(
    summary: pd.DataFrame, manifest: dict | None = None
) -> ml_models.files.Results:
    """
    Make checked results with their summary and manifest.

    Returns
    -------
    ml_models.files.Results
        The results, without rows.
    """
    return ml_models.files.Results(
        "all_20261031_000000.parquet", pd.DataFrame(), summary, manifest
    )


@pytest.mark.parametrize(
    ("holdout", "description"),
    [
        (
            "country",
            (
                "leaves each country, with its subdivisions, out of the "
                "training in turn, and the median WAPE of the 3 held-out "
                "countries and subdivisions is **10.0%**, an estimate of the "
                "error for a country without data."
            ),
        ),
        (
            "entity",
            (
                "leaves each country or subdivision out of the training in "
                "turn, and the median WAPE of the 3 held-out countries and "
                "subdivisions is **10.0%**, an estimate of the error for a "
                "country or subdivision without data, whose country can have "
                "data of its other subdivisions."
            ),
        ),
    ],
)
def test_describe_cross_validation(holdout, description):
    """Test that the cross-validation is described by its holdout."""
    cross_validation = _summary({("All", "All"): 0.1})

    assert status.describe_cross_validation(
        ("xgboost", _results(cross_validation, {"holdout": holdout}))
    ) == ("The cross-validation of XGBoost " + description)
    assert status.describe_cross_validation(None) == (
        "The models have no cross-validation yet."
    )


def test_describe_model():
    """
    Test the paragraph of the models of the results.

    It names their algorithm, once, not the trained model.
    """
    summary = _summary({("All", "All"): 0.1})

    assert status.describe_model(
        ("xgboost_model_20261102_194204", _results(summary)),
        ("xgboost", _results(summary)),
    ) == (
        "The results below are those of XGBoost models, trained on the "
        "data of the countries and subdivisions above, without the data "
        "that each evaluation leaves out, which its section describes."
    )
    assert status.describe_model(None, ("lstm", _results(summary))).startswith(
        "The results below are those of LSTM models"
    )
    assert status.describe_model(None, None) == ""


def test_describe_validation():
    """Test the paragraph of the errors of the validation."""
    validation = _summary(
        {
            ("All", "All"): 0.071,
            ("Seen in training", "Yes"): 0.066,
            ("Seen in training", "No"): 0.112,
        }
    )

    assert status.describe_validation(
        ("xgboost_model_20261031_212342", _results(validation))
    ) == (
        "In the validation of XGBoost, the median WAPE of the countries "
        "and subdivisions is **7.1%**: 6.6% "
        "for those whose other years the model saw in training, and 11.2% "
        "for those that it never saw."
    )
    assert status.describe_validation(None) == (
        "The models have no validation yet."
    )


def _save_results(
    case: Literal["validation", "cross_validation"],
    version: str,
    summary: pd.DataFrame,
) -> str:
    """
    Save results of a case with their summary, predictions and manifest.

    The predictions are those of France in 2024.

    Returns
    -------
    str
        The path of the Parquet file of the results.
    """
    hours = pd.date_range("2024-01-01 00:00", "2024-12-31 23:00", freq="h")
    ml_models.files.save_results(
        case,
        pd.DataFrame(
            {
                "Entity code": ["FRA"],
                "Testing MAPE": [0.1],
                "Testing WAPE": [0.1],
            }
        ),
        version,
        "data_1",
        "all",
        summary=summary,
        predictions=pd.DataFrame(
            {
                "Entity code": "FRA",
                "Time (UTC)": hours,
                "Local year": 2024,
                "Load (MW)": 50000.0,
                "Forecast load (MW)": 51000.0,
            }
        ),
    )
    return str(
        ml_models.files.find_latest_results(
            utils.paths.get_results_folder(case), version
        )
    )


def test_plot_ml_results(tmp_path):
    """
    Test that the results of the models go to the page.

    The figures of the validation are copied with fixed names, and a
    case without results, here the cross-validation, has none.
    """
    summary = _summary({("All", "All"): 0.1})
    file_path = _save_results("validation", "xgboost_model_1", summary)
    status_folder = tmp_path / "status"
    status_folder.mkdir()

    validation, cross_validation = status._plot_ml_results(
        str(tmp_path), str(status_folder)
    )

    assert validation is not None
    assert validation[0] == "xgboost_model_1"
    assert validation[1].file_path == file_path
    assert validation[1].summary is not None
    pd.testing.assert_frame_equal(validation[1].summary, summary)
    assert cross_validation is None
    assert sorted(os.listdir(status_folder)) == sorted(
        status.ML_FIGURE_FILES["validation"]
    )


def test_given_results_are_published(monkeypatch):
    """
    Test that the given results are published, not the latest.

    The latest results are those with the latest time in their names.
    """
    monkeypatch.setattr(
        ml_models.files.pd.Timestamp,
        "now",
        lambda: pd.Timestamp("2026-11-01 00:00:00"),
    )
    latest = _save_results(
        "validation", "xgboost_model_2", _summary({("All", "All"): 0.2})
    )
    monkeypatch.setattr(
        ml_models.files.pd.Timestamp,
        "now",
        lambda: pd.Timestamp("2026-10-31 00:00:00"),
    )
    given = _save_results(
        "validation", "xgboost_model_1", _summary({("All", "All"): 0.1})
    )

    found = status._find_results("validation")
    assert found is not None
    assert (found[0], found[1].file_path) == ("xgboost_model_2", latest)
    found = status._find_results("validation", given)
    assert found is not None
    assert (found[0], found[1].file_path) == ("xgboost_model_1", given)


def test_changed_summary_is_not_published():
    """Test that a summary changed after its results is not read."""
    file_path = _save_results(
        "cross_validation", "xgboost", _summary({("All", "All"): 0.1})
    )
    summary_path = file_path.replace("all_", "summary_").replace(
        ".parquet", ".csv"
    )
    _summary({("All", "All"): 0.01}).to_csv(summary_path, index=False)

    with pytest.raises(ValueError, match="differs from the one"):
        status._find_results("cross_validation")


def test_results_without_summary():
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

    with pytest.raises(ValueError, match="no summary"):
        status._find_results("cross_validation")


def test_results_without_predictions():
    """Test that results without predictions are not described."""
    ml_models.files.save_results(
        "cross_validation",
        pd.DataFrame({"Entity code": ["FRA"], "Testing WAPE": [0.1]}),
        "xgboost",
        "data_1",
        "all",
        summary=_summary({("All", "All"): 0.1}),
    )

    with pytest.raises(ValueError, match="no predictions"):
        status._find_results("cross_validation")

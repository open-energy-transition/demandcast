"""
License: AGPL-3.0.

Description:

    Tests of the figures and numbers of the "Current state" page of the
    documentation.
"""

import dataclasses
import datetime as dt
import os
import re
from typing import Literal
from unittest.mock import patch

import pandas as pd
import pytest

import ml_models.files
import utils.paths
from figures import status

PERIODS = {
    "FRA": [
        (dt.date(2015, 1, 1), dt.date(2019, 12, 31)),
        (dt.date(2021, 1, 1), dt.date(2024, 12, 31)),
    ],
    "USA_TEX": [(dt.date(2019, 1, 1), dt.date(2024, 12, 31))],
    "USA_CAL": [(dt.date(2019, 1, 1), dt.date(2024, 12, 31))],
    "DEU": [(dt.date(2010, 1, 1), dt.date(2010, 12, 31))],
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
    """
    Test that the codes of the data sources are counted.

    The years are those of all the periods of each code: 9 for France,
    without 2020, and 6 for each of the two states.
    """
    with (
        patch.object(
            status.utils.data_sources,
            "read_all_periods",
            return_value=PERIODS,
        ),
        patch.object(
            status.utils.data_sources,
            "read_all_codes",
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
        years=21,
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


def test_replace_readme_block(tmp_path):
    """Test that only the block between the markers is replaced."""
    readme_file = tmp_path / "README.md"
    readme_file.write_text(
        f"# Title\n\n{status.STATUS_START}\nold\n{status.STATUS_END}\n\nEnd\n",
        encoding="utf-8",
    )

    readme_file.write_text(
        status.replace_readme_block(str(readme_file), "new"),
        encoding="utf-8",
    )

    assert status.replace_readme_block(str(readme_file), "newer") == (
        f"# Title\n\n{status.STATUS_START}\nnewer\n{status.STATUS_END}\n\n"
        "End\n"
    )


def test_replace_readme_block_without_markers(tmp_path):
    """Test that a README without the markers is refused."""
    readme_file = tmp_path / "README.md"
    readme_file.write_text("# Title\n", encoding="utf-8")

    with pytest.raises(ValueError, match="markers"):
        status.replace_readme_block(str(readme_file), "new")


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
        """Write each figure file with its name as content."""
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


def test_plot_keeps_the_page_of_cases_without_results(tmp_path):
    """
    Test that a case without results keeps its part of the page.

    Its figures and text, and the description of the models, stay as
    they were, while the numbers are new.
    """
    figure_directory = tmp_path / "figures"
    figure_directory.mkdir()
    status_folder = tmp_path / "status"
    status_folder.mkdir()
    old_files = {
        **{
            file_name: "old figure"
            for file_names in status.ML_FIGURE_FILES.values()
            for file_name in file_names
        },
        **dict.fromkeys(status.ML_RESULTS_FILES.values(), "old text\n"),
    }
    for file_name, content in old_files.items():
        (status_folder / file_name).write_text(content, encoding="utf-8")
    readme_file = tmp_path / "README.md"
    readme_file.write_text(
        f"{status.STATUS_START}\n{status.STATUS_END}\n", encoding="utf-8"
    )

    with (
        patch.object(status.figures.map_of_available_entities, "plot"),
        patch.object(status.figures.data_availability, "plot"),
        patch.object(status, "FIGURE_FILES", ()),
        patch.object(status, "get_numbers", return_value=NUMBERS),
    ):
        status.plot(
            str(figure_directory), str(status_folder), str(readme_file)
        )

    for file_name, content in old_files.items():
        assert (status_folder / file_name).read_text(
            encoding="utf-8"
        ) == content
    assert (status_folder / status.NUMBERS_FILE).read_text(
        encoding="utf-8"
    ) == status.describe(NUMBERS) + "\n"


def test_readme_is_written_after_the_page(tmp_path):
    """Test that a page that cannot be written leaves the README."""
    figure_directory = tmp_path / "figures"
    figure_directory.mkdir()
    # A file where the folder of the page should be.
    status_folder = tmp_path / "status"
    status_folder.write_text("", encoding="utf-8")
    readme = f"{status.STATUS_START}\nold\n{status.STATUS_END}\n"
    readme_file = tmp_path / "README.md"
    readme_file.write_text(readme, encoding="utf-8")

    with (
        patch.object(status.figures.map_of_available_entities, "plot"),
        patch.object(status.figures.data_availability, "plot"),
        patch.object(status, "FIGURE_FILES", ()),
        patch.object(status, "get_numbers", return_value=NUMBERS),
        pytest.raises(FileExistsError),
    ):
        status.plot(
            str(figure_directory), str(status_folder), str(readme_file)
        )

    assert readme_file.read_text(encoding="utf-8") == readme


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
        "Each trains XGBoost models on the data above, without the data "
        "that it scores them on, which its section describes."
    )
    assert status.describe_model(None, ("lstm", _results(summary))).startswith(
        "Each trains LSTM models"
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

    The figures of the validation are drawn for fixed names of the
    page, and a case without results, here the cross-validation, has
    none.
    """
    summary = _summary({("All", "All"): 0.1})
    file_path = _save_results("validation", "xgboost_model_1", summary)

    drawn_files, (validation, cross_validation) = status._plot_ml_results(
        str(tmp_path)
    )

    assert validation is not None
    assert validation[0] == "xgboost_model_1"
    assert validation[1].file_path == file_path
    assert validation[1].summary is not None
    pd.testing.assert_frame_equal(validation[1].summary, summary)
    assert cross_validation is None
    assert sorted(drawn_files) == sorted(status.ML_FIGURE_FILES["validation"])
    assert all(os.path.isfile(drawn) for drawn in drawn_files.values())


def test_failed_plot_writes_nothing(tmp_path):
    """
    Test that a failure of the figures of the models writes nothing.

    The README and the page keep their content when the results of the
    models cannot be described.
    """
    figure_directory = tmp_path / "figures"
    figure_directory.mkdir()
    status_folder = tmp_path / "status"
    readme = f"{status.STATUS_START}\nold\n{status.STATUS_END}\n"
    readme_file = tmp_path / "README.md"
    readme_file.write_text(readme, encoding="utf-8")

    with (
        patch.object(status.figures.map_of_available_entities, "plot"),
        patch.object(status.figures.data_availability, "plot"),
        patch.object(status, "get_numbers", return_value=NUMBERS),
        patch.object(
            status, "_find_results", side_effect=ValueError("no summary")
        ),
        pytest.raises(ValueError, match="no summary"),
    ):
        status.plot(
            str(figure_directory), str(status_folder), str(readme_file)
        )

    assert readme_file.read_text(encoding="utf-8") == readme
    assert not status_folder.exists()


def test_given_results_are_published(monkeypatch):
    """
    Test that the given results are published, not the latest.

    The latest results are those with the latest time in their names.
    """
    monkeypatch.setattr(
        pd.Timestamp,
        "now",
        lambda *_, **__: pd.Timestamp("2026-11-01 00:00:00"),
    )
    latest = _save_results(
        "validation", "xgboost_model_2", _summary({("All", "All"): 0.2})
    )
    monkeypatch.setattr(
        pd.Timestamp,
        "now",
        lambda *_, **__: pd.Timestamp("2026-10-31 00:00:00"),
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


def test_numbers_of_the_readme_are_current():
    """
    Test that the README and the status page give the current numbers.

    The numbers of the block of the README and of numbers.md are those
    of the YAML files of the data sources, but the years of data, which
    grow every day with the data sources that end today. A change of the
    data sources, such as a new one, also needs new numbers: the message
    gives them, to replace the block of the README and numbers.md.
    """
    with open(utils.paths.README_FILE, encoding="utf-8") as file:
        readme = file.read()
    block = readme[
        readme.index(status.STATUS_START) + len(status.STATUS_START) : (
            readme.index(status.STATUS_END)
        )
    ].strip()
    with open(
        os.path.join(utils.paths.STATUS_FOLDER, status.NUMBERS_FILE),
        encoding="utf-8",
    ) as file:
        numbers_page = file.read().strip()
    date_match = re.search(r"As of (\d{2} \w+ \d{4})", block)
    years_match = re.search(r"about \*\*([\d,]+) years", block)
    assert date_match is not None
    assert years_match is not None
    date = pd.Timestamp(date_match.group(1)).date()
    years = int(years_match.group(1).replace(",", ""))

    current = status.get_numbers(date)

    assert numbers_page == block
    assert status.describe(dataclasses.replace(current, years=years)) == (
        block
    ), (
        "The numbers of the README and of webpage/docs/status/numbers.md "
        "are not those of the data sources. Replace them with:\n"
        + status.describe(
            status.get_numbers(dt.datetime.now().astimezone().date())
        )
    )

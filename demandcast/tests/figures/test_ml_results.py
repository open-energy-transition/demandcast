"""
License: AGPL-3.0.

Description:

    Tests for the figures of the results of the machine learning
    models. They read the MAPE files of two example versions, in the
    folder mape_examples, and results saved as validate.py and
    cross_validate.py save them.
"""

import os
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

import utils.manifest
import utils.paths
from figures import ml_results

# The folder of the MAPE files of the example versions.
EXAMPLES_FOLDER = os.path.join(os.path.dirname(__file__), "mape_examples")


@pytest.fixture(autouse=True)
def _close_figures():
    """Close the figures that a test draws."""
    yield
    plt.close("all")


def test_plot_by_group_and_comparison(tmp_path):
    """Test that the two options are refused before any file is read."""
    with (
        patch.object(ml_results, "_read_errors") as read_mape,
        pytest.raises(ValueError, match="cannot be used together"),
    ):
        ml_results.plot(str(tmp_path), "a", "b", by_group=True)

    read_mape.assert_not_called()


def test_read_mape():
    """Test that the MAPE values are read in percent, by version."""
    groups = {"income": ["high_income"], "continent": ["AF"]}

    mape = ml_results._read_errors(
        EXAMPLES_FOLDER, "example1", "example2", False, groups, "MAPE"
    )
    assert list(mape.columns) == ["example1_all", "example2_all"]
    assert len(mape) == 95
    assert mape.loc["AT", "example1_all"] == pytest.approx(8.104806914070335)
    assert mape.loc["AT", "example2_all"] == pytest.approx(9.574320937012813)

    mape = ml_results._read_errors(
        EXAMPLES_FOLDER, "example1", None, True, groups, "MAPE"
    )
    assert list(mape.columns) == [
        "example1_all",
        "example1_high_income",
        "example1_AF",
    ]
    assert mape.loc["DZ", "example1_AF"] == pytest.approx(4.378211941703889)
    assert mape["example1_AF"].notna().sum() == 3

    # The earlier versions have no WAPE.
    with pytest.raises(ValueError, match="have no WAPE"):
        ml_results._read_errors(
            EXAMPLES_FOLDER, "example1", None, False, groups, "WAPE"
        )


@pytest.mark.parametrize(
    ("compare_with_version", "by_group", "file_names"),
    [
        (None, False, ["mape_example1.png"]),
        ("example2", False, ["mape_example1_vs_example2.png"]),
        (
            None,
            True,
            ["mape_example1_by_continent.png", "mape_example1_by_income.png"],
        ),
    ],
)
def test_plot(tmp_path, compare_with_version, by_group, file_names):
    """Test that each kind of figure is saved."""
    ml_results.plot(
        str(tmp_path),
        "example1",
        compare_with_version,
        by_group,
        results_directory=EXAMPLES_FOLDER,
        metric="MAPE",
    )

    assert sorted(os.listdir(tmp_path)) == file_names


def test_plot_reads_validation_results(tmp_path):
    """Test that the MAPE files are read from the validation results."""
    with (
        patch.object(ml_results, "_read_errors") as read_mape,
        patch.object(ml_results, "_read_results"),
        patch.object(ml_results, "_plot_overall"),
        patch.object(ml_results, "_plot_groups_of_codes"),
    ):
        ml_results.plot(str(tmp_path), "a")

    assert read_mape.call_args.args[0] == utils.paths.get_results_folder(
        "validation"
    )


def test_read_saved_results(tmp_path):
    """
    Test that the latest results of a model are read as saved.

    validate.py saves them in with_<model>/using_<data>/ with the
    columns "Entity code" and "Testing MAPE"; the latest file is read.
    """
    folder = tmp_path / "with_xgboost_model_1" / "using_data_1"
    folder.mkdir(parents=True)
    old = folder / "all_20260101_000000.parquet"
    pd.DataFrame({"Entity code": ["FRA"], "Testing MAPE": [0.5]}).to_parquet(
        old
    )
    os.utime(old, (0, 0))
    pd.DataFrame(
        {"Entity code": ["FRA", "DEU"], "Testing MAPE": [0.1, 0.2]}
    ).to_parquet(folder / "all_20260102_000000.parquet")

    mape = ml_results._read_errors(
        str(tmp_path), "xgboost_model_1", None, False, {}, "MAPE"
    )

    assert mape["xgboost_model_1_all"].to_dict() == pytest.approx(
        {"FRA": 10.0, "DEU": 20.0}
    )
    with pytest.raises(FileNotFoundError, match="has no results all"):
        ml_results._read_errors(
            str(tmp_path), "other_model", None, False, {}, "MAPE"
        )


@pytest.mark.parametrize(
    ("case", "version", "title", "file_name"),
    [
        (
            "validation",
            "xgboost_model_20261029_144400",
            "Validation of the XGBoost model 20261029_144400",
            "wape_validation_xgboost_model_20261029_144400.png",
        ),
        (
            "cross_validation",
            "xgboost",
            "Cross-validation of XGBoost, country holdout, 20261029_161733",
            "wape_cross_validation_xgboost_country_20261029_161733.png",
        ),
    ],
)
def test_plot_saved_results(tmp_path, case, version, title, file_name):
    """
    Test that the figure of saved results names what it shows.

    Its title and the name of its file tell whether the results are
    those of a validation or of a cross-validation, and the algorithm
    and version of the model.
    """
    folder = tmp_path / case / f"with_{version}" / "using_data_1"
    folder.mkdir(parents=True)
    results = folder / "all_20261029_161733.parquet"
    pd.DataFrame(
        {
            "Entity code": ["FRA", "DEU", "ITA"],
            "Testing MAPE": [0.1, 0.2, 0.3],
            "Testing WAPE": [0.1, 0.2, 0.3],
        }
    ).to_parquet(results)
    utils.manifest.write_manifest(
        str(results), "results", {"holdout": "country"}
    )

    assert ml_results.describe_version(str(tmp_path / case), version) == (
        title,
        file_name.removeprefix("wape_").removesuffix(".png"),
    )
    ml_results.plot(
        str(tmp_path), version, results_directory=str(tmp_path / case)
    )

    assert (tmp_path / file_name).exists()


def test_validation_of_another_version(tmp_path):
    """Test the description of a validation without a model time."""
    folder = tmp_path / "validation" / "with_model" / "using_data_1"
    folder.mkdir(parents=True)
    pd.DataFrame({"Entity code": ["FRA"], "Testing MAPE": [0.1]}).to_parquet(
        folder / "all_20261029_161733.parquet"
    )

    assert ml_results.describe_version(
        str(tmp_path / "validation"), "model"
    ) == ("Validation of model", "validation_model")


def test_figure_width():
    """Test that a figure of many bars is wide enough for its names."""
    assert ml_results._get_figure_width(30) == 10.0
    assert ml_results._get_figure_width(168) == pytest.approx(21.48)


@pytest.mark.parametrize("metric", ["WAPE", "MAPE"])
def test_plot_described_results(tmp_path, metric):
    """
    Test the figures of results that describe their codes.

    The codes never seen in training are hatched, and the errors are
    also plotted by group of codes, without the codes whose value of a
    group is not known.
    """
    folder = tmp_path / "with_xgboost_model_1" / "using_data_1"
    folder.mkdir(parents=True)
    pd.DataFrame(
        {
            "Entity code": ["FRA", "IND_PB", "MLT", "USA_CA"],
            "Testing MAPE": [0.06, 0.30, 0.20, 0.08],
            "Testing WAPE": [0.05, 0.25, 0.15, 0.07],
            "Seen in training": [True, False, True, True],
            "Scored hours": [100, 100, 50, 100],
            "Mean load (MW)": [50000.0, 5000.0, 250.0, 30000.0],
            "Size class": ["Large", "Medium", "Small", "Large"],
            "Continent": ["Europe", "Asia", "Europe", "North America"],
            "Embedded generation": ["unknown", None, "included", "unknown"],
        }
    ).to_parquet(folder / "all_20261029_161733.parquet")

    with patch.object(plt, "savefig"):
        ml_results.plot(
            str(tmp_path),
            "xgboost_model_1",
            results_directory=str(tmp_path),
            metric=metric,
        )
        overall, groups = (plt.figure(number) for number in plt.get_fignums())

    bars = overall.axes[1].patches
    assert [bar.get_hatch() for bar in bars] == [None, None, None, "////"]
    legend = overall.axes[1].get_legend()
    assert legend is not None
    assert [text.get_text() for text in legend.texts] == [
        "Seen in training",
        "Not seen in training",
    ]
    assert [ax.get_title() for ax in groups.axes] == [
        "Seen in training",
        "Size class",
        "Continent",
        "Embedded generation",
    ]
    assert [
        label.get_text() for label in groups.axes[1].get_xticklabels()
    ] == [
        "Small\n(1)",
        "Medium\n(1)",
        "Large\n(2)",
    ]
    # The errors are labelled as plain numbers, also between the powers
    # of ten.
    axis = groups.axes[0].yaxis
    assert axis.get_minor_formatter()(20.0, 0) == "20"
    assert axis.get_major_formatter()(10.0, 0) == "10"
    # The WAPE of each group, weighted by energy, is marked.
    markers = [
        np.asarray(collection.get_offsets())[:, 1]
        for collection in groups.axes[0].collections
    ]
    if metric == "WAPE":
        energy = np.array([50000.0 * 100, 250.0 * 50, 30000.0 * 100])
        assert markers[0].tolist() == pytest.approx(
            [25.0, (np.array([5.0, 15.0, 7.0]) * energy).sum() / energy.sum()]
        )
    else:
        assert markers == []


def test_plot_results_without_description(tmp_path):
    """Test that results without description have no group figure."""
    folder = tmp_path / "with_xgboost" / "using_data_1"
    folder.mkdir(parents=True)
    pd.DataFrame(
        {"Entity code": ["FRA"], "Testing MAPE": [0.1], "Testing WAPE": [0.1]}
    ).to_parquet(folder / "all_20261029_161733.parquet")

    ml_results.plot(str(tmp_path), "xgboost", results_directory=str(tmp_path))

    assert [
        name for name in os.listdir(tmp_path) if name.endswith(".png")
    ] == ["wape_validation_xgboost.png"]

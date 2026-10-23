"""
License: AGPL-3.0.

Description:

    Tests for the figures of the results of the machine learning
    models. They read the MAPE files of two example versions, in the
    folder mape_examples.
"""

import os
from unittest.mock import patch

import matplotlib.pyplot as plt
import pytest
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
        patch.object(ml_results, "_read_mape") as read_mape,
        pytest.raises(ValueError, match="cannot be used together"),
    ):
        ml_results.plot(str(tmp_path), "a", "b", by_group=True)

    read_mape.assert_not_called()


def test_read_mape():
    """Test that the MAPE values are read in percent, by version."""
    groups = {"income": ["high_income"], "continent": ["AF"]}

    mape = ml_results._read_mape(
        EXAMPLES_FOLDER, "example1", "example2", False, groups
    )
    assert list(mape.columns) == ["example1_all", "example2_all"]
    assert len(mape) == 95
    assert mape.loc["AT", "example1_all"] == pytest.approx(8.104806914070335)
    assert mape.loc["AT", "example2_all"] == pytest.approx(9.574320937012813)

    mape = ml_results._read_mape(
        EXAMPLES_FOLDER, "example1", None, True, groups
    )
    assert list(mape.columns) == [
        "example1_all",
        "example1_high_income",
        "example1_AF",
    ]
    assert mape.loc["DZ", "example1_AF"] == pytest.approx(4.378211941703889)
    assert mape["example1_AF"].notna().sum() == 3


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
    )

    assert sorted(os.listdir(tmp_path)) == file_names


def test_plot_reads_validation_results(tmp_path):
    """Test that the MAPE files are read from the validation results."""
    with (
        patch.object(ml_results, "_read_mape") as read_mape,
        patch.object(ml_results, "_plot_overall"),
    ):
        ml_results.plot(str(tmp_path), "a")

    assert read_mape.call_args.args[0] == utils.paths.get_results_folder(
        "validation"
    )

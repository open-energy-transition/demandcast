"""
License: AGPL-3.0.

Description:

    Unit tests of the files of the models: the latest model and
    assembled data, and the results.
"""

import os
from unittest.mock import patch

import pandas as pd
import pytest

import ml_models.files
import utils.manifest


def test_get_trained_model_path_with_provided_path():
    """
    Test get_trained_model_path when a path is provided.

    This test checks if the function returns the provided path when
    it's not None.
    """
    model_path = "/path/to/model.json"
    result = ml_models.files.get_trained_model_path(model_path, "xgboost")
    assert result == model_path


def test_get_trained_model_path_without_provided_path():
    """
    Test get_trained_model_path when no path is provided.

    This test mocks the file system to simulate finding the latest
    trained model file.
    """
    with (
        patch("utils.paths.get_models_folder", return_value="/models"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = [
            "xgboost_model_20240101_120000.json",
            "xgboost_model_20240102_120000.json",
            "other_file.txt",
        ]

        result = ml_models.files.get_trained_model_path(None, "xgboost")

        assert result == os.path.join(
            "/models", "xgboost_model_20240102_120000.json"
        )


def test_get_trained_model_path_without_the_manifests():
    """Test that the manifest of a model is not taken for a model."""
    with (
        patch("utils.paths.get_models_folder", return_value="/models"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = [
            "xgboost_model_20240101_120000.json",
            "xgboost_model_20240101_120000.manifest.json",
        ]

        result = ml_models.files.get_trained_model_path(None, "xgboost")

    assert result == os.path.join(
        "/models", "xgboost_model_20240101_120000.json"
    )


def test_get_trained_model_path_no_files_found():
    """
    Test get_trained_model_path when no files are found.

    This test checks if the function raises FileNotFoundError when no
    trained model files are found.
    """
    with (
        patch("utils.paths.get_models_folder", return_value="/models"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = []

        with pytest.raises(FileNotFoundError):
            ml_models.files.get_trained_model_path(None, "xgboost")


def test_get_trained_model_path_pt_extension():
    """
    Test get_trained_model_path with ``.pt`` extension for LSTM.

    Verifies the extension parameter selects ``.pt`` files and picks
    the latest by datetime stamp.
    """
    with (
        patch("utils.paths.get_models_folder", return_value="/models"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = [
            "lstm_model_20240101_120000.pt",
            "lstm_model_20240102_120000.pt",
            "xgboost_model_20240103_120000.json",
        ]

        result = ml_models.files.get_trained_model_path(
            None, "lstm", extension=".pt"
        )

        assert result == os.path.join(
            "/models", "lstm_model_20240102_120000.pt"
        )


def test_get_trained_model_path_xgboost_unchanged_with_pt_present():
    """
    XGBoost path search ignores ``.pt`` files even when they exist.

    Ensures the extension parameter keeps the two algorithm namespaces
    fully separated.
    """
    with (
        patch("utils.paths.get_models_folder", return_value="/models"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = [
            "xgboost_model_20240101_120000.json",
            "lstm_model_20240103_120000.pt",
        ]

        result = ml_models.files.get_trained_model_path(None, "xgboost")

        assert result == os.path.join(
            "/models", "xgboost_model_20240101_120000.json"
        )


def test_get_assemble_data_path_with_provided_path():
    """
    Test get_assemble_data_path when a path is provided.

    This test checks if the function returns the provided path when
    it's not None.
    """
    data_path = "/path/to/data.parquet"
    result = ml_models.files.get_assemble_data_path(data_path)
    assert result == data_path


def test_get_assemble_data_path_without_provided_path():
    """
    Test get_assemble_data_path when no path is provided.

    This test mocks the file system to simulate finding the latest
    assembled data file.
    """
    with (
        patch("utils.paths.get_assembled_folder", return_value="/data"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = [
            "assembled_data_for_training_20240101_120000.parquet",
            "assembled_data_for_training_20240102_120000.parquet",
            "assembled_data_for_forecasting_20240103_120000.parquet",
            "other_file.txt",
        ]

        # A newer dataset for forecasting is not one for training.
        assert ml_models.files.get_assemble_data_path(None) == os.path.join(
            "/data", "assembled_data_for_training_20240102_120000.parquet"
        )
        assert ml_models.files.get_assemble_data_path(
            None, "forecasting"
        ) == os.path.join(
            "/data", "assembled_data_for_forecasting_20240103_120000.parquet"
        )


def test_get_assemble_data_path_no_files_found():
    """
    Test get_assemble_data_path when no files are found.

    This test checks if the function raises FileNotFoundError when no
    assembled data files are found.
    """
    with (
        patch("utils.paths.get_assembled_folder", return_value="/data"),
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = []

        with pytest.raises(FileNotFoundError):
            ml_models.files.get_assemble_data_path(None)


@pytest.mark.parametrize(
    ("case", "extra", "expected"),
    [
        ("validation", None, {"metric": ml_models.files.METRIC}),
        (
            "cross_validation",
            {"holdout": "country"},
            {"metric": ml_models.files.METRIC, "holdout": "country"},
        ),
        ("forecasts", None, {"units": "MW"}),
    ],
)
def test_save_results(tmp_path, case, extra, expected):
    """Test that the results are saved with their manifest."""
    with patch("utils.paths.get_results_folder", return_value=str(tmp_path)):
        ml_models.files.save_results(
            case,
            pd.DataFrame({"MAPE": [0.1, 0.2]}),
            "xgboost_model",
            "assembled_data",
            "all",
            extra,
        )

    folder = tmp_path / "with_xgboost_model" / "using_assembled_data"
    [parquet] = folder.glob("all_*.parquet")
    assert parquet.with_suffix(".csv").exists()
    manifest = utils.manifest.read_manifest(str(parquet))
    assert manifest is not None
    assert (manifest["kind"], manifest["case"]) == ("results", case)
    assert manifest["model"] == "xgboost_model"
    assert manifest["dataset"] == "assembled_data"
    assert manifest["columns"] == ["MAPE"]
    assert manifest["sha256"] == utils.manifest.get_checksum(str(parquet))
    for key, value in expected.items():
        assert manifest[key] == value


def test_save_results_invalid_case():
    """
    Test save_results with invalid case.

    This test checks if the function raises ValueError when an invalid
    case is provided.
    """
    output_data = pd.DataFrame({"value": [1, 2]})

    with pytest.raises(ValueError, match="Invalid case"):
        ml_models.files.save_results(
            case="invalid_case",  # type: ignore[arg-type]
            output_dataset=output_data,
            trained_model_name="xgboost_model",
            assembled_data_file_name="assembled_data",
            file_name_prefix="test",
        )

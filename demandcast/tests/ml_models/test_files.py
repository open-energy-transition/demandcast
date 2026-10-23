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
            "assembled_data_20240101_120000.parquet",
            "assembled_data_20240102_120000.parquet",
            "other_file.txt",
        ]

        result = ml_models.files.get_assemble_data_path(None)

        assert result == os.path.join(
            "/data", "assembled_data_20240102_120000.parquet"
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


def test_save_results_validation():
    """
    Test save_results for validation case.

    This test mocks the file system operations to check if the function
    correctly saves validation results.
    """
    output_data = pd.DataFrame({"mape": [0.1, 0.2]})

    with (
        patch("utils.paths.get_results_folder", return_value="/results"),
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_now.return_value.strftime.return_value = "20240101-120000"

        ml_models.files.save_results(
            case="validation",
            output_dataset=output_data,
            trained_model_name="xgboost_model",
            assembled_data_file_name="assembled_data",
            file_name_prefix="validation",
        )

        mock_makedirs.assert_called_once()
        mock_to_csv.assert_called_once()
        mock_to_parquet.assert_called_once()


def test_save_results_cross_validation():
    """
    Test save_results for cross_validation case.

    This test checks if the function correctly saves cross-validation
    results.
    """
    output_data = pd.DataFrame({"mape": [0.1, 0.2]})

    with (
        patch("utils.paths.get_results_folder", return_value="/results"),
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_now.return_value.strftime.return_value = "20240101-120000"

        ml_models.files.save_results(
            case="cross_validation",
            output_dataset=output_data,
            trained_model_name="xgboost_model",
            assembled_data_file_name="assembled_data",
            file_name_prefix="cross_validation",
        )

        mock_makedirs.assert_called_once()
        mock_to_csv.assert_called_once()
        mock_to_parquet.assert_called_once()


def test_save_results_forecasts():
    """
    Test save_results for forecasts case.

    This test checks if the function correctly saves forecast results.
    """
    output_data = pd.DataFrame({"forecast": [100, 200]})

    with (
        patch("utils.paths.get_results_folder", return_value="/results"),
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_now.return_value.strftime.return_value = "20240101-120000"

        ml_models.files.save_results(
            case="forecasts",
            output_dataset=output_data,
            trained_model_name="xgboost_model",
            assembled_data_file_name="assembled_data",
            file_name_prefix="forecasts",
        )

        mock_makedirs.assert_called_once()
        mock_to_csv.assert_called_once()
        mock_to_parquet.assert_called_once()


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

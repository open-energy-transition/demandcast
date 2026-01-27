# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the ml module in the ETL
    utility package.
"""

from unittest.mock import Mock, mock_open, patch

import pandas
import pytest
import utils.config
import utils.ml


def test_read_and_check_ml_configuration():
    """
    Test reading and checking ML configuration.

    This test mocks the configuration file reading and checks if the
    function correctly validates the configuration.
    """
    # Define a sample configuration.
    sample_config = {
        "algorithm": "xgboost",
        "group": "entity_code",
        "features": ["feature1", "feature2"],
        "target": "demand",
        "splitter": "year",
        "time": "timestamp",
        "categorical_features": ["feature1"],
        "scaling_variables": ["population"],
    }

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_read_folders.return_value = {"config_folder": "/config"}
        mock_yaml_load.return_value = sample_config

        config = utils.ml.read_and_check_ml_configuration()

        assert config.algorithm == "xgboost"
        assert config.group == "entity_code"
        assert config.features == ["feature1", "feature2"]
        assert config.target == "demand"
        assert config.splitter == "year"
        assert config.time == "timestamp"
        assert config.categorical_features == ["feature1"]
        assert config.scaling_variables == ["population"]


def test_read_and_check_ml_configuration_minimal():
    """
    Test reading ML configuration with minimal fields.

    This test checks if the function works with optional fields set to
    None.
    """
    # Define a minimal configuration.
    minimal_config = {
        "algorithm": "xgboost",
        "group": "entity_code",
        "features": ["feature1"],
        "target": "demand",
        "splitter": "year",
        "time": "timestamp",
    }

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_read_folders.return_value = {"config_folder": "/config"}
        mock_yaml_load.return_value = minimal_config

        config = utils.ml.read_and_check_ml_configuration()

        assert config.algorithm == "xgboost"
        assert config.categorical_features is None
        assert config.scaling_variables is None


def test_read_and_check_ml_configuration_error():
    """
    Test error handling in read_and_check_ml_configuration.

    This test checks if the function raises ValueError when the
    configuration is invalid.
    """
    # Define an invalid configuration (missing required fields).
    invalid_config = {
        "algorithm": "xgboost",
        "features": ["feature1"],
    }

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_read_folders.return_value = {"config_folder": "/config"}
        mock_yaml_load.return_value = invalid_config

        with pytest.raises(ValueError):
            utils.ml.read_and_check_ml_configuration()


def test_get_trained_model_path_with_provided_path():
    """
    Test get_trained_model_path when a path is provided.

    This test checks if the function returns the provided path when
    it's not None.
    """
    model_path = "/path/to/model.json"
    result = utils.ml.get_trained_model_path(model_path, "xgboost")
    assert result == model_path


def test_get_trained_model_path_without_provided_path():
    """
    Test get_trained_model_path when no path is provided.

    This test mocks the file system to simulate finding the latest
    trained model file.
    """
    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.listdir") as mock_listdir,
    ):
        mock_read_folders.return_value = {
            "trained_ml_models_folder": "/models"
        }
        mock_listdir.return_value = [
            "xgboost_model_20240101_120000.json",
            "xgboost_model_20240102_120000.json",
            "other_file.txt",
        ]

        result = utils.ml.get_trained_model_path(None, "xgboost")

        assert result == "/models/xgboost_model_20240102_120000.json"


def test_get_trained_model_path_no_files_found():
    """
    Test get_trained_model_path when no files are found.

    This test checks if the function raises FileNotFoundError when no
    trained model files are found.
    """
    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.listdir") as mock_listdir,
    ):
        mock_read_folders.return_value = {
            "trained_ml_models_folder": "/models"
        }
        mock_listdir.return_value = []

        with pytest.raises(FileNotFoundError):
            utils.ml.get_trained_model_path(None, "xgboost")


def test_get_assemble_data_path_with_provided_path():
    """
    Test get_assemble_data_path when a path is provided.

    This test checks if the function returns the provided path when
    it's not None.
    """
    data_path = "/path/to/data.parquet"
    result = utils.ml.get_assemble_data_path(data_path)
    assert result == data_path


def test_get_assemble_data_path_without_provided_path():
    """
    Test get_assemble_data_path when no path is provided.

    This test mocks the file system to simulate finding the latest
    assembled data file.
    """
    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.listdir") as mock_listdir,
    ):
        mock_read_folders.return_value = {"assembled_data_folder": "/data"}
        mock_listdir.return_value = [
            "assembled_data_20240101_120000.parquet",
            "assembled_data_20240102_120000.parquet",
            "other_file.txt",
        ]

        result = utils.ml.get_assemble_data_path(None)

        assert result == "/data/assembled_data_20240102_120000.parquet"


def test_get_assemble_data_path_no_files_found():
    """
    Test get_assemble_data_path when no files are found.

    This test checks if the function raises FileNotFoundError when no
    assembled data files are found.
    """
    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.listdir") as mock_listdir,
    ):
        mock_read_folders.return_value = {"assembled_data_folder": "/data"}
        mock_listdir.return_value = []

        with pytest.raises(FileNotFoundError):
            utils.ml.get_assemble_data_path(None)


def test_split_temporally_with_testing_and_validation():
    """
    Test _split_temporally with both testing and validation sets.

    This test checks if the function correctly splits the dataset into
    training, testing, and validation sets based on the splitter column.
    """
    # Create a sample dataset.
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "A", "A", "B", "B", "B"],
            "year": [2020, 2021, 2022, 2020, 2021, 2022],
            "value": [1, 2, 3, 4, 5, 6],
        }
    )

    result = utils.ml._split_temporally(
        dataset,
        testing_set=True,
        validation_set=True,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" in result
    assert "validation" in result
    assert len(result["testing"]) == 2  # Latest year for each entity
    assert len(result["validation"]) == 2  # Second latest year
    assert len(result["training"]) == 2  # Remaining data


def test_split_temporally_with_testing_only():
    """
    Test _split_temporally with only testing set.

    This test checks if the function correctly splits the dataset when
    only testing set is requested.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = utils.ml._split_temporally(
        dataset,
        testing_set=True,
        validation_set=False,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" in result
    assert "validation" not in result
    assert len(result["testing"]) == 1
    assert len(result["training"]) == 2


def test_split_temporally_with_validation_only():
    """
    Test _split_temporally with only validation set.

    This test checks if the function correctly splits the dataset when
    only validation set is requested.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = utils.ml._split_temporally(
        dataset,
        testing_set=False,
        validation_set=True,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" not in result
    assert "validation" in result
    assert len(result["validation"]) == 1
    assert len(result["training"]) == 2


def test_split_temporally_without_splits():
    """
    Test _split_temporally without testing or validation sets.

    This test checks if the function returns only training set when
    no splits are requested.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = utils.ml._split_temporally(
        dataset,
        testing_set=False,
        validation_set=False,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" not in result
    assert "validation" not in result
    assert len(result["training"]) == 3


def test_split_in_groups():
    """
    Test _split_in_groups function.

    This test checks if the function correctly splits the dataset into
    features, target, group, time, and other components.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "feature2": [3, 4],
            "target": [10, 20],
            "timestamp": [2020, 2021],
        }
    )

    result = utils.ml._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1", "feature2"],
        target_column="target",
        time_column="timestamp",
        target=True,
    )

    assert "features" in result
    assert "target" in result
    assert "group" in result
    assert "time" in result
    assert list(result["features"].columns) == ["feature1", "feature2"]
    assert len(result["target"]) == 2
    assert len(result["group"]) == 2
    assert len(result["time"]) == 2


def test_split_in_groups_without_target():
    """
    Test _split_in_groups without target.

    This test checks if the function works correctly when target is
    not included.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "timestamp": [2020, 2021],
            "target": [10, 20],
        }
    )

    result = utils.ml._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1"],
        target_column="target",
        time_column="timestamp",
        target=False,
    )

    assert "features" in result
    assert "target" not in result
    assert "group" in result
    assert "time" in result


def test_split_in_groups_with_categorical_features():
    """
    Test _split_in_groups with categorical features.

    This test checks if the function correctly converts categorical
    features to category dtype.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1.0, 2.0],
            "feature2": [3, 4],
            "target": [10, 20],
            "timestamp": [2020, 2021],
        }
    )

    result = utils.ml._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1", "feature2"],
        target_column="target",
        time_column="timestamp",
        categorical_feature_columns=["feature1"],
        target=True,
    )

    assert result["features"]["feature1"].dtype.name == "category"
    assert result["features"]["feature2"].dtype.name != "category"


def test_split_in_groups_with_scaling_variables():
    """
    Test _split_in_groups with scaling variables.

    This test checks if the function correctly calculates the scaling
    factor from scaling variables.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "target": [10, 20],
            "timestamp": [2020, 2021],
            "scale1": [2, 3],
            "scale2": [5, 10],
        }
    )

    result = utils.ml._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1"],
        target_column="target",
        time_column="timestamp",
        scaling_variable_columns=["scale1", "scale2"],
        target=True,
    )

    assert "scaling_factor" in result
    assert result["scaling_factor"][0] == 10  # 2 * 5
    assert result["scaling_factor"][1] == 30  # 3 * 10


def test_split_in_groups_with_additional_columns():
    """
    Test _split_in_groups with additional columns.

    This test checks if the function correctly handles additional
    columns not specified in the parameters.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "target": [10, 20],
            "timestamp": [2020, 2021],
            "extra_col": [100, 200],
        }
    )

    result = utils.ml._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1"],
        target_column="target",
        time_column="timestamp",
        target=True,
    )

    assert "others" in result
    assert "extra_col" in result["others"].columns


def test_split_in_groups_missing_columns():
    """
    Test _split_in_groups with missing columns.

    This test checks if the function raises ValueError when required
    columns are missing from the dataset.
    """
    dataset = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
        }
    )

    with pytest.raises(ValueError):
        utils.ml._split_in_groups(
            dataset,
            group_column="entity_code",
            feature_columns=["feature1", "feature2"],
            target_column="target",
            time_column="timestamp",
            target=True,
        )


def test_prepare_dataset_with_splits():
    """
    Test prepare_dataset with testing and validation sets.

    This test mocks the configuration reading and data loading to check
    if the function correctly prepares the dataset with splits.
    """
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pandas.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "feature1": [1, 2, 3],
            "demand": [10, 20, 30],
            "year": [2020, 2021, 2022],
            "timestamp": [2020, 2021, 2022],
        }
    )

    with (
        patch("utils.ml.read_and_check_ml_configuration") as mock_read_config,
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_config.return_value = sample_config
        mock_read_parquet.return_value = sample_data

        result = utils.ml.prepare_dataset(
            "/path/to/data.parquet",
            testing_set=True,
            validation_set=True,
            target=True,
        )

        assert "training" in result
        assert "testing" in result
        assert "validation" in result
        assert "features" in result["training"]
        assert "target" in result["training"]


def test_prepare_dataset_without_splits():
    """
    Test prepare_dataset without testing and validation sets.

    This test checks if the function correctly prepares the dataset
    without temporal splits.
    """
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "demand": [10, 20],
            "year": [2020, 2021],
            "timestamp": [2020, 2021],
        }
    )

    with (
        patch("utils.ml.read_and_check_ml_configuration") as mock_read_config,
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_config.return_value = sample_config
        mock_read_parquet.return_value = sample_data

        result = utils.ml.prepare_dataset(
            "/path/to/data.parquet",
            testing_set=False,
            validation_set=False,
            target=True,
        )

        assert "features" in result
        assert "target" in result
        assert "group" in result
        assert "time" in result


def test_prepare_dataset_without_target():
    """
    Test prepare_dataset without target variable.

    This test checks if the function correctly prepares the dataset
    when target is not requested.
    """
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pandas.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "demand": [10, 20],
            "year": [2020, 2021],
            "timestamp": [2020, 2021],
        }
    )

    with (
        patch("utils.ml.read_and_check_ml_configuration") as mock_read_config,
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_config.return_value = sample_config
        mock_read_parquet.return_value = sample_data

        result = utils.ml.prepare_dataset(
            "/path/to/data.parquet",
            testing_set=False,
            validation_set=False,
            target=False,
        )

        assert "features" in result
        assert "target" not in result
        assert "group" in result
        assert "time" in result


def test_save_results_validation():
    """
    Test save_results for validation case.

    This test mocks the file system operations to check if the function
    correctly saves validation results.
    """
    output_data = pandas.DataFrame({"mape": [0.1, 0.2]})

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_read_folders.return_value = {"ml_validation_folder": "/results"}
        mock_now.return_value.strftime.return_value = "20240101-120000"

        utils.ml.save_results(
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
    output_data = pandas.DataFrame({"mape": [0.1, 0.2]})

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_read_folders.return_value = {
            "ml_cross_validation_folder": "/results"
        }
        mock_now.return_value.strftime.return_value = "20240101-120000"

        utils.ml.save_results(
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
    output_data = pandas.DataFrame({"forecast": [100, 200]})

    with (
        patch("utils.config.read_folders_structure") as mock_read_folders,
        patch("os.makedirs") as mock_makedirs,
        patch("pandas.DataFrame.to_csv") as mock_to_csv,
        patch("pandas.DataFrame.to_parquet") as mock_to_parquet,
        patch("pandas.Timestamp.now") as mock_now,
    ):
        mock_read_folders.return_value = {"ml_forecasts_folder": "/results"}
        mock_now.return_value.strftime.return_value = "20240101-120000"

        utils.ml.save_results(
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
    output_data = pandas.DataFrame({"value": [1, 2]})

    with pytest.raises(ValueError):
        utils.ml.save_results(
            case="invalid_case",
            output_dataset=output_data,
            trained_model_name="xgboost_model",
            assembled_data_file_name="assembled_data",
            file_name_prefix="test",
        )

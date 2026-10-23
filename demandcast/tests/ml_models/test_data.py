"""
License: AGPL-3.0.

Description:

    Unit tests of the preparation of the data of the models.
"""

from unittest.mock import Mock, mock_open, patch

import pandas as pd
import pytest

import ml_models.data
import ml_models.files


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
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_yaml_load.return_value = sample_config

        config = ml_models.data.read_and_check_ml_configuration()

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
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_yaml_load.return_value = minimal_config

        config = ml_models.data.read_and_check_ml_configuration()

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
        patch("builtins.open", mock_open(read_data="dummy")),
        patch("utils.config.yaml.safe_load") as mock_yaml_load,
    ):
        mock_yaml_load.return_value = invalid_config

        with pytest.raises(ValueError, match="Configuration validation error"):
            ml_models.data.read_and_check_ml_configuration()


def test_split_temporally_with_testing_and_validation():
    """
    Test _split_temporally with both testing and validation sets.

    This test checks if the function correctly splits the dataset into
    training, testing, and validation sets based on the splitter column.
    """
    # Create a sample dataset.
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A", "B", "B", "B"],
            "year": [2020, 2021, 2022, 2020, 2021, 2022],
            "value": [1, 2, 3, 4, 5, 6],
        }
    )

    result = ml_models.data._split_temporally(
        dataset,
        testing_set=True,
        validation_set=True,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" in result
    assert "validation" in result
    assert set(result["testing"]["year"]) == {2022}
    assert set(result["validation"]["year"]) == {2021}
    assert set(result["training"]["year"]) == {2020}
    assert len(result["testing"]) == 2


def test_split_temporally_with_testing_only():
    """
    Test _split_temporally with only testing set.

    This test checks if the function correctly splits the dataset when
    only testing set is requested.
    """
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = ml_models.data._split_temporally(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = ml_models.data._split_temporally(
        dataset,
        testing_set=False,
        validation_set=True,
        group_column="entity_code",
        splitter_column="year",
    )

    assert "training" in result
    assert "testing" not in result
    assert "validation" in result
    # Without a testing set, the validation set is the latest year, so
    # that the training set has no year after it.
    assert result["validation"]["year"].tolist() == [2022]
    assert result["training"]["year"].tolist() == [2020, 2021]


def test_split_temporally_with_missing_years():
    """Test that the holdouts are the latest available years."""
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A", "B", "B"],
            "year": [2019, 2021, 2023, 2020, 2022],
            "value": [1, 2, 3, 4, 5],
        }
    )

    result = ml_models.data._split_temporally(
        dataset,
        testing_set=True,
        validation_set=True,
        group_column="entity_code",
        splitter_column="year",
    )

    assert result["testing"]["year"].tolist() == [2023, 2022]
    assert result["validation"]["year"].tolist() == [2021, 2020]
    assert result["training"]["year"].tolist() == [2019]


def test_split_temporally_with_too_few_years(caplog):
    """Test that an entity with too few years is all held out."""
    dataset = pd.DataFrame(
        {"entity_code": ["A"], "year": [2022], "value": [1]}
    )

    with caplog.at_level("WARNING"):
        result = ml_models.data._split_temporally(
            dataset,
            testing_set=True,
            validation_set=True,
            group_column="entity_code",
            splitter_column="year",
        )

    assert result["testing"]["year"].tolist() == [2022]
    assert result["validation"].empty
    assert result["training"].empty
    assert "none is for training" in caplog.text


def test_split_temporally_without_splits():
    """
    Test _split_temporally without testing or validation sets.

    This test checks if the function returns only training set when
    no splits are requested.
    """
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "year": [2020, 2021, 2022],
            "value": [1, 2, 3],
        }
    )

    result = ml_models.data._split_temporally(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "feature2": [3, 4],
            "target": [10, 20],
            "timestamp": [2020, 2021],
        }
    )

    result = ml_models.data._split_in_groups(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "timestamp": [2020, 2021],
            "target": [10, 20],
        }
    )

    result = ml_models.data._split_in_groups(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1.0, 2.0],
            "feature2": [3, 4],
            "target": [10, 20],
            "timestamp": [2020, 2021],
        }
    )

    result = ml_models.data._split_in_groups(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "target": [10, 20],
            "timestamp": [2020, 2021],
            "scale1": [2, 3],
            "scale2": [5, 10],
        }
    )

    result = ml_models.data._split_in_groups(
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
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "target": [10, 20],
            "timestamp": [2020, 2021],
            "zeta": [100, 200],
            "alpha": [300, 400],
            "mu": [500, 600],
            "beta": [700, 800],
        }
    )

    result = ml_models.data._split_in_groups(
        dataset,
        group_column="entity_code",
        feature_columns=["feature1"],
        target_column="target",
        time_column="timestamp",
        target=True,
    )

    assert result["others"].columns.tolist() == ["zeta", "alpha", "mu", "beta"]


def test_split_in_groups_missing_columns():
    """
    Test _split_in_groups with missing columns.

    This test checks if the function raises ValueError when required
    columns are missing from the dataset.
    """
    dataset = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
        }
    )

    with pytest.raises(ValueError, match="required columns are missing"):
        ml_models.data._split_in_groups(
            dataset,
            group_column="entity_code",
            feature_columns=["feature1", "feature2"],
            target_column="target",
            time_column="timestamp",
            target=True,
        )


def test_prepare_split_datasets():
    """
    Test prepare_split_datasets with testing and validation sets.

    This test mocks the configuration reading and data loading to check
    if the function correctly prepares the dataset with splits.
    """
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "Local year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "feature1": [1, 2, 3],
            "demand": [10, 20, 30],
            "Local year": [2020, 2021, 2022],
            "timestamp": [2020, 2021, 2022],
        }
    )

    with (
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_parquet.return_value = sample_data

        result = ml_models.data.prepare_split_datasets(
            "/path/to/data.parquet",
            sample_config,
            testing_set=True,
            validation_set=True,
        )

        assert "training" in result
        assert "testing" in result
        assert "validation" in result
        assert "features" in result["training"]
        assert "target" in result["training"]


def test_prepare_split_datasets_with_training_set_only():
    """
    Test prepare_split_datasets without testing and validation sets.

    This test checks that the whole dataset is the training set.
    """
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "Local year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pd.DataFrame(
        {
            "entity_code": ["A", "A", "A"],
            "feature1": [1, 2, 3],
            "demand": [10, 20, 30],
            "Local year": [2020, 2021, 2022],
            "timestamp": [2020, 2021, 2022],
        }
    )

    with (
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_parquet.return_value = sample_data

        result = ml_models.data.prepare_split_datasets(
            "/path/to/data.parquet",
            sample_config,
            testing_set=False,
            validation_set=False,
        )

        assert list(result) == ["training"]
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
    sample_config.splitter = "Local year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "demand": [10, 20],
            "Local year": [2020, 2021],
            "timestamp": [2020, 2021],
        }
    )

    with (
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_parquet.return_value = sample_data

        result = ml_models.data.prepare_dataset(
            "/path/to/data.parquet",
            sample_config,
            target=True,
        )

        assert "features" in result
        assert "group" in result
        assert "time" in result

        # The target is relative to the annual mean: 2020 is a leap
        # year of 8784 hours, 2021 a year of 8760.
        assert result["target"].tolist() == [10 * 8784, 20 * 8760]
        assert result["local_year"].tolist() == [2020, 2021]


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
    sample_config.splitter = "Local year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "demand": [10, 20],
            "Local year": [2020, 2021],
            "timestamp": [2020, 2021],
        }
    )

    with (
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_parquet.return_value = sample_data

        result = ml_models.data.prepare_dataset(
            "/path/to/data.parquet",
            sample_config,
            target=False,
        )

        assert "features" in result
        assert "target" not in result
        assert "group" in result
        assert "time" in result
        assert result["local_year"].tolist() == [2020, 2021]


def test_prepare_dataset_without_local_year():
    """Test that prepare_dataset needs the local year of each row."""
    sample_config = Mock()
    sample_config.group = "entity_code"
    sample_config.features = ["feature1"]
    sample_config.target = "demand"
    sample_config.splitter = "Local year"
    sample_config.time = "timestamp"
    sample_config.categorical_features = None
    sample_config.scaling_variables = None

    sample_data = pd.DataFrame(
        {
            "entity_code": ["A", "B"],
            "feature1": [1, 2],
            "demand": [10, 20],
            "timestamp": [2020, 2021],
        }
    )

    with (
        patch("pandas.read_parquet") as mock_read_parquet,
    ):
        mock_read_parquet.return_value = sample_data

        with pytest.raises(ValueError, match="no 'Local year' column"):
            ml_models.data.prepare_dataset(
                "/path/to/data.parquet", sample_config
            )


def test_to_load_relative_to_annual_mean():
    """Test the conversion of the target, in common and leap years."""
    # 2000 and 2024 are leap years; 2100 is not, as a century that is
    # not divisible by 400.
    local_year = pd.Series([2023, 2024, 2100, 2000])
    load_fraction = pd.Series([1 / 8760, 1 / 8784, 2 / 8760, 2 / 8784])

    load_relative = ml_models.data.to_load_relative_to_annual_mean(
        load_fraction, local_year
    )

    assert load_relative.tolist() == pytest.approx([1, 1, 2, 2])


def test_to_load_fraction_of_annual_total():
    """Test that converting the predictions inverts the target."""
    local_year = pd.Series([2023, 2024, 2100, 2000])
    load_fraction = pd.Series([1.1e-4, 1.2e-4, 0.9e-4, 1.0e-4])

    load_relative = ml_models.data.to_load_relative_to_annual_mean(
        load_fraction, local_year
    )

    assert ml_models.data.to_load_fraction_of_annual_total(
        load_relative, local_year
    ).tolist() == pytest.approx(load_fraction.tolist())


def test_to_megawatts():
    """Test that a load of 1 is the mean hour of the annual demand."""
    local_year = pd.Series([2023, 2024])
    # 8.76 TWh in 2023 and 8.784 TWh in 2024, in kWh: 1 GW on average.
    scaling_factor = pd.Series([8.76e9, 8.784e9])

    megawatts = ml_models.data.to_megawatts(
        pd.Series([1.0, 1.5]), local_year, scaling_factor
    )

    assert megawatts.tolist() == pytest.approx([1000.0, 1500.0])


def test_check_model_features():
    """Test that the features of the trained model are accepted."""
    model = Mock(feature_names_in_=pd.Index(["a", "b"]))

    ml_models.data.check_model_features(
        model, pd.DataFrame(columns=["a", "b"])
    )


@pytest.mark.parametrize("columns", [["b", "a"], ["a"], ["a", "b", "c"]])
def test_check_model_features_errors(columns):
    """Test that other features, or another order, raise an error."""
    model = Mock(feature_names_in_=pd.Index(["a", "b"]))

    with pytest.raises(ValueError, match="do not match those used during"):
        ml_models.data.check_model_features(
            model, pd.DataFrame(columns=columns)
        )


def test_get_latest_file(tmp_path):
    """Test that the latest file is found by the time in its name."""
    for file_name in [
        "assembled_data_for_training_20250102_000000.parquet",
        "assembled_data_for_training_20250103_000000.parquet",
        "assembled_data_for_training_20250101_000000.parquet",
        "assembled_data_for_training_20250104_000000.csv",
        "other_data_20250105_000000.parquet",
    ]:
        (tmp_path / file_name).touch()

    assert ml_models.files._get_latest_file(
        str(tmp_path), "assembled_data", ".parquet"
    ) == str(tmp_path / "assembled_data_for_training_20250103_000000.parquet")
    assert (
        ml_models.files._get_latest_file(str(tmp_path), "model", ".json")
        is None
    )

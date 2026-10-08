"""
License: AGPL-3.0.

Description:

    This module provides utility functions for machine learning tasks,
    including data reading, temporal splitting, and feature preparation.
"""

import logging
import os
from typing import Any, NotRequired, TypedDict

import numpy as np
import pandas as pd
from pydantic import BaseModel, ValidationError

import utils.config

# The column of the local year of each row. assemble.py computes the
# target as the fraction of the annual total of each entity and local
# year, so converting it needs the local year of each row.
LOCAL_YEAR_COLUMN = "Local year"


class ConfigModel(BaseModel):
    """Settings of the machine learning models."""

    algorithm: str
    group: str
    features: list[str]
    target: str
    splitter: str
    time: str
    categorical_features: list[str] | None = None
    scaling_variables: list[str] | None = None


class PreparedDataset(TypedDict):
    """Dataset prepared for the machine learning models."""

    features: pd.DataFrame
    group: NotRequired[pd.Series]
    time: NotRequired[pd.Series]
    others: NotRequired[pd.DataFrame]
    target: NotRequired[pd.Series]
    scaling_factor: NotRequired[pd.Series]
    local_year: NotRequired[pd.Series]


def read_and_check_ml_configuration() -> ConfigModel:
    """
    Read and check the features and target.

    Returns
    -------
    config : ConfigModel
        A Pydantic model containing the ml configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """
    # Define the path to the features and target configuration file.
    config_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "ml_config.yaml",
    )

    # Read the configuration.
    with open(config_path, encoding="utf-8") as file:
        raw_config = utils.config.yaml.safe_load(file)

    # Validate the configuration.
    try:
        config = ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e

    logging.info("ML configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")

    return config


def _get_latest_file(folder: str, prefix: str, extension: str) -> str | None:
    """
    Get the latest file of a folder by the time in its name.

    The names of the files end with the time of their creation, in the
    format YYYYMMDD_HHMMSS, before the extension.

    Parameters
    ----------
    folder : str
        The folder to search.
    prefix : str
        The start of the names of the files.
    extension : str
        The extension of the files, such as ".parquet".

    Returns
    -------
    latest_path : str | None
        The path of the latest file, or None if there is no file.
    """
    latest_path = None
    latest_time = "00000000_000000"
    for file_name in os.listdir(folder):
        time = file_name[-len(latest_time) - len(extension) : -len(extension)]
        if (
            file_name.startswith(prefix)
            and file_name.endswith(extension)
            and time > latest_time
        ):
            latest_time = time
            latest_path = os.path.join(folder, file_name)

    return latest_path


def get_trained_model_path(
    model_path: str | None,
    algorithm_name: str,
    extension: str = ".json",
) -> str:
    """
    Get the path to the trained model file.

    Parameters
    ----------
    model_path : str | None
        The path to the trained model file. If None, the latest file
        in the default directory will be used.
    algorithm_name : str
        The name of the machine learning algorithm.
    extension : str, optional
        File extension of the saved model, e.g. ``".json"`` for
        XGBoost or ``".pt"`` for LSTM. Defaults to ``".json"``.

    Returns
    -------
    model_path : str
        The path to the trained model file.

    Raises
    ------
    FileNotFoundError
        If no trained model files are found.
    """
    # Get the folder containing trained model files.
    trained_models_folder = utils.config.read_folders_structure()[
        "trained_ml_models_folder"
    ]

    # If no model path is provided, find the latest trained model file.
    if model_path is None:
        model_path = _get_latest_file(
            trained_models_folder, f"{algorithm_name}_model", extension
        )
        if model_path is None:
            raise FileNotFoundError(
                f"No trained model files found in '{trained_models_folder}'."
            )

    logging.info(f"Using trained model file: {model_path}")

    return model_path


def check_model_features(model: Any, features: pd.DataFrame) -> None:
    """
    Check that a model was trained with the given features.

    Parameters
    ----------
    model : Any
        The trained model, with the names of its features in
        ``feature_names_in_``.
    features : pandas.DataFrame
        The features to give to the model.

    Raises
    ------
    ValueError
        If the features, or their order, differ from those used to
        train the model.
    """
    if model.feature_names_in_.tolist() != features.columns.tolist():
        raise ValueError(
            "The features used in the prepared dataset do not match "
            "those used during model training."
        )


def get_assemble_data_path(data_path: str | None) -> str:
    """
    Get the path to the assembled data file.

    Parameters
    ----------
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.

    Returns
    -------
    data_path : str
        The path to the assembled data file.

    Raises
    ------
    FileNotFoundError
        If no assembled data files are found.
    """
    # Get the folder containing assembled data files.
    assembled_data_folder = utils.config.read_folders_structure()[
        "assembled_data_folder"
    ]

    # If no data path is provided, find the latest assembled data file.
    if data_path is None:
        data_path = _get_latest_file(
            assembled_data_folder, "assembled_data", ".parquet"
        )
        if data_path is None:
            raise FileNotFoundError(
                f"No assembled data files found in '{assembled_data_folder}'."
            )

    logging.info(f"Using assembled data file: {data_path}")

    return data_path


def _hours_in_year(local_year: pd.Series) -> np.ndarray:
    """
    Count the hours of each year: 8784 in leap years, 8760 otherwise.

    Parameters
    ----------
    local_year : pandas.Series
        The local year of each row.

    Returns
    -------
    numpy.ndarray
        The hours in the local year of each row.
    """
    years = local_year.to_numpy(dtype=int)
    is_leap_year = (years % 4 == 0) & ((years % 100 != 0) | (years % 400 == 0))
    return np.where(is_leap_year, 8784, 8760)


def to_load_relative_to_annual_mean(
    load_fraction: pd.Series, local_year: pd.Series
) -> pd.Series:
    """
    Express the load relative to the annual mean.

    The fraction of the annual total of an average hour is 1/8760 (or
    1/8784 in leap years), which is too small for the models: the gain
    of an XGBoost split scales with the square of the target, so almost
    no split reaches its minimum gain (issue #145). Multiplying by the
    hours in the local year gives the load relative to the annual mean,
    so that an average hour is 1.

    Parameters
    ----------
    load_fraction : pandas.Series
        The load as a fraction of the annual total.
    local_year : pandas.Series
        The local year of each row, in the same order.

    Returns
    -------
    pandas.Series
        The load relative to the annual mean.
    """
    return load_fraction * _hours_in_year(local_year)


def to_load_fraction_of_annual_total(
    load_relative: pd.Series, local_year: pd.Series
) -> pd.Series:
    """
    Convert the load relative to the annual mean back to a fraction.

    This is the inverse of `to_load_relative_to_annual_mean`, for the
    predictions of the models.

    Parameters
    ----------
    load_relative : pandas.Series
        The load relative to the annual mean.
    local_year : pandas.Series
        The local year of each row, in the same order.

    Returns
    -------
    pandas.Series
        The load as a fraction of the annual total.
    """
    return load_relative / _hours_in_year(local_year)


def _split_temporally(
    dataset: pd.DataFrame,
    testing_set: bool,
    validation_set: bool,
    group_column: str,
    splitter_column: str,
) -> dict[str, pd.DataFrame]:
    """
    Split the dataset into training, validation, and test sets.

    Parameters
    ----------
    dataset : pandas.DataFrame
        The dataset to split.
    testing_set : bool
        Whether to have a testing set.
    validation_set : bool
        Whether to have a validation set.
    group_column : str
        The column name representing the entity codes.
    splitter_column : str
        The column name used to split the data temporally.

    Returns
    -------
    split_dataset : dict[str, pandas.DataFrame]
        A dictionary containing the split datasets with keys
        'training', 'testing' (if used), and 'validation' (if used).
    """
    logging.info(
        "Splitting dataset into training, testing, and validation sets, "
        "if requested."
    )

    # Initialize an empty dictionary to hold the split datasets.
    split_dataset: dict[str, pd.DataFrame] = {}
    if testing_set:
        split_dataset["testing"] = pd.DataFrame()
    if validation_set:
        split_dataset["validation"] = pd.DataFrame()

    # Initialize lists to keep track of indexes to be removed from
    # the original dataset.
    indexes_not_for_training = []

    for __, entity in dataset.groupby(group_column):
        # Determine the latest year for the current entity.
        latest_year = entity[splitter_column].max()

        if testing_set or validation_set:
            for split_name, split_data in split_dataset.items():
                # Define the year to extract based on the split.
                if split_name == "testing":
                    year_to_extract = latest_year
                elif split_name == "validation":
                    year_to_extract = latest_year - 1

                # Extract the data for the relevant year.
                data_of_entity = entity[
                    entity[splitter_column] == year_to_extract
                ].copy()

                # Append the indexes of the data to be removed later.
                indexes_not_for_training.extend(data_of_entity.index)

                # Append the data to the respective dataset.
                split_dataset[split_name] = pd.concat(
                    [split_data, data_of_entity],
                    ignore_index=True,
                )

    # Remove testing and validation data from the original dataset to
    # create the training dataset.
    split_dataset["training"] = dataset.drop(index=indexes_not_for_training)

    # Reset indexes for all datasets.
    for key, split_data in split_dataset.items():
        split_dataset[key] = split_data.reset_index(drop=True)

    logging.info("Dataset split complete:")
    for key, split_data in split_dataset.items():
        logging.info(
            f" - {key.capitalize()} set: {len(split_data)} records "
            f"({(len(split_data) / len(dataset)) * 100:.2f}%)"
        )

    return split_dataset


def _split_in_groups(  # noqa: C901
    dataset: pd.DataFrame,
    group_column: str,
    feature_columns: list[str],
    target_column: str,
    time_column: str,
    categorical_feature_columns: list[str] | None = None,
    scaling_variable_columns: list[str] | None = None,
    target: bool = True,
) -> PreparedDataset:
    """
    Split the dataset into features, target, group, and scaling factor.

    Parameters
    ----------
    dataset : pandas.DataFrame
        The dataset to prepare.
    group_column : str
        The column name representing the entity codes.
    feature_columns : list[str]
        List of feature column names.
    target_column : str
        Target column name.
    time_column : str
        The column name representing the time variable.
    categorical_feature_columns : list[str] | None, optional
        List of categorical feature column names to convert to category
        dtype.
    scaling_variable_columns : list[str] | None, optional
        List of scaling variable column names.
    target : bool, optional
        Whether to include the target variable in the prepared dataset.

    Returns
    -------
    split_dataset : PreparedDataset
        A dictionary containing the features, target, entity codes,
        and scaling factors (if any).

    Raises
    ------
    ValueError
        If required columns are missing from the dataset.
    """
    # Construct the list of columns to check for existence in the
    # dataset.
    columns_to_check = [*feature_columns, group_column, time_column]
    if target:
        columns_to_check += [target_column]
    if categorical_feature_columns:
        columns_to_check += categorical_feature_columns
    if scaling_variable_columns:
        columns_to_check += scaling_variable_columns

    # Check if all required columns are present in the dataset.
    missing_columns = set(columns_to_check) - set(dataset.columns)
    if missing_columns:
        raise ValueError(
            "The following required columns are missing from the "
            f"dataset: {missing_columns}"
        )

    # Check if additional columns are present in the dataset, and keep
    # them in the order of the dataset.
    additional_columns = [
        column for column in dataset.columns if column not in columns_to_check
    ]
    if additional_columns:
        logging.warning(
            "The following additional columns are present in the "
            f"dataset but not used: {additional_columns}"
        )

    # Extract features.
    features = dataset[feature_columns].copy()

    if categorical_feature_columns:
        # Convert values of categorical features to integer type and
        # then to category dtype.
        for feature in categorical_feature_columns:
            features[feature] = (
                features[feature].astype(int).astype("category")
            )

    # Split the dataset into features and group.
    split_dataset: PreparedDataset = {
        "features": features,
        "group": dataset[group_column].copy(),
        "time": dataset[time_column].copy(),
    }

    if additional_columns:
        split_dataset["others"] = dataset[additional_columns].copy()

    if target:
        # Extract target.
        split_dataset["target"] = dataset[target_column].copy()

    if scaling_variable_columns:
        # Calculate the scaling factor.
        scaling_factor = pd.Series(1.0, index=dataset.index)
        for scaling_variable in scaling_variable_columns:
            scaling_factor *= dataset[scaling_variable]

        # Add the scaling factor to the split dataset.
        split_dataset["scaling_factor"] = scaling_factor

    return split_dataset


def _prepare(
    dataset: pd.DataFrame, ml_config: ConfigModel, target: bool = True
) -> PreparedDataset:
    """
    Prepare a dataset, with the target relative to the annual mean.

    Parameters
    ----------
    dataset : pandas.DataFrame
        The dataset to prepare.
    ml_config : ConfigModel
        The configuration of the machine learning models.
    target : bool, optional
        Whether to include the target variable in the prepared dataset.

    Returns
    -------
    PreparedDataset
        The features, target, entity codes, local years and scaling
        factors (if any) of the dataset.

    Raises
    ------
    ValueError
        If the dataset has no local year column.
    """
    if LOCAL_YEAR_COLUMN not in dataset.columns:
        raise ValueError(
            f"The dataset has no '{LOCAL_YEAR_COLUMN}' column, which is "
            "needed to convert the target and the predictions."
        )

    prepared_dataset = _split_in_groups(
        dataset,
        ml_config.group,
        ml_config.features,
        ml_config.target,
        ml_config.time,
        ml_config.categorical_features,
        ml_config.scaling_variables,
        target,
    )

    # Keep the local years, to convert the predictions back.
    prepared_dataset["local_year"] = dataset[LOCAL_YEAR_COLUMN].copy()

    if target:
        prepared_dataset["target"] = to_load_relative_to_annual_mean(
            prepared_dataset["target"], prepared_dataset["local_year"]
        )

    return prepared_dataset


def prepare_dataset(data_path: str, target: bool = True) -> PreparedDataset:
    """
    Prepare the whole dataset for forecasting or cross-validation.

    Parameters
    ----------
    data_path : str
        The path to the assembled data file.
    target : bool, optional
        Whether to include the target variable in the prepared dataset.

    Returns
    -------
    PreparedDataset
        The features, target, entity codes, local years and scaling
        factors (if any) of the dataset. The target is the load
        relative to the annual mean.
    """
    # Read the configuration of the machine learning models.
    ml_config = read_and_check_ml_configuration()

    # Read the dataset.
    dataset = pd.read_parquet(data_path)

    # Prepare and return the dataset without splitting.
    return _prepare(dataset, ml_config, target)


def prepare_split_datasets(
    data_path: str, testing_set: bool, validation_set: bool
) -> dict[str, PreparedDataset]:
    """
    Prepare the training, testing, and validation sets.

    Parameters
    ----------
    data_path : str
        The path to the assembled data file.
    testing_set : bool
        Whether to have a testing set.
    validation_set : bool
        Whether to have a validation set.

    Returns
    -------
    dict[str, PreparedDataset]
        The prepared datasets, with keys 'training', 'testing' (if
        used), and 'validation' (if used). Their target is the load
        relative to the annual mean.
    """
    # Read the configuration of the machine learning models.
    ml_config = read_and_check_ml_configuration()

    # Read the dataset and split it temporally.
    split_dataset = _split_temporally(
        pd.read_parquet(data_path),
        testing_set,
        validation_set,
        ml_config.group,
        ml_config.splitter,
    )

    # Prepare each split of the dataset.
    return {
        split_name: _prepare(dataset, ml_config)
        for split_name, dataset in split_dataset.items()
    }


def save_results(
    case: str,
    output_dataset: pd.DataFrame,
    trained_model_name: str,
    assembled_data_file_name: str,
    file_name_prefix: str,
) -> None:
    """
    Save the model results to CSV and Parquet files.

    Parameters
    ----------
    output_dataset : pandas.DataFrame
        The dataset containing the model results to save.
    trained_model_name : str
        The name of the trained model used for obtaining the results.
    case : str
        The case of the results.

    Raises
    ------
    ValueError
        If the case is invalid.
    """
    # Check that the case is valid.
    if case not in ["validation", "cross_validation", "forecasts"]:
        raise ValueError(f"Invalid case: {case}")

    # Determine the content type for logging.
    output_dataset_content = "MAPEs" if "validation" in case else "forecasts"

    logging.info(f"Saving model {output_dataset_content}.")

    # Get the folder where to save the model results.
    results_folder = utils.config.read_folders_structure()[f"ml_{case}_folder"]

    # Construct the model results folder path.
    model_results_folder = os.path.join(
        results_folder,
        f"with_{trained_model_name}",
        f"using_{assembled_data_file_name}",
    )
    os.makedirs(model_results_folder, exist_ok=True)

    # Construct the results file name.
    results_file_name = os.path.join(
        model_results_folder,
        f"{file_name_prefix}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
    )

    # Save the results to CSV and Parquet files.
    output_dataset.to_csv(results_file_name + ".csv", index=False)
    output_dataset.to_parquet(results_file_name + ".parquet", index=False)

    logging.info(
        f"Model {case} saved to {results_file_name}.csv and "
        f"{results_file_name}.parquet"
    )

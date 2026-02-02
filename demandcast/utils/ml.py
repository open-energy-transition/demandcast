# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides utility functions for machine learning tasks,
    including data reading, temporal splitting, and feature preparation.
"""

import logging
import os
from typing import Optional

import pandas
from pydantic import BaseModel, ValidationError

import utils.config


def read_and_check_ml_configuration() -> BaseModel:
    """
    Read and check the features and target.

    Returns
    -------
    config : BaseModel
        A Pydantic model containing the ml configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        algorithm: str
        group: str
        features: list[str]
        target: str
        splitter: str
        time: str
        categorical_features: Optional[list[str]] = None
        scaling_variables: Optional[list[str]] = None

    # Define the path to the features and target configuration file.
    config_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "ml_config.yaml",
    )

    # Read the configuration.
    with open(config_path, "r") as file:
        raw_config = utils.config.yaml.safe_load(file)

    try:
        # Validate the configuration.
        config = ConfigModel(**raw_config)

        logging.info("ML configuration validated successfully:")
        for field, value in config.model_dump().items():
            logging.info(f" - {field}: {value}")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def get_trained_model_path(model_path: str | None, algorithm_name: str) -> str:
    """
    Get the path to the trained model file.

    Parameters
    ----------
    model_path : str | None
        The path to the trained model file. If None, the latest file
        in the default directory will be used.
    algorithm_name : str
        The name of the machine learning algorithm.

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
        # List all files in the trained models folder.
        model_paths = os.listdir(trained_models_folder)

        # Initialize a variable to hold the latest datetime and model
        # path.
        model_path = None
        datetime = "00000000_000000"
        for path in model_paths:
            # Extract datetime from the file name.
            datetime_of_file = path[
                -len(datetime) - len(".json") : -len(".json")
            ]
            if (
                path.startswith(f"{algorithm_name}_model")
                and path.endswith(".json")
                and datetime_of_file > datetime
            ):
                datetime = datetime_of_file
                model_path = os.path.join(trained_models_folder, path)
        if model_path is None:
            raise FileNotFoundError(
                f"No trained model files found in '{trained_models_folder}'."
            )

    logging.info(f"Using trained model file: {model_path}")

    return model_path


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
        # List all files in the assembled data folder.
        data_paths = os.listdir(assembled_data_folder)

        # Initialize a variable to hold the latest datetime and data
        # path.
        data_path = None
        datetime = "00000000_000000"
        for path in data_paths:
            # Extract datetime from the file name.
            datetime_of_file = path[
                -len(datetime) - len(".parquet") : -len(".parquet")
            ]
            if (
                path.startswith("assembled_data")
                and path.endswith(".parquet")
                and datetime_of_file > datetime
            ):
                datetime = datetime_of_file
                data_path = os.path.join(assembled_data_folder, path)
        if data_path is None:
            raise FileNotFoundError(
                f"No assembled data files found in '{assembled_data_folder}'."
            )

    logging.info(f"Using assembled data file: {data_path}")

    return data_path


def _split_temporally(
    dataset: pandas.DataFrame,
    testing_set: bool,
    validation_set: bool,
    group_column: str,
    splitter_column: str,
) -> dict[str, pandas.DataFrame]:
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
    split_dataset: dict[str, pandas.DataFrame] = {}
    if testing_set:
        split_dataset["testing"] = pandas.DataFrame()
    if validation_set:
        split_dataset["validation"] = pandas.DataFrame()

    # Initialize lists to keep track of indexes to be removed from
    # the original dataset.
    indexes_not_for_training = []

    for __, entity in dataset.groupby(group_column):
        # Determine the latest year for the current entity.
        latest_year = entity[splitter_column].max()

        if testing_set or validation_set:
            for split_name in split_dataset.keys():
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
                split_dataset[split_name] = pandas.concat(
                    [split_dataset[split_name], data_of_entity],
                    ignore_index=True,
                )

    # Remove testing and validation data from the original dataset to
    # create the training dataset.
    split_dataset["training"] = dataset.drop(index=indexes_not_for_training)

    # Reset indexes for all datasets.
    for key in split_dataset.keys():
        split_dataset[key] = split_dataset[key].reset_index(drop=True)

    logging.info("Dataset split complete:")
    for key in split_dataset.keys():
        logging.info(
            f" - {key.capitalize()} set: {len(split_dataset[key])} records "
            f"({(len(split_dataset[key]) / len(dataset)) * 100:.2f}%)"
        )

    return split_dataset


def _split_in_groups(
    dataset: pandas.DataFrame,
    group_column: str,
    feature_columns: list[str],
    target_column: str,
    time_column: str,
    categorical_feature_columns: list[str] | None = None,
    scaling_variable_columns: list[str] | None = None,
    target: bool = True,
) -> dict[str, dict[str, pandas.DataFrame | pandas.Series]]:
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
    split_dataset : dict[str, pandas.DataFrame | pandas.Series]
        A dictionary containing the features, target, entity codes,
        and scaling factors (if any).

    Raises
    ------
    ValueError
        If required columns are missing from the dataset.
    """
    # Construct the list of columns to check for existence in the
    # dataset.
    columns_to_check = feature_columns + [group_column] + [time_column]
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

    # Check if additional columns are present in the dataset.
    additional_columns = set(dataset.columns) - set(columns_to_check)
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
    split_dataset = {
        "features": features,
        "group": dataset[group_column].copy(),
        "time": dataset[time_column].copy(),
    }

    if additional_columns:
        split_dataset["others"] = dataset[list(additional_columns)].copy()

    if target:
        # Extract target.
        split_dataset["target"] = dataset[target_column].copy()

    if scaling_variable_columns:
        # Calculate the scaling factor.
        scaling_factor = 1.0
        for scaling_variable in scaling_variable_columns:
            scaling_factor *= dataset[scaling_variable]

        # Add the scaling factor to the split dataset.
        split_dataset["scaling_factor"] = scaling_factor

    return split_dataset


def prepare_dataset(
    data_path: str,
    testing_set: bool,
    validation_set: bool,
    target: bool = True,
) -> dict[
    str,
    pandas.Series
    | pandas.DataFrame
    | dict[str, pandas.DataFrame | pandas.Series],
]:
    """
    Prepare the dataset for training or validation.

    Parameters
    ----------
    data_path : str
        The path to the assembled data file.
    testing_set : bool
        Whether to have a testing set.
    validation_set : bool
        Whether to have a validation set.
    target : bool, optional
        Whether to include the target variable in the prepared dataset.

    Returns
    -------
    dict[str, pandas.DataFrame | pandas.Series |
        dict[str, pandas.DataFrame | pandas.Series]]
        A dictionary containing the prepared dataset(s).
    """
    # Read and check machine learning configuration.
    ml_config = read_and_check_ml_configuration()

    # Read the assembled data.
    dataset = pandas.read_parquet(data_path)

    if testing_set or validation_set:
        # Split the dataset temporally.
        split_dataset = _split_temporally(
            dataset,
            testing_set,
            validation_set,
            ml_config.group,
            ml_config.splitter,
        )

        # Initialize a dictionary to hold prepared datasets.
        prepared_dataset: dict[
            str, dict[str, pandas.DataFrame | pandas.Series]
        ] = {}

        # Prepare features and target for each dataset.
        for split_name, dataset in split_dataset.items():
            prepared_dataset[split_name] = _split_in_groups(
                dataset,
                ml_config.group,
                ml_config.features,
                ml_config.target,
                ml_config.time,
                ml_config.categorical_features,
                ml_config.scaling_variables,
                target,
            )

        return prepared_dataset

    else:
        # Prepare and return the dataset without splitting.
        return _split_in_groups(
            dataset,
            ml_config.group,
            ml_config.features,
            ml_config.target,
            ml_config.time,
            ml_config.categorical_features,
            ml_config.scaling_variables,
            target,
        )


def save_results(
    case: str,
    output_dataset: pandas.DataFrame,
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
        f"{file_name_prefix}_"
        f"{pandas.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
    )

    # Save the results to CSV and Parquet files.
    output_dataset.to_csv(results_file_name + ".csv", index=False)
    output_dataset.to_parquet(results_file_name + ".parquet", index=False)

    logging.info(
        f"Model {case} saved to {results_file_name}.csv and "
        f"{results_file_name}.parquet"
    )

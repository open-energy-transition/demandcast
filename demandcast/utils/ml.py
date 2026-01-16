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
        features: list[str]
        target: str
        categorical_features: Optional[list[str]] = None

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


def _read_assembled_data(data_path: str | None) -> pandas.DataFrame:
    """
    Read the assembled data.

    Parameters
    ----------
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.

    Returns
    -------
    pandas.DataFrame
        The assembled dataset.

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

    return pandas.read_parquet(data_path)


def _split_temporally(
    dataset: pandas.DataFrame,
    testing_set: bool,
    validation_set: bool,
    entity_code_column: str = "Entity code",
    year_column: str = "Local year",
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
    entyty_column : str, optional
        The column name representing the entity codes (default is
        "Entity code").
    year_column : str, optional
        The column name representing the year (default is "Local year").

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

    for __, entity in dataset.groupby(entity_code_column):
        # Determine the latest year for the current entity.
        latest_year = entity[year_column].max()

        if testing_set or validation_set:
            for split_name in split_dataset.keys():
                # Define the year to extract based on the split.
                if split_name == "testing":
                    year_to_extract = latest_year
                elif split_name == "validation":
                    year_to_extract = latest_year - 1

                # Extract the data for the relevant year.
                data_of_entity = entity[
                    entity[year_column] == year_to_extract
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


def _split_in_features_target_and_entity_codes(
    dataset: pandas.DataFrame,
    feature_columns: list[str],
    target_column: str,
    categorical_feature_columns: list[str] | None = None,
    entity_code_column: str = "Entity code",
) -> dict[str, dict[str, pandas.DataFrame | pandas.Series]]:
    """
    Extract features, target, and entity codes from the dataset.

    Parameters
    ----------
    dataset : pandas.DataFrame
        The dataset to prepare.
    feature_columns : list[str]
        List of feature column names.
    target_column : str
        Target column name (default: "Load (fraction of annual total)").
    categorical_feature_columns : list[str] | None, optional
        List of categorical feature column names to convert to category
        dtype.
    entity_code_column : str, optional
        The column name representing the entity codes (default is
        "Entity code").

    Returns
    -------
    dict[str, pandas.DataFrame | pandas.Series]
        A dictionary containing the features DataFrame, target Series,
        and entity codes Series.
    """
    # Extract features.
    features = dataset[feature_columns].copy()

    if categorical_feature_columns:
        for feature in categorical_feature_columns:
            if feature in features.columns:
                # Convert values of categorical features to integer
                # type and then to category dtype.
                features[feature] = (
                    features[feature].astype(int).astype("category")
                )
            else:
                logging.warning(
                    f"Categorical feature '{feature}' not found in "
                    f"the dataset columns."
                )

    # Return the prepared features, target, and entity codes.
    return {
        "features": features,
        "target": dataset[target_column].copy(),
        "entity_codes": dataset[entity_code_column].copy(),
    }


def prepare_dataset(
    data_path: str | None,
    testing_set: bool,
    validation_set: bool,
    feature_columns: list[str],
    target_column: str,
    categorical_feature_columns: list[str] | None = None,
    entity_code_column: str = "Entity code",
) -> dict[
    str,
    pandas.DataFrame
    | pandas.Series
    | dict[str, pandas.DataFrame | pandas.Series],
]:
    """
    Prepare the dataset for training or validation.

    Parameters
    ----------
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.
    testing_set : bool
        Whether to have a testing set.
    validation_set : bool
        Whether to have a validation set.
    feature_columns : list[str]
        List of feature column names.
    target_column : str
        Target column name.
    categorical_feature_columns : list[str] | None, optional
        List of categorical feature column names to convert to category
        dtype.
    entity_code_column : str, optional
        The column name representing the entity codes (default is
        "Entity code").

    Returns
    -------
    dict[str, pandas.DataFrame | pandas.Series |
        dict[str, pandas.DataFrame | pandas.Series]]
        A dictionary containing the prepared dataset(s).
    """
    # Read the assembled data.
    dataset = _read_assembled_data(data_path)

    if testing_set or validation_set:
        # Split the dataset temporally.
        split_dataset = _split_temporally(dataset, testing_set, validation_set)

        # Initialize a dictionary to hold prepared datasets.
        prepared_dataset: dict[
            str, dict[str, pandas.DataFrame | pandas.Series]
        ] = {}

        # Prepare features and target for each dataset.
        for split_name, dataset in split_dataset.items():
            prepared_dataset[split_name] = (
                _split_in_features_target_and_entity_codes(
                    dataset,
                    feature_columns,
                    target_column,
                    categorical_feature_columns,
                    entity_code_column,
                )
            )

        return prepared_dataset

    else:
        # Prepare and return the dataset without splitting.
        return _split_in_features_target_and_entity_codes(
            dataset,
            feature_columns,
            target_column,
            categorical_feature_columns,
            entity_code_column,
        )

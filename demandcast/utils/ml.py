# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides utility functions for machine learning tasks,
    including data reading, temporal splitting, and feature preparation.
"""

import logging
import os

import pandas

import utils.config


def read_preprocessed_data(data_path: str | None) -> pandas.DataFrame:
    """
    Read the preprocessed data.

    Parameters
    ----------
    data_path : str | None
        The path to the preprocessed data file. If None, the latest file
        in the default directory will be used.

    Returns
    -------
    pandas.DataFrame
        The preprocessed dataset.

    Raises
    ------
    FileNotFoundError
        If no processed data files are found.
    """
    # Get the folder containing processed data files.
    processed_data_folder = utils.config.read_folders_structure()[
        "processed_data_folder"
    ]

    # If no data path is provided, find the latest processed data file.
    if data_path is None:
        # List all files in the processed data folder.
        data_paths = os.listdir(processed_data_folder)

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
                data_path = os.path.join(processed_data_folder, path)
        if data_path is None:
            raise FileNotFoundError(
                f"No processed data files found in '{processed_data_folder}'."
            )

    logging.info(f"Using processed data file: {data_path}")

    return pandas.read_parquet(data_path)


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


def split_temporal(
    processed_data: pandas.DataFrame,
    reserve_testing_set: bool,
    use_validation_set: bool,
    entyty_column: str = "Entity code",
    year_column: str = "Local year",
) -> dict[str, pandas.DataFrame]:
    """
    Split the dataset into training, validation, and test sets.

    Parameters
    ----------
    processed_data : pandas.DataFrame
        The preprocessed dataset to be split.
    reserve_testing_set : bool
        Whether to reserve a testing set.
    use_validation_set : bool
        Whether to use a validation set.
    entyty_column : str, optional
        The column name representing the entity codes (default is
        "Entity code").
    year_column : str, optional
        The column name representing the year (default is "Local year").

    Returns
    -------
    split_dataset : dict[str, pandas.DataFrame]
        A dictionary containing the split datasets with keys
        'training', 'testing' (if reserved), and 'validation' (if used).
    """
    logging.info(
        "Splitting dataset into training, testing, and validation sets."
    )

    # Initialize an empty dictionary to hold the split datasets.
    split_dataset: dict[str, pandas.DataFrame] = {}
    if reserve_testing_set:
        split_dataset["testing"] = pandas.DataFrame()
    if use_validation_set:
        split_dataset["validation"] = pandas.DataFrame()

    # Initialize lists to keep track of indexes to be removed from
    # the original dataset.
    indexes_not_for_training = []

    for __, entity in processed_data.groupby(entyty_column):
        # Determine the maximum year in the group.
        latest_year = entity[year_column].max()

        for key in split_dataset.keys():
            # Extract the data for the latest year.
            data_of_entity = entity[
                entity[year_column]
                == (
                    latest_year
                    - (
                        1
                        if (key == "validation" and use_validation_set)
                        else 0
                    )
                )
            ].copy()

            # Append the indexes of the data to be removed later.
            indexes_not_for_training.extend(data_of_entity.index)

            # Append the data to the respective dataset.
            split_dataset[key] = pandas.concat(
                [split_dataset[key], data_of_entity], ignore_index=True
            )

    # Remove testing and validation data from the original dataset to
    # create the training dataset.
    split_dataset["training"] = processed_data.drop(
        index=indexes_not_for_training
    )

    # Reset indexes for all datasets.
    for key in split_dataset.keys():
        split_dataset[key] = split_dataset[key].reset_index(drop=True)

    logging.info("Dataset split complete:")
    for key in split_dataset.keys():
        logging.info(
            f" - {key.capitalize()} set: {len(split_dataset[key])} records "
            f"({(len(split_dataset[key]) / len(processed_data)) * 100:.2f}%)"
        )

    return split_dataset


def prepare_features_and_target(
    split_dataset: dict[str, pandas.DataFrame],
    feature_columns: list[str],
    target_column: str,
    categorical_features: list[str] | None = None,
) -> dict[str, dict[str, pandas.DataFrame | pandas.Series]]:
    """
    Extract features, target, and groups from dataset.

    Parameters
    ----------
    split_dataset : dict[str, pandas.DataFrame]
        A dictionary containing the split datasets (training,
        validation, testing).
    feature_columns : list[str]
        List of feature column names.
    target_column : str
        Target column name (default: "Load (fraction of annual total)").
    categorical_features : list[str] | None
        List of categorical feature names to convert to category dtype.

    Returns
    -------
    dict[str, dict[str, pandas.DataFrame | pandas.Series]]
        A dictionary with keys as split names and values as dictionaries
        containing 'features', 'target', and 'entity_codes'.
    """
    # Initialize the prepared data dictionary.
    prepared_data: dict[str, dict[str, pandas.DataFrame | pandas.Series]] = {}

    for split_name, dataset in split_dataset.items():
        # Extract features.
        features = dataset[feature_columns].copy()

        if categorical_features:
            for feature in categorical_features:
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

        # Store in the prepared data dictionary.
        prepared_data[split_name] = {
            "features": features,
            "target": dataset[target_column].copy(),
            "entity_codes": dataset["Entity code"].copy(),
        }

    return prepared_data

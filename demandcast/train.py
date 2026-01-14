"""
Training script for DemandCast XGBoost model.

Loads preprocessed data, splits the dataset temporally,
trains model, and saves results.
"""

import logging
import os
from typing import Optional

import ml_models.xgboost
import numpy
import pandas
import utils.config
from pydantic import BaseModel, ValidationError
from sklearn.metrics import mean_absolute_percentage_error


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for model training.

    Returns
    -------
    ConfigModel : BaseModel
        A Pydantic model containing the validated configuration.

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
        data_path: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        os.path.basename(__file__),
        "Train the machine learning model using the specified preprocessed "
        "data and algorithm.",
    )

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def _split_temporal(
    processed_data: pandas.DataFrame,
    entyty_column: str = "Entity code",
    year_column: str = "Local year",
    use_validation: bool = False,
) -> dict[str, pandas.DataFrame]:
    """
    Split the dataset into training, validation, and test sets.

    Parameters
    ----------
    processed_data : pandas.DataFrame
        The preprocessed dataset to be split.
    group_column : str, optional
        The column name used to group the data (default is "Entity
        code").
    time_column : str, optional
        The column name representing the time dimension (default is
        "Local year").

    Returns
    -------
    training_dataset : pandas.DataFrame
        The training dataset.
    testing_dataset : pandas.DataFrame
        The testing dataset.
    validation_dataset : pandas.DataFrame | None
        The validation dataset, or None if not used.
    """
    logging.info(
        "Splitting dataset into training, testing, and validation sets."
    )

    # Initialize empty DataFrames for testing and validation datasets.
    split_dataset: dict[str, pandas.DataFrame] = {}
    split_dataset["testing"] = pandas.DataFrame()
    if use_validation:
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
                    - (1 if (key == "validation" and use_validation) else 0)
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
    ).reset_index(drop=True)

    logging.info(
        "Dataset split complete: \n"
        + "".join(
            [
                (
                    f" - {key.capitalize()} set: {len(split_dataset[key])} records "
                    f"({(len(split_dataset[key]) / len(processed_data)) * 100:.2f}%)"
                )
                for key in split_dataset.keys()
            ]
        )
    )

    return split_dataset


def _prepare_features_and_target(
    split_dataset: dict[str, pandas.DataFrame],
    feature_columns: list[str],
    target_column: str = "Load (fraction of annual total)",
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
        containing 'features', 'target', and 'entities'.
    """
    # Initialize the prepared data dictionary.
    prepared_data: dict[str, dict[str, pandas.DataFrame | pandas.Series]] = {}

    for split_name, dataset in split_dataset.items():
        # Extract features.
        features = dataset[feature_columns].copy().reset_index(drop=True)

        # Convert categorical features to category dtype.
        if categorical_features:
            for feature in categorical_features:
                if feature in features.columns:
                    features[feature] = features[feature].astype("category")

        # Extract target and groups.
        target = dataset[target_column].copy().reset_index(drop=True)
        groups = dataset["Entity code"].copy().reset_index(drop=True)

        # Store in the prepared data dictionary.
        prepared_data[split_name] = {
            "features": features,
            "target": target,
            "entities": groups,
        }

    return prepared_data


def _calculate_mape_by_entity(
    predictions: numpy.ndarray,
    actual: pandas.Series,
    entities: pandas.Series,
) -> pandas.Series:
    """
    Calculate MAPE per entity.

    Parameters
    ----------
    predictions : numpy.ndarray
        Model predictions.
    actual : pandas.Series
        Actual target values.
    entities : pandas.Series
        Series indicating the code of each entity.

    Returns
    -------
    mapes : pandas.Series
        Series containing MAPE values for each entity.
    """
    # Initialize lists to hold entity codes and their MAPE values.
    list_entity_codes = []
    list_mapes_values = []

    # Calculate MAPE for each entity.
    for code, group in pandas.DataFrame(entities).groupby("Entity code"):
        current_mape = mean_absolute_percentage_error(
            actual.iloc[group.index], predictions[group.index]
        )
        list_entity_codes.append(code)
        list_mapes_values.append(current_mape)

    # Create a Series for MAPE values indexed by entity codes.
    mapes = pandas.Series(
        data=list_mapes_values,
        index=list_entity_codes,
        name="MAPE",
    )

    return mapes


def _save_metrics(
    mapes: pandas.DataFrame,
    model_name_folder: str,
) -> None:
    """
    Save metrics to CSV and parquet files.

    Parameters
    ----------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values.
    model_name_folder : str
        The folder name for the model results.
    """
    # Get the results folder path.
    results_folder = utils.config.read_folders_structure()["results_folder"]

    # Construct the model results folder path.
    model_results_folder = os.path.join(
        results_folder,
        model_name_folder,
    )
    os.makedirs(model_results_folder, exist_ok=True)

    # Construct the results file name.
    results_file_name = os.path.join(
        model_results_folder,
        f"all_{pandas.Timestamp.now().strftime('%Y%m%d-%H%M%S')}",
    )

    # Save the MAPE values to CSV and Parquet files.
    mapes.to_csv(results_file_name + ".csv", index=True)
    mapes.to_parquet(results_file_name + ".parquet", index=True)


def run_model_training(
    algorithm: str,
    feature_columns: list[str],
    target_column: str,
    categorical_features: list[str] | None = None,
    data_path: str | None = None,
) -> None:
    """
    Run the model training process.

    Parameters
    ----------
    algorithm : str
        The machine learning algorithm to use for training.
    feature_columns : list[str]
        List of feature column names.
    target_column : str
        Target column name.
    categorical_features : list[str] | None
        List of categorical feature names to convert to category dtype.
    data_path : str | None
        The path to the preprocessed data file. If None, the latest file
        in the default directory will be used.

    Raises
    ------
    FileNotFoundError
        If no processed data files are found.
    ValueError
        If an unsupported algorithm is specified.
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
            if (
                path.startswith("processed_data_for_training")
                and path.endswith(".parquet")
                and path[-20:-8] > datetime
            ):
                datetime = path[-20:-8]
                data_path = os.path.join(processed_data_folder, path)
        if data_path is None:
            raise FileNotFoundError(
                f"No processed data files found in '{processed_data_folder}'."
            )

    # Load the processed dataset.
    processed_dataset = pandas.read_parquet(data_path)

    # Split the dataset temporally.
    split_dataset = _split_temporal(processed_dataset)

    # Prepare features and target for each dataset.
    prepared_dataset = _prepare_features_and_target(
        split_dataset,
        feature_columns,
        target_column,
        categorical_features,
    )

    if algorithm.lower() == "xgboost":
        # Train the model.
        model = ml_models.xgboost.train(prepared_dataset)

        # Define a model name based on timestamp.
        model_name = (
            f"xgboost_model_{pandas.Timestamp.now().strftime('%Y%m%d-%H%M%S')}"
        )

        # Save the trained model.
        ml_models.xgboost.save(model, model_name)

        # Initialize a DataFrame to hold MAPE results.
        mapes = pandas.DataFrame()

        for split in prepared_dataset.keys():
            # Make predictions with the trained model.
            predictions = model.predict(prepared_dataset[split]["features"])

            # Calculate MAPE per entity for the current split.
            mapes_of_split = _calculate_mape_by_entity(
                predictions,
                prepared_dataset[split]["target"],
                prepared_dataset[split]["entities"],
            )

            # Store the MAPE values in the results DataFrame.
            mapes[f"MAPE_{split}"] = mapes_of_split

            logging.info(
                f"{split.capitalize()} set: "
                f"Average MAPE = {mapes_of_split.mean():.4f}, "
                f"Median MAPE = {mapes_of_split.median():.4f}, "
                f"Std MAPE = {mapes_of_split.std():.4f}"
            )

        # Save the MAPE metrics.
        _save_metrics(mapes, model_name)

    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


if __name__ == "__main__":
    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Set up the logging configuration.
    utils.config.set_up_logging("assembly_of_retrieved_data")

    # Run the data assembly process.
    run_model_training(
        config.algorithm,
        config.features,
        config.target,
        config.categorical_features,
        config.data_path,
    )

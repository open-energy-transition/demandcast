# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script validates a trained machine learning model using
    preprocessed data, reserving a testing set and computing mean
    absolute percentage error (MAPE) metrics.
"""

import logging
import os
from typing import Optional

import ml_models.xgboost
import pandas
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError
from sklearn.metrics import mean_absolute_percentage_error


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for model validation.

    Returns
    -------
    config : BaseModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        used_validation_set: bool
        model_path: Optional[str] = None
        data_path: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "validate",
        "Validate the machine learning model using the specified "
        "preprocessed data and algorithm.",
    )

    try:
        # Validate the configuration.
        config = ConfigModel(**raw_config)

        logging.info("Configuration validated successfully:")
        for field, value in config.model_dump().items():
            logging.info(f" - {field}: {value}")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def _calculate_mape_by_entity(
    predictions: pandas.Series,
    actual: pandas.Series,
    entity_codes: pandas.Series,
) -> pandas.Series:
    """
    Calculate MAPE per entity.

    Parameters
    ----------
    predictions : numpy.ndarray
        Model predictions.
    actual : pandas.Series
        Actual target values.
    entity_codes : pandas.Series
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
    for entity_code, entity_group in pandas.DataFrame(entity_codes).groupby(
        "Entity code"
    ):
        current_mape = mean_absolute_percentage_error(
            actual.iloc[entity_group.index],
            predictions.iloc[entity_group.index],
        )
        list_entity_codes.append(entity_code)
        list_mapes_values.append(current_mape)

    # Create a Series for MAPE values indexed by entity codes.
    mapes = pandas.Series(
        data=list_mapes_values,
        index=list_entity_codes,
        name="MAPE",
    ).rename_axis("Entity code")

    return mapes


def _calculate_mapes(
    prepared_dataset: dict[str, dict[str, pandas.DataFrame | pandas.Series]],
    predictions: dict[str, pandas.Series],
) -> pandas.DataFrame:
    """
    Calculate MAPE for training, validation, and testing datasets.

    Parameters
    ----------
    prepared_dataset :
        dict[str, dict[str, pandas.DataFrame | pandas.Series]]
        A dictionary containing the prepared datasets for training,
        validation, and testing.
    predictions : dict[str, pandas.Series]
        A dictionary containing predictions for each dataset split.

    Returns
    -------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values for each entity across the
        datasets.
    """
    # Initialize a DataFrame to hold MAPE results.
    mapes = pandas.DataFrame()

    for split in prepared_dataset.keys():
        # Calculate MAPE per entity for the current split.
        mapes_of_split = _calculate_mape_by_entity(
            predictions[split],
            prepared_dataset[split]["target"],
            prepared_dataset[split]["entity_codes"],
        )

        # Store the MAPE values in the results DataFrame.
        mapes[f"{split.capitalize()} MAPE"] = mapes_of_split

        logging.info(
            f"{split.capitalize()} set: "
            f"Average MAPE = {mapes_of_split.mean():.4f}, "
            f"Median MAPE = {mapes_of_split.median():.4f}, "
            f"Std MAPE = {mapes_of_split.std():.4f}"
        )

    return mapes


def _save_mapes(
    mapes: pandas.DataFrame,
    model_name_folder: str,
) -> None:
    """
    Save MAPEs to CSV and parquet files.

    Parameters
    ----------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values.
    model_name_folder : str
        The folder name for the model results.
    """
    # Get the results folder path.
    results_folder = utils.config.read_folders_structure()["ml_results_folder"]

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

    logging.info(
        f"MAPEs saved to {results_file_name}.csv and "
        f"{results_file_name}.parquet"
    )


def run_model_validation(
    used_validation_set: bool,
    model_path: str | None,
    data_path: str | None,
    algorithm: str,
    features: list[str],
    target: str,
    categorical_features: list[str] | None,
) -> None:
    """
    Run the model validation process.

    Parameters
    ----------
    used_validation_set : bool
        Whether a validation set was used during training.
    model_path : str | None
        The path to the trained model file. If None, the latest file
        in the default directory will be used.
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.
    algorithm : str
        The machine learning algorithm to use for validation.
    features : list[str]
        List of feature column names.
    target : str
        Target column name.
    categorical_features : list[str] | None
        List of categorical feature names to convert to category dtype.

    Raises
    ------
    ValueError
        If an unsupported algorithm is specified.
    """
    logging.info("Starting model validation process.")

    # Read the assembled data.
    assembled_dataset = utils.ml.read_assembled_data(data_path)

    # Split the dataset temporally.
    split_dataset = utils.ml.split_temporal(
        assembled_dataset, True, used_validation_set
    )

    # Prepare features and target for each dataset.
    prepared_dataset = utils.ml.prepare_features_and_target(
        split_dataset,
        features,
        target,
        categorical_features,
    )

    if algorithm.lower() == "xgboost":
        # Get the trained model path.
        trained_model_path = utils.ml.get_trained_model_path(
            model_path, algorithm.lower()
        )

        # Load the trained model.
        model = ml_models.xgboost.load(trained_model_path)

        # Make predictions.
        predictions = ml_models.xgboost.predict(model, prepared_dataset)

        # Calculate MAPEs.
        mapes = _calculate_mapes(prepared_dataset, predictions)

        # Save the MAPEs.
        _save_mapes(mapes, os.path.basename(trained_model_path).split(".")[0])

    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("model_validation")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Read and check features and target configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    # Run the model validation process.
    run_model_validation(
        config.used_validation_set,
        config.model_path,
        config.data_path,
        ml_config.algorithm,
        ml_config.features,
        ml_config.target,
        ml_config.categorical_features,
    )

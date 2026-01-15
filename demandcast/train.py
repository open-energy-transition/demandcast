# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script trains a machine learning model using preprocessed data.
"""

import logging
from typing import Optional

import ml_models.xgboost
import pandas
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for model training.

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
        algorithm: str
        reserve_testing_set: bool
        use_validation_set: bool
        features: list[str]
        target: str
        categorical_features: Optional[list[str]] = None
        data_path: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "train",
        "Train the machine learning model using the specified preprocessed "
        "data and algorithm.",
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


def run_model_training(
    algorithm: str,
    reserve_testing_set: bool,
    use_validation_set: bool,
    features: list[str],
    target: str,
    categorical_features: list[str] | None,
    data_path: str | None,
) -> None:
    """
    Run the model training process.

    Parameters
    ----------
    algorithm : str
        The machine learning algorithm to use for training.
    features : list[str]
        List of feature column names.
    target : str
        Target column name.
    categorical_features : list[str] | None
        List of categorical feature names to convert to category dtype.
    data_path : str | None
        The path to the preprocessed data file. If None, the latest file
        in the default directory will be used.

    Raises
    ------
    ValueError
        If an unsupported algorithm is specified.
    """
    logging.info("Starting model training process.")

    # Read the preprocessed data.
    processed_dataset = utils.ml.read_preprocessed_data(data_path)

    # Split the dataset temporally.
    split_dataset = utils.ml.split_temporal(
        processed_dataset, reserve_testing_set, use_validation_set
    )

    # Prepare features and target for each dataset.
    prepared_dataset = utils.ml.prepare_features_and_target(
        split_dataset,
        features,
        target,
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
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("model_training")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Run the model training process.
    run_model_training(
        config.algorithm,
        config.reserve_testing_set,
        config.use_validation_set,
        config.features,
        config.target,
        config.categorical_features,
        config.data_path,
    )

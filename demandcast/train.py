# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script trains a machine learning model using a preprocessed
    dataset, with configuration options for algorithm selection,
    feature selection, and data splitting.
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
        reserve_testing_set: bool
        use_validation_set: bool
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
    reserve_testing_set: bool,
    use_validation_set: bool,
    data_path: str | None,
    algorithm: str,
    features: list[str],
    target: str,
    categorical_features: list[str] | None,
) -> None:
    """
    Run the model training process.

    Parameters
    ----------
    reserve_testing_set : bool
        Whether to reserve a testing set from the data.
    use_validation_set : bool
        Whether to use a validation set during training.
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.
    algorithm : str
        The machine learning algorithm to use for training.
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
    logging.info("Starting model training process.")

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(
        data_path,
        reserve_testing_set,
        use_validation_set,
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

    # Read and check features and target configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    # Run the model training process.
    run_model_training(
        config.reserve_testing_set,
        config.use_validation_set,
        config.data_path,
        ml_config.algorithm,
        ml_config.features,
        ml_config.target,
        ml_config.categorical_features,
    )

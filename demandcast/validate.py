"""
License: AGPL-3.0.

Description:

    This script validates a trained machine learning model using
    preprocessed data, reserving a testing set and computing mean
    absolute percentage error (MAPE) metrics.
"""

import logging
import os

import ml_models.evaluation
import ml_models.registry
import utils.config
import utils.ml
from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Settings of validate.py."""

    used_validation_set: bool
    model_path: str | None = None
    data_path: str | None = None


def run_model_validation(
    used_validation_set: bool,
    model_path: str | None,
    data_path: str | None,
    ml_config: utils.ml.ConfigModel,
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
    ml_config : utils.ml.ConfigModel
        The settings of the machine learning models, with the
        algorithm.
    """
    logging.info("Starting model validation process.")

    # Get the module of the model.
    algorithm = ml_config.algorithm
    model_module = ml_models.registry.get_model_module(algorithm)

    # Get the assembled data path.
    data_path = utils.ml.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_split_datasets(
        data_path, ml_config, True, used_validation_set
    )

    # Load the trained model, and check that it was trained with the
    # features of the prepared dataset.
    trained_model_path = utils.ml.get_trained_model_path(
        model_path, algorithm.lower(), model_module.FILE_EXTENSION
    )
    model = model_module.load(trained_model_path)
    utils.ml.check_model_features(
        model, prepared_dataset["training"]["features"]
    )

    # Make predictions.
    predictions = model_module.predict(model, prepared_dataset)

    # Calculate MAPEs.
    mapes = ml_models.evaluation.calculate_mapes(prepared_dataset, predictions)

    # Save the MAPEs.
    utils.ml.save_results(
        "validation",
        mapes,
        os.path.basename(trained_model_path).split(".")[0],
        os.path.basename(data_path).split(".")[0],
        "all",
    )


def main(config: ConfigModel) -> None:
    """
    Validate the model of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("model_validation")
    utils.config.log_configuration(config)

    # Read and check machine learning configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    run_model_validation(
        config.used_validation_set,
        config.model_path,
        config.data_path,
        ml_config,
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "validate",
            ConfigModel,
            "Validate the machine learning model using the specified "
            "preprocessed data and algorithm.",
        )
    )

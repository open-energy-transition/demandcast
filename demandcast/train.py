"""
License: AGPL-3.0.

Description:

    This script trains a machine learning model using a preprocessed
    dataset, with configuration options for algorithm selection,
    feature selection, and data splitting.
"""

# On Windows, PyTorch must be imported before pandas, so the ml_models
# package, which imports it first, is imported before everything else.
import ml_models  # noqa: F401

# isort: split
import logging
import os

import pandas as pd
from pydantic import BaseModel

import ml_models.data
import ml_models.files
import ml_models.registry
import utils.config
import utils.paths


class ConfigModel(utils.config.StrictSettings):
    """Settings of train.py."""

    reserve_testing_set: bool
    use_validation_set: bool
    data_path: str | None = None


def run_model_training(
    reserve_testing_set: bool,
    use_validation_set: bool,
    data_path: str | None,
    ml_config: ml_models.data.ConfigModel,
    model_config: BaseModel,
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
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models, with the
        algorithm.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.
    """
    logging.info("Starting model training process.")

    # Get the module of the model.
    algorithm = ml_config.algorithm
    model_module = ml_models.registry.get_model_module(algorithm)

    # Get the assembled data path.
    data_path = ml_models.files.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = ml_models.data.prepare_split_datasets(
        data_path, ml_config, reserve_testing_set, use_validation_set
    )

    # Define a model name based on timestamp.
    model_name = (
        f"{algorithm.lower()}_model_"
        f"{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
    )

    # Train the model and save it.
    model = model_module.train(prepared_dataset, model_config)
    model_folder = utils.paths.get_models_folder(algorithm.lower())
    os.makedirs(model_folder, exist_ok=True)
    model_module.save(
        model,
        os.path.join(model_folder, model_name + model_module.FILE_EXTENSION),
    )


def main(config: ConfigModel) -> None:
    """
    Train the model of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("model_training")
    utils.config.log_configuration(config)

    # Read and check machine learning configuration.
    ml_config = ml_models.data.read_and_check_ml_configuration()

    run_model_training(
        config.reserve_testing_set,
        config.use_validation_set,
        config.data_path,
        ml_config,
        ml_models.registry.read_model_configuration(ml_config.algorithm),
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "train",
            ConfigModel,
            "Train the machine learning model using the specified "
            "preprocessed data and algorithm.",
        )
    )

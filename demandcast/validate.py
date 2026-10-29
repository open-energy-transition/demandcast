"""
License: AGPL-3.0.

Description:

    This script validates a trained machine learning model using
    preprocessed data, reserving a testing set and computing mean
    absolute percentage error (MAPE) metrics.
"""

# On Windows, PyTorch must be imported before pandas, so the ml_models
# package, which imports it first, is imported before everything else.
import ml_models  # noqa: F401

# isort: split
import logging
import os

import ml_models.data
import ml_models.evaluation
import ml_models.files
import ml_models.registry
import utils.config
import utils.manifest


class ConfigModel(utils.config.StrictSettings):
    """Settings of validate.py."""

    used_validation_set: bool
    model_path: str | None = None
    data_path: str | None = None


def run_model_validation(
    used_validation_set: bool,
    model_path: str | None,
    data_path: str | None,
    ml_config: ml_models.data.ConfigModel,
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
        The path to the assembled data file. If None, the data of the
        training of the model, or for a model without manifest the
        latest file in the default directory, will be used.
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models, with the
        algorithm.
    """
    logging.info("Starting model validation process.")

    # Get the module of the model.
    algorithm = ml_config.algorithm
    model_module = ml_models.registry.get_model_module(algorithm)

    # Load the trained model, after checking it against its manifest.
    trained_model_path = ml_models.files.get_trained_model_path(
        model_path, algorithm.lower(), model_module.FILE_EXTENSION
    )
    manifest = utils.manifest.verify_file(trained_model_path, "model")
    model = model_module.load(trained_model_path)

    # Get the assembled data path: by default, that of the training of
    # the model.
    data_path = ml_models.files.get_validation_data_path(data_path, manifest)

    # Read and prepare the dataset.
    prepared_dataset = ml_models.data.prepare_split_datasets(
        data_path, ml_config, True, used_validation_set
    )

    # Check that the model was trained with the features, target, data
    # and sets of the prepared dataset.
    ml_models.data.check_model_features(
        model, prepared_dataset["training"]["features"]
    )
    ml_models.files.check_model_manifest(
        manifest, ml_config, data_path, prepared_dataset
    )

    # Make predictions.
    predictions = model_module.predict(model, prepared_dataset)

    # Calculate MAPEs.
    mapes = ml_models.evaluation.calculate_mapes(prepared_dataset, predictions)

    # Save the MAPEs.
    ml_models.files.save_results(
        "validation",
        mapes,
        os.path.basename(trained_model_path).split(".")[0],
        os.path.basename(data_path).split(".")[0],
        "all",
        model_path=trained_model_path,
        data_path=data_path,
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
    ml_config = ml_models.data.read_and_check_ml_configuration()

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

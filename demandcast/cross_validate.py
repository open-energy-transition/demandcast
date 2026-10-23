"""
License: AGPL-3.0.

Description:

    This script performs a cross-validation of a machine learning model
    using a preprocessed dataset, implementing a Leave-One-Group-Out
    (LOGO) strategy and saving the results.
"""

import logging
import os

import ml_models.data
import ml_models.evaluation
import ml_models.files
import ml_models.registry
import utils.config
from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Settings of cross_validate.py."""

    scoring_metric: str
    n_jobs: int | None = 1
    data_path: str | None = None


def run_model_cross_validation(
    scoring_metric: str,
    n_jobs: int | None,
    data_path: str | None,
    ml_config: ml_models.data.ConfigModel,
    model_config: BaseModel,
) -> None:
    """
    Run cross-validation of the machine learning model and save results.

    Parameters
    ----------
    scoring_metric : str
        The scoring metric of the cross-validation.
    n_jobs : int | None
        The number of jobs to run in parallel.
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models, with the
        algorithm.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.
    """
    logging.info("Starting cross-validation process.")

    # Get the assembled data path.
    data_path = ml_models.files.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = ml_models.data.prepare_dataset(data_path, ml_config)

    # Run Leave-One-Group-Out cross-validation.
    mapes = ml_models.evaluation.cross_validate(
        prepared_dataset,
        scoring_metric,
        n_jobs,
        ml_config.algorithm,
        model_config,
    )

    # Save the cross-validation results.
    ml_models.files.save_results(
        "cross_validation",
        mapes,
        ml_config.algorithm.lower(),
        os.path.basename(data_path).split(".")[0],
        "all",
    )


def main(config: ConfigModel) -> None:
    """
    Cross-validate the model of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("model_cross_validation")
    utils.config.log_configuration(config)

    # Read and check machine learning configuration.
    ml_config = ml_models.data.read_and_check_ml_configuration()

    run_model_cross_validation(
        config.scoring_metric,
        config.n_jobs,
        config.data_path,
        ml_config,
        ml_models.registry.read_model_configuration(ml_config.algorithm),
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "cross_validate",
            ConfigModel,
            "Perform cross-validation of the machine learning model using "
            "the specified preprocessed data and algorithm.",
        )
    )

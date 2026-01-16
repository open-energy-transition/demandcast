# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script performs a cross-validation of a machine learning model
    using a preprocessed dataset, implementing a Leave-One-Group-Out
    (LOGO) strategy and saving the results.
"""

import logging
import os
from typing import Optional

import ml_models.xgboost
import pandas
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError
from sklearn.model_selection import LeaveOneGroupOut, cross_validate


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for model cross-validation.

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
        scoring_metric: str
        n_jobs: Optional[int] = 1
        data_path: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "cross_validate",
        "Perform cross-validation of the machine learning model using the "
        "specified preprocessed data and algorithm.",
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


def _cross_validate(
    prepared_dataset: dict[str, pandas.DataFrame],
    scoring_metric: str,
    n_jobs: int,
    algorithm: str,
) -> pandas.DataFrame:
    """
    Run cross-validation for the specified machine learning model.

    Parameters
    ----------
    prepared_dataset : dict[str, pandas.DataFrame]
        A dictionary containing prepared features, target, and entity
        codes.
    scoring_metric : str
        The scoring metric to use for evaluation.
    n_jobs : int
        The number of parallel jobs to run.
    algorithm : str
        The machine learning algorithm to use.

    Returns
    -------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values for each entity.

    Raises
    ------
    ValueError
        If an unsupported algorithm is specified.
    """
    # Get an initialized model.
    if algorithm.lower() == "xgboost":
        xgb_model = ml_models.xgboost.get_initialized_model()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    # Perform Leave-One-Group-Out cross-validation
    cv_results = cross_validate(
        xgb_model,
        prepared_dataset["features"],
        prepared_dataset["target"],
        groups=prepared_dataset["entity_codes"],
        cv=LeaveOneGroupOut(),
        scoring=scoring_metric,
        return_train_score=True,
        return_indices=True,
        return_estimator=True,
        n_jobs=n_jobs,
    )

    logging.info("Cross-validation completed successfully.")

    # Initialize a DataFrame to store mapes.
    mapes = pandas.DataFrame()

    # Extract entity codes.
    list_entity_codes = []
    for test_indices in cv_results["indices"]["test"]:
        list_entity_codes.append(
            prepared_dataset["entity_codes"].iloc[test_indices[0]]
        )
    mapes["Entity Code"] = list_entity_codes

    # Add train and test scores to the results DataFrame.
    mapes["Training MAPE"] = -cv_results["train_score"]
    mapes["Testing MAPE"] = -cv_results["test_score"]

    logging.info("Training set:")
    logging.info(f" - Average MAPE: {mapes['Training MAPE'].mean():.4f}")
    logging.info(f" - Median MAPE: {mapes['Training MAPE'].median():.4f}")
    logging.info(f" - Std MAPE: {mapes['Training MAPE'].std():.4f}")
    logging.info("Testing set:")
    logging.info(f" - Average MAPE: {mapes['Testing MAPE'].mean():.4f}")
    logging.info(f" - Median MAPE: {mapes['Testing MAPE'].median():.4f}")
    logging.info(f" - Std MAPE: {mapes['Testing MAPE'].std():.4f}")

    return mapes


def _save_mapes(
    mapes: pandas.DataFrame,
    subfolder: str,
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
        subfolder,
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


def run_model_cross_validation(
    scoring_metric: str,
    n_jobs: int,
    data_path: str | None,
    algorithm: str,
    features: list[str],
    target: str,
    categorical_features: list[str] | None,
) -> None:
    """
    Run cross-validation of the machine learning model and save results.

    Parameters
    ----------
    use_validation_set : bool
        Whether to use a validation set during cross-validation.
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
    """
    logging.info("Starting cross-validation process.")

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(
        data_path,
        False,
        False,
        features,
        target,
        categorical_features,
    )

    # Run Leave-One-Group-Out cross-validation.
    mapes = _cross_validate(
        prepared_dataset,
        scoring_metric,
        n_jobs,
        algorithm,
    )

    # Define the subfolder name for saving results.
    subfolder = f"cross_validation_{algorithm.lower()}_{pandas.Timestamp.now().strftime('%Y%m%d-%H%M%S')}"

    # Save the MAPE values to CSV and parquet files.
    _save_mapes(
        mapes,
        subfolder,
    )


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("model_cross_validation")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Read and check features and target configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    # Run the model validation process.
    run_model_cross_validation(
        config.scoring_metric,
        config.n_jobs,
        config.data_path,
        ml_config.algorithm,
        ml_config.features,
        ml_config.target,
        ml_config.categorical_features,
    )

"""
License: AGPL-3.0.

Description:

    This script performs a cross-validation of a machine learning model
    using a preprocessed dataset, implementing a Leave-One-Group-Out
    (LOGO) strategy and saving the results.
"""

import logging
import os
from typing import Any

import ml_models.registry
import numpy as np
import pandas as pd
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import get_scorer
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.utils.parallel import Parallel, delayed


class ConfigModel(BaseModel):
    """Settings of cross_validate.py."""

    scoring_metric: str
    n_jobs: int | None = 1
    data_path: str | None = None


def _read_and_check_configuration() -> ConfigModel:
    """
    Read and check the configuration for model cross-validation.

    Returns
    -------
    config : ConfigModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """
    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "cross_validate",
        "Perform cross-validation of the machine learning model using the "
        "specified preprocessed data and algorithm.",
    )

    # Validate the configuration.
    try:
        config = ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e

    logging.info("Configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")

    return config


def _log_mape_summary(mapes: pd.DataFrame) -> None:
    """
    Log average, median, and standard deviation of MAPE values.

    Parameters
    ----------
    mapes : pandas.DataFrame
        DataFrame with "Training MAPE" and "Testing MAPE" columns.
    """
    logging.info("Training set:")
    logging.info(f" - Average MAPE: {mapes['Training MAPE'].mean():.4f}")
    logging.info(f" - Median MAPE: {mapes['Training MAPE'].median():.4f}")
    logging.info(f" - Std MAPE: {mapes['Training MAPE'].std():.4f}")
    logging.info("Testing set:")
    logging.info(f" - Average MAPE: {mapes['Testing MAPE'].mean():.4f}")
    logging.info(f" - Median MAPE: {mapes['Testing MAPE'].median():.4f}")
    logging.info(f" - Std MAPE: {mapes['Testing MAPE'].std():.4f}")


class _GroupAwareModel(RegressorMixin, BaseEstimator):
    """
    Adapt a trained model for scikit-learn scorers.

    A scorer calls ``predict`` with the features only. This wrapper
    keeps the entity codes of the rows to predict, so that models that
    build sequences, such as the LSTM, do not cross the boundaries
    between entities.
    """

    def __init__(
        self, model_module: Any, model: Any, group: pd.Series
    ) -> None:
        self.model_module = model_module
        self.model = model
        self.group = group

    def predict(self, features: pd.DataFrame) -> pd.Series:
        """
        Predict the target of the given rows.

        Parameters
        ----------
        features : pandas.DataFrame
            The features of the rows, in the order of the entity codes
            of the wrapper.

        Returns
        -------
        pandas.Series
            The predictions, one per row.
        """
        return self.model_module.predict(
            self.model, {"features": features, "group": self.group}
        )


def _score_fold(
    algorithm: str,
    prepared_dataset: utils.ml.PreparedDataset,
    scoring_metric: str,
    train_index: np.ndarray,
    test_index: np.ndarray,
) -> tuple[str, float, float]:
    """
    Train a model on one fold and score it.

    Parameters
    ----------
    algorithm : str
        The machine learning algorithm.
    prepared_dataset : PreparedDataset
        The features, target and entity codes of the dataset.
    scoring_metric : str
        The scoring metric of scikit-learn.
    train_index : numpy.ndarray
        The positions of the training rows.
    test_index : numpy.ndarray
        The positions of the rows of the held-out entity.

    Returns
    -------
    tuple[str, float, float]
        The code of the held-out entity, and the scores of the model on
        the training rows and on the held-out rows.
    """
    model_module = ml_models.registry.get_model_module(algorithm)
    features = prepared_dataset["features"]
    target = prepared_dataset["target"]
    group = prepared_dataset["group"]

    # Train the model with the entity codes of the training rows.
    model = model_module.train(
        {
            "training": {
                "features": features.iloc[train_index],
                "target": target.iloc[train_index],
                "group": group.iloc[train_index],
            }
        }
    )

    # Score the model on the training rows and on the held-out rows.
    scorer = get_scorer(scoring_metric)
    train_score, test_score = (
        scorer(
            _GroupAwareModel(model_module, model, group.iloc[index]),
            features.iloc[index],
            target.iloc[index],
        )
        for index in (train_index, test_index)
    )

    return group.iloc[test_index[0]], train_score, test_score


def _cross_validate(
    prepared_dataset: utils.ml.PreparedDataset,
    scoring_metric: str,
    n_jobs: int | None,
    algorithm: str,
) -> pd.DataFrame:
    """
    Run Leave-One-Group-Out cross-validation of a model.

    Each entity is held out in turn: a model is trained on the other
    entities, and scored on its training rows and on the rows of the
    held-out entity.

    Parameters
    ----------
    prepared_dataset : PreparedDataset
        The features, target and entity codes of the dataset.
    scoring_metric : str
        The scoring metric to use for evaluation.
    n_jobs : int | None
        The number of folds to run in parallel.
    algorithm : str
        The machine learning algorithm to use.

    Returns
    -------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values for each entity.
    """
    # Check that the algorithm is supported.
    ml_models.registry.get_model_module(algorithm)

    folds = Parallel(n_jobs=n_jobs)(
        delayed(_score_fold)(
            algorithm, prepared_dataset, scoring_metric, train, test
        )
        for train, test in LeaveOneGroupOut().split(
            prepared_dataset["features"],
            prepared_dataset["target"],
            prepared_dataset["group"],
        )
    )

    logging.info("Cross-validation completed successfully.")

    # The scores of scikit-learn are negative errors, such as the
    # negative MAPE.
    mapes = pd.DataFrame(
        folds, columns=["Entity Code", "Training MAPE", "Testing MAPE"]
    )
    mapes[["Training MAPE", "Testing MAPE"]] *= -1

    _log_mape_summary(mapes)

    return mapes


def run_model_cross_validation(
    scoring_metric: str,
    n_jobs: int | None,
    data_path: str | None,
    algorithm: str,
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
    algorithm : str
        The machine learning algorithm to use for training.
    """
    logging.info("Starting cross-validation process.")

    # Get the assembled data path.
    data_path = utils.ml.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(data_path)

    # Run Leave-One-Group-Out cross-validation.
    mapes = _cross_validate(
        prepared_dataset,
        scoring_metric,
        n_jobs,
        algorithm,
    )

    # Save the cross-validation results.
    utils.ml.save_results(
        "cross_validation",
        mapes,
        algorithm.lower(),
        os.path.basename(data_path).split(".")[0],
        "all",
    )


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("model_cross_validation")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Read and check machine learning configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    # Run the model validation process.
    run_model_cross_validation(
        config.scoring_metric,
        config.n_jobs,
        config.data_path,
        ml_config.algorithm,
    )

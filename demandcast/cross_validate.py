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

import ml_models.lstm
import ml_models.xgboost
import pandas
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import get_scorer
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


def _log_mape_summary(mapes: pandas.DataFrame) -> None:
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


def _cross_validate_xgboost(
    prepared_dataset: dict[str, pandas.DataFrame],
    scoring_metric: str,
    n_jobs: int,
) -> pandas.DataFrame:
    """
    Run Leave-One-Group-Out cross-validation for XGBoost.

    Uses sklearn's ``cross_validate()`` directly. This is safe for
    XGBoost because its ``fit()``/``predict()`` calls do not depend
    on entity ``groups`` — unlike the LSTM, whose sequence
    construction must respect entity boundaries and therefore cannot
    go through ``cross_validate()`` (see ``_cross_validate_lstm``).

    Parameters
    ----------
    prepared_dataset : dict[str, pandas.DataFrame]
        A dictionary containing prepared features, target, and entity
        codes.
    scoring_metric : str
        The scoring metric to use for evaluation.
    n_jobs : int
        The number of parallel jobs to run.

    Returns
    -------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values for each entity.
    """
    model = ml_models.xgboost.get_initialized_model()

    # Perform Leave-One-Group-Out cross-validation
    cv_results = cross_validate(
        model,
        prepared_dataset["features"],
        prepared_dataset["target"],
        groups=prepared_dataset["group"],
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
            prepared_dataset["group"].iloc[test_indices[0]]
        )
    mapes["Entity Code"] = list_entity_codes

    # Add train and test scores to the results DataFrame.
    mapes["Training MAPE"] = -cv_results["train_score"]
    mapes["Testing MAPE"] = -cv_results["test_score"]

    _log_mape_summary(mapes)

    return mapes


class _GroupAwareLSTM(BaseEstimator, RegressorMixin):
    """
    Adapt a fitted LSTM model for sklearn scorers.

    A scorer obtained from ``sklearn.metrics.get_scorer()`` calls
    ``estimator.predict(X)`` with no way to pass entity ``groups``
    alongside ``X``. This wrapper closes over the group labels for a
    specific fold/split so that predictions still respect entity
    boundaries, while routing every prediction through
    ``ml_models.lstm.predict()``. Inherits from ``BaseEstimator`` and
    ``RegressorMixin`` only so sklearn's scorer machinery recognises
    it as a fitted regressor.
    """

    def __init__(
        self,
        lstm_model: ml_models.lstm.LSTMRegressor,
        group: pandas.Series,
    ) -> None:
        self.lstm_model = lstm_model
        self.group = group

    def predict(self, features: pandas.DataFrame) -> pandas.Series:
        """
        Predict target values for ``features``.

        Parameters
        ----------
        features : pandas.DataFrame
            Feature rows to predict on. Must align row-for-row with
            the ``group`` labels this wrapper was built with.

        Returns
        -------
        pandas.Series
            Predicted values, one per row of ``features``.
        """
        return ml_models.lstm.predict(
            self.lstm_model,
            {"features": features, "group": self.group},
        )


def _cross_validate_lstm(
    prepared_dataset: dict[str, pandas.DataFrame],
    scoring_metric: str,
) -> pandas.DataFrame:
    """
    Run manual Leave-One-Group-Out cross-validation for the LSTM.

    sklearn's ``cross_validate()`` never forwards ``groups`` into
    ``estimator.fit()``, so using it for the LSTM would silently let
    it build sequences across country boundaries during
    cross-validation (``groups`` would be ``None`` inside ``fit()``).
    This function instead builds LOGO folds by hand with
    ``LeaveOneGroupOut().split()`` and calls ``ml_models.lstm.train()``
    and ``ml_models.lstm.predict()`` directly for each fold, so
    group boundaries are always respected.

    Parameters
    ----------
    prepared_dataset : dict[str, pandas.DataFrame]
        A dictionary containing prepared features, target, and entity
        codes.
    scoring_metric : str
        The scoring metric to use for evaluation.

    Returns
    -------
    mapes : pandas.DataFrame
        DataFrame containing MAPE values for each entity.
    """
    scorer = get_scorer(scoring_metric)

    features = prepared_dataset["features"]
    target = prepared_dataset["target"]
    group = prepared_dataset["group"]

    list_entity_codes = []
    train_scores = []
    test_scores = []

    for train_index, test_index in LeaveOneGroupOut().split(
        features, target, group
    ):
        fold_dataset = {
            "training": {
                "features": features.iloc[train_index],
                "target": target.iloc[train_index],
                "group": group.iloc[train_index],
            }
        }
        lstm_model = ml_models.lstm.train(fold_dataset)

        train_scores.append(
            scorer(
                _GroupAwareLSTM(lstm_model, group.iloc[train_index]),
                features.iloc[train_index],
                target.iloc[train_index],
            )
        )
        test_scores.append(
            scorer(
                _GroupAwareLSTM(lstm_model, group.iloc[test_index]),
                features.iloc[test_index],
                target.iloc[test_index],
            )
        )
        list_entity_codes.append(group.iloc[test_index[0]])

    logging.info("Cross-validation completed successfully.")

    # Initialize a DataFrame to store mapes.
    mapes = pandas.DataFrame()
    mapes["Entity Code"] = list_entity_codes

    # Add train and test scores to the results DataFrame.
    mapes["Training MAPE"] = -pandas.Series(train_scores)
    mapes["Testing MAPE"] = -pandas.Series(test_scores)

    _log_mape_summary(mapes)

    return mapes


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
    if algorithm.lower() == "xgboost":
        return _cross_validate_xgboost(
            prepared_dataset, scoring_metric, n_jobs
        )
    elif algorithm.lower() == "lstm":
        return _cross_validate_lstm(prepared_dataset, scoring_metric)
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")


def run_model_cross_validation(
    scoring_metric: str,
    n_jobs: int,
    data_path: str | None,
    algorithm: str,
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
    """
    logging.info("Starting cross-validation process.")

    # Get the assembled data path.
    data_path = utils.ml.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(
        data_path,
        False,
        False,
    )

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

"""
License: AGPL-3.0.

Description:

    This module evaluates the machine learning models: the mean
    absolute percentage error (MAPE) of each country and subdivision,
    on each set of a validation, and the Leave-One-Group-Out
    cross-validation, which trains a model without each country or
    subdivision in turn and scores it on the one left out.

    The errors are those of the target of the models, the load relative
    to the annual mean of its local year (see utils.ml), so they measure
    the error of the hourly profile, not that of the annual demand.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
import utils.ml
from pydantic import BaseModel
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.metrics import get_scorer, mean_absolute_percentage_error
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.utils.parallel import Parallel, delayed

import ml_models.registry


def log_summary(name: str, mapes: pd.Series) -> None:
    """
    Log the average, median and standard deviation of MAPEs.

    Parameters
    ----------
    name : str
        The name of the set, such as "Testing".
    mapes : pandas.Series
        The MAPE of each country or subdivision.
    """
    logging.info(f"{name} set:")
    logging.info(f" - Average MAPE = {mapes.mean():.4f}")
    logging.info(f" - Median MAPE = {mapes.median():.4f}")
    logging.info(f" - Std MAPE = {mapes.std():.4f}")


def calculate_mape_by_entity(
    predictions: pd.Series,
    actual: pd.Series,
    entity_codes: pd.Series,
) -> pd.Series:
    """
    Calculate the MAPE of each country or subdivision.

    Parameters
    ----------
    predictions : pandas.Series
        The predictions of the model.
    actual : pandas.Series
        The actual values of the target, in the same order.
    entity_codes : pandas.Series
        The code of the country or subdivision of each row, named
        "Entity code".

    Returns
    -------
    mapes : pandas.Series
        The MAPE of each country or subdivision, indexed by its code.
    """
    # Initialize lists to hold entity codes and their MAPE values.
    list_entity_codes = []
    list_mapes_values = []

    # Calculate MAPE for each entity.
    for entity_code, entity_group in pd.DataFrame(entity_codes).groupby(
        "Entity code"
    ):
        current_mape = mean_absolute_percentage_error(
            actual.iloc[entity_group.index],
            predictions.iloc[entity_group.index],
        )
        list_entity_codes.append(entity_code)
        list_mapes_values.append(current_mape)

    # Create a Series for MAPE values indexed by entity codes.
    mapes = pd.Series(
        data=list_mapes_values,
        index=list_entity_codes,
        name="MAPE",
    ).rename_axis("Entity code")

    return mapes


def calculate_mapes(
    prepared_dataset: dict[str, utils.ml.PreparedDataset],
    predictions: dict[str, pd.Series],
) -> pd.DataFrame:
    """
    Calculate the MAPEs of each set: training, validation and testing.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared dataset of each set.
    predictions : dict[str, pandas.Series]
        The predictions of each set.

    Returns
    -------
    mapes : pandas.DataFrame
        The code of each country or subdivision, and its MAPE in each
        set, in the columns "<Set> MAPE".
    """
    # Initialize a DataFrame to hold MAPE results.
    mapes = pd.DataFrame()

    for split in prepared_dataset:
        # Calculate MAPE per entity for the current split.
        mapes_of_split = calculate_mape_by_entity(
            predictions[split],
            prepared_dataset[split]["target"],
            prepared_dataset[split]["group"],
        )

        # Store the MAPE values in the results DataFrame.
        mapes[f"{split.capitalize()} MAPE"] = mapes_of_split
        log_summary(split.capitalize(), mapes_of_split)

    # Reset the index and reorder columns.
    mapes = mapes.reset_index()
    column_order = ["Entity code"] + [
        f"{split.capitalize()} MAPE" for split in prepared_dataset
    ]
    mapes = mapes[column_order]

    return mapes


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
    model_config: BaseModel,
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
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.
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
        },
        model_config,
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


def cross_validate(
    prepared_dataset: utils.ml.PreparedDataset,
    scoring_metric: str,
    n_jobs: int | None,
    algorithm: str,
    model_config: BaseModel,
) -> pd.DataFrame:
    """
    Run the Leave-One-Group-Out cross-validation of a model.

    Each entity is held out in turn: a model is trained on the other
    entities, and scored on its training rows and on the rows of the
    held-out entity.

    Parameters
    ----------
    prepared_dataset : PreparedDataset
        The features, target and entity codes of the dataset.
    scoring_metric : str
        The scoring metric of scikit-learn, such as
        "neg_mean_absolute_percentage_error".
    n_jobs : int | None
        The number of folds to run in parallel.
    algorithm : str
        The machine learning algorithm to use.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.

    Returns
    -------
    mapes : pandas.DataFrame
        The code of each held-out entity, and the scores of its model
        on the training rows and on the rows of the entity.
    """
    # Check that the algorithm is supported.
    ml_models.registry.get_model_module(algorithm)

    folds = Parallel(n_jobs=n_jobs)(
        delayed(_score_fold)(
            algorithm,
            model_config,
            prepared_dataset,
            scoring_metric,
            train,
            test,
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
    log_summary("Training", mapes["Training MAPE"])
    log_summary("Testing", mapes["Testing MAPE"])
    return mapes

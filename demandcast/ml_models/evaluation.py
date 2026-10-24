"""
License: AGPL-3.0.

Description:

    This module evaluates the machine learning models: the mean
    absolute percentage error (MAPE) of each country and subdivision,
    on each set of a validation, and the Leave-One-Group-Out
    cross-validation, which trains a model without each country or
    subdivision in turn and scores it on the one left out.

    The cross-validation can instead hold out each country with its
    subdivisions, so that a model is scored on a country of which it
    has seen no part: holding out Argentina alone still trains on its
    provinces, which measures the error on a held-out entity, not on an
    unseen country. Its results say which holdout they used.

    The errors are those of the target of the models, the load relative
    to the annual mean of its local year (see ml_models.data), so they
    measure the error of the hourly profile, not that of the annual
    demand. The models are trained and scored on all the fields of their
    rows, such as their times, as in a validation.
"""

import logging
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.utils.parallel import Parallel, delayed

import ml_models.data
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
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
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


def _score_fold(
    algorithm: str,
    model_config: BaseModel,
    prepared_dataset: ml_models.data.PreparedDataset,
    train_index: np.ndarray,
    test_index: np.ndarray,
) -> list[tuple[str, float, float]]:
    """
    Train a model on one fold and score it.

    Parameters
    ----------
    algorithm : str
        The machine learning algorithm.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.
    prepared_dataset : PreparedDataset
        The features, target, entity codes and other fields of the
        dataset.
    train_index : numpy.ndarray
        The positions of the training rows.
    test_index : numpy.ndarray
        The positions of the held-out rows.

    Returns
    -------
    list[tuple[str, float, float]]
        The code of each held-out entity, the MAPE of the model on the
        training rows, and its MAPE on the rows of the entity.
    """
    model_module = ml_models.registry.get_model_module(algorithm)
    training = ml_models.data.select_rows(prepared_dataset, train_index)
    held_out = ml_models.data.select_rows(prepared_dataset, test_index)

    model = model_module.train({"training": training}, model_config)

    training_mape = mean_absolute_percentage_error(
        training["target"], model_module.predict(model, training)
    )
    predictions = pd.Series(
        np.asarray(model_module.predict(model, held_out)),
        index=held_out["target"].index,
    )
    return [
        (
            str(entity_code),
            training_mape,
            mean_absolute_percentage_error(
                held_out["target"][rows], predictions[rows]
            ),
        )
        for entity_code, rows in held_out["group"]
        .groupby(held_out["group"])
        .groups.items()
    ]


def cross_validate(
    prepared_dataset: ml_models.data.PreparedDataset,
    n_jobs: int | None,
    algorithm: str,
    model_config: BaseModel,
    holdout: Literal["entity", "country"] = "entity",
) -> pd.DataFrame:
    """
    Run the Leave-One-Group-Out cross-validation of a model.

    Each entity, or each country with its subdivisions, is held out in
    turn: a model is trained on the others, and scored on its training
    rows and on the rows of each held-out entity.

    Parameters
    ----------
    prepared_dataset : PreparedDataset
        The features, target, entity codes and other fields of the
        dataset.
    n_jobs : int | None
        The number of folds to run in parallel.
    algorithm : str
        The machine learning algorithm to use.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.
    holdout : str, optional
        What each fold holds out: an "entity", or a "country" with its
        subdivisions.

    Returns
    -------
    mapes : pandas.DataFrame
        The code of each held-out entity, the MAPE of its model on the
        training rows and on the rows of the entity, and the holdout.
    """
    # Check that the algorithm is supported.
    ml_models.registry.get_model_module(algorithm)

    group = prepared_dataset["group"]
    folds = group if holdout == "entity" else group.str.split("_").str[0]

    results = Parallel(n_jobs=n_jobs)(
        delayed(_score_fold)(
            algorithm, model_config, prepared_dataset, train, test
        )
        for train, test in LeaveOneGroupOut().split(
            prepared_dataset["features"], prepared_dataset["target"], folds
        )
    )
    logging.info("Cross-validation completed successfully.")

    mapes = pd.DataFrame(
        [row for fold in results for row in fold],
        columns=["Entity code", "Training MAPE", "Testing MAPE"],
    )
    mapes["Holdout"] = holdout
    log_summary("Training", mapes["Training MAPE"])
    log_summary("Testing", mapes["Testing MAPE"])
    return mapes

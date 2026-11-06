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

    Each error is given as the mean absolute percentage error (MAPE)
    and as the weighted absolute percentage error (WAPE).

    The errors are those of the target of the models, the load relative
    to the annual mean of its local year (see ml_models.data), so they
    measure the error of the hourly profile, not that of the annual
    demand, and each year of an entity counts the same, whatever its
    demand. The results also give the sum of the absolute errors of
    each entity and of its demand in MWh, with the error of each hour
    in MW, its error times the mean load of its local year, so that the
    WAPE of a group of entities is that of all their hours in MW (see
    ml_models.reporting).
"""

import logging
import os
from typing import Any, Literal

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


def weighted_absolute_percentage_error(
    actual: pd.Series | np.ndarray, predictions: pd.Series | np.ndarray
) -> float:
    """
    Calculate the weighted absolute percentage error (WAPE).

    The WAPE is the sum of the absolute errors divided by the sum of the
    absolute actual values.

    Parameters
    ----------
    actual : pandas.Series | numpy.ndarray
        The actual values.
    predictions : pandas.Series | numpy.ndarray
        The predictions, in the same order.

    Returns
    -------
    float
        The WAPE, as a fraction.

    Notes
    -----
    Unlike the MAPE, whose error of each hour is divided by its own
    actual value, the WAPE is not dominated by the hours whose actual
    value is close to zero, such as the net demand of North Macedonia at
    midday in 2025.
    """
    actual_values = np.asarray(actual, dtype=float)
    errors = np.abs(np.asarray(predictions, dtype=float) - actual_values)
    return float(errors.sum() / np.abs(actual_values).sum())


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
    return _calculate_by_entity(
        predictions, actual, entity_codes, mean_absolute_percentage_error
    ).rename("MAPE")


def calculate_wape_by_entity(
    predictions: pd.Series,
    actual: pd.Series,
    entity_codes: pd.Series,
) -> pd.Series:
    """
    Calculate the WAPE of each country or subdivision.

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
    pandas.Series
        The WAPE of each country or subdivision, indexed by its code.
    """
    return _calculate_by_entity(
        predictions, actual, entity_codes, weighted_absolute_percentage_error
    ).rename("WAPE")


def _calculate_by_entity(
    predictions: pd.Series,
    actual: pd.Series,
    entity_codes: pd.Series,
    metric: Any,
) -> pd.Series:
    """
    Calculate an error of each country or subdivision.

    Parameters
    ----------
    predictions : pandas.Series
        The predictions of the model.
    actual : pandas.Series
        The actual values of the target, in the same order.
    entity_codes : pandas.Series
        The code of the country or subdivision of each row, named
        "Entity code".
    metric : Any
        The function of the error, of the actual values and of the
        predictions.

    Returns
    -------
    pandas.Series
        The error of each country or subdivision, indexed by its code.
    """
    list_entity_codes = []
    list_mapes_values = []

    for entity_code, entity_group in pd.DataFrame(entity_codes).groupby(
        "Entity code"
    ):
        current_mape = metric(
            actual.iloc[entity_group.index],
            predictions.iloc[entity_group.index],
        )
        list_entity_codes.append(entity_code)
        list_mapes_values.append(current_mape)

    mapes = pd.Series(
        data=list_mapes_values,
        index=list_entity_codes,
    ).rename_axis("Entity code")

    return mapes


def get_scored_predictions(
    predictions: pd.Series, data: ml_models.data.PreparedDataset
) -> pd.DataFrame | None:
    """
    Get the predictions of the scored rows in MW.

    The target of each hour is its load divided by the mean load of its
    local year among the rows, so its prediction times that mean is its
    prediction in MW, with the same annual demand as the actual one: the
    two differ by the error of the hourly profile, which the WAPE
    measures.

    Parameters
    ----------
    predictions : pandas.Series
        The predictions of the model, in the order of the rows.
    data : PreparedDataset
        The rows, with their target, entity code, time and local year,
        and their load in MW among their other fields.

    Returns
    -------
    pandas.DataFrame | None
        The entity code ("Entity code"), the end of the hour in UTC
        ("Time (UTC)"), the local year ("Local year"), the actual load
        ("Load (MW)") and the predicted load ("Forecast load (MW)") of
        each row, or None if the rows have no load in MW, time or local
        year.
    """
    others = data.get("others")
    if (
        others is None
        or "Load (MW)" not in others
        or "local_year" not in data
        or "time" not in data
    ):
        return None
    rows = pd.DataFrame(
        {
            "Entity code": data["group"].to_numpy(),
            "Time (UTC)": data["time"].to_numpy(),
            "Local year": data["local_year"].to_numpy(),
            "Load (MW)": others["Load (MW)"].to_numpy(dtype=float),
            "Target": data["target"].to_numpy(dtype=float),
        }
    )
    sums = rows.groupby(["Entity code", "Local year"])[
        ["Load (MW)", "Target"]
    ].transform("sum")
    rows["Forecast load (MW)"] = np.asarray(predictions, dtype=float) * (
        sums["Load (MW)"] / sums["Target"]
    )
    return rows.drop(columns="Target")


def calculate_energy_errors_by_entity(
    predictions: pd.Series, data: ml_models.data.PreparedDataset
) -> pd.DataFrame | None:
    """
    Calculate the absolute errors and the demand of each entity in MWh.

    The error of each hour is that of its prediction in MW (see
    get_scored_predictions), in MWh over the hour.

    Parameters
    ----------
    predictions : pandas.Series
        The predictions of the model, in the order of the rows.
    data : PreparedDataset
        The rows, with their target, entity code, time and local year,
        and their load in MW among their other fields.

    Returns
    -------
    pandas.DataFrame | None
        The sum of the absolute errors ("Absolute error (MWh)") and of
        the demand ("Demand (MWh)") of each entity, indexed by its code,
        or None if the rows have no load in MW, time or local year.
    """
    rows = get_scored_predictions(predictions, data)
    if rows is None:
        return None
    rows["Absolute error (MWh)"] = (
        rows["Forecast load (MW)"] - rows["Load (MW)"]
    ).abs()
    rows["Demand (MWh)"] = rows["Load (MW)"]
    return rows.groupby("Entity code")[
        ["Absolute error (MWh)", "Demand (MWh)"]
    ].sum()


def calculate_mapes(
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
    predictions: dict[str, pd.Series],
) -> pd.DataFrame:
    """
    Calculate the MAPEs of each set: training, validation and testing.

    Besides the MAPE of the predictions as the model gives them, the
    MAPE of the predictions scaled to the annual total of their year,
    as forecast.py delivers them, is calculated on the complete years
    of each entity, those with all their hours, and is missing for an
    entity without one (see ml_models.data.normalize_to_annual_totals).

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared dataset of each set.
    predictions : dict[str, pandas.Series]
        The predictions of each set.

    Returns
    -------
    mapes : pandas.DataFrame
        The code of each country or subdivision, and its MAPE and WAPE
        in each set, in the columns "<Set> MAPE", "<Set> WAPE" and
        "<Set> MAPE of the complete years scaled to their annual
        totals", and, if the rows have their load in MW, the sums of its
        absolute errors and of its demand in "<Set> absolute error
        (MWh)" and "<Set> demand (MWh)".
    """
    columns: dict[str, pd.Series] = {}
    for split, data in prepared_dataset.items():
        name = split.capitalize()
        mapes_of_split = calculate_mape_by_entity(
            predictions[split], data["target"], data["group"]
        )
        columns[f"{name} MAPE"] = mapes_of_split
        columns[f"{name} WAPE"] = calculate_wape_by_entity(
            predictions[split], data["target"], data["group"]
        )
        log_summary(name, mapes_of_split)
        logging.info(
            f" - Median WAPE = {columns[f'{name} WAPE'].median():.4f}"
        )
        energy = calculate_energy_errors_by_entity(predictions[split], data)
        if energy is not None:
            columns[f"{name} absolute error (MWh)"] = energy[
                "Absolute error (MWh)"
            ]
            columns[f"{name} demand (MWh)"] = energy["Demand (MWh)"]

        if "time" in data and "local_year" in data:
            scaled, status = ml_models.data.normalize_to_annual_totals(
                predictions[split],
                data["group"],
                data["local_year"],
                data["time"],
                report=False,
            )
            complete = pd.MultiIndex.from_arrays(
                [data["group"], data["local_year"].astype(int)]
            ).isin(
                pd.MultiIndex.from_frame(
                    status.loc[
                        status["Status"] == "scaled",
                        ["Entity code", "Local year"],
                    ]
                )
            )
            rows = np.flatnonzero(complete)
            columns[
                f"{name} MAPE of the complete years scaled to their annual "
                "totals"
            ] = calculate_mape_by_entity(
                scaled.iloc[rows].reset_index(drop=True),
                data["target"].iloc[rows].reset_index(drop=True),
                data["group"].iloc[rows].reset_index(drop=True),
            ).reindex(mapes_of_split.index)

    return pd.DataFrame(columns).rename_axis("Entity code").reset_index()


def get_folds(
    group: pd.Series, holdout: Literal["entity", "country"]
) -> dict[str, list[str]]:
    """
    Get the entities that each fold of a cross-validation holds out.

    Parameters
    ----------
    group : pandas.Series
        The entity code of each row.
    holdout : str
        What each fold holds out: an "entity", or a "country" with its
        subdivisions.

    Returns
    -------
    dict[str, list[str]]
        The entity codes held out by each fold, by the name of the fold:
        the entity code, or the code of the country.
    """
    codes = sorted(group.unique())
    return {
        fold: [code for code in codes if _get_fold(code, holdout) == fold]
        for fold in sorted({_get_fold(code, holdout) for code in codes})
    }


def _get_fold(code: str, holdout: Literal["entity", "country"]) -> str:
    """
    Get the fold of an entity in a cross-validation.

    Parameters
    ----------
    code : str
        The entity code.
    holdout : str
        What each fold holds out: an "entity", or a "country" with its
        subdivisions.

    Returns
    -------
    str
        The entity code, or the code of its country.
    """
    return code if holdout == "entity" else code.split("_", maxsplit=1)[0]


def _score_fold(
    algorithm: str,
    model_config: BaseModel,
    prepared_dataset: ml_models.data.PreparedDataset,
    train_index: np.ndarray,
    test_index: np.ndarray,
    model_path: str | None = None,
) -> tuple[
    list[tuple[str, float, float, float, float, float, float]],
    pd.DataFrame | None,
]:
    """
    Train a model on one fold and score it, and save it if asked.

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
    model_path : str | None, optional
        The file where the trained model of the fold is saved, with the
        extension of the model, none to not save it.

    Returns
    -------
    tuple[list[tuple[str, float, float, float, float, float, float]], \
pandas.DataFrame | None]
        The code of each held-out entity, the MAPE of the model on the
        training rows and on the rows of the entity, its WAPE on them,
        and the sums of the absolute errors and of the demand of the
        entity in MWh, not numbers if its rows have no load in MW; and
        the predictions of the held-out rows in MW (see
        get_scored_predictions).

    Notes
    -----
    The model is trained and scored on all the fields of the rows, such
    as their times.
    """
    model_module = ml_models.registry.get_model_module(algorithm)
    training = ml_models.data.select_rows(prepared_dataset, train_index)
    held_out = ml_models.data.select_rows(prepared_dataset, test_index)

    model = model_module.train({"training": training}, model_config)
    if model_path is not None:
        model_module.save(model, model_path)

    training_predictions = model_module.predict(model, training)
    training_mape = mean_absolute_percentage_error(
        training["target"], training_predictions
    )
    training_wape = weighted_absolute_percentage_error(
        training["target"], training_predictions
    )
    predictions = pd.Series(
        np.asarray(model_module.predict(model, held_out)),
        index=held_out["target"].index,
    )
    energy = calculate_energy_errors_by_entity(predictions, held_out)
    errors_in_mwh = {} if energy is None else energy.to_dict("index")
    scores = [
        (
            str(entity_code),
            training_mape,
            mean_absolute_percentage_error(
                held_out["target"][rows], predictions[rows]
            ),
            training_wape,
            weighted_absolute_percentage_error(
                held_out["target"][rows], predictions[rows]
            ),
            float(
                errors_in_mwh.get(entity_code, {}).get(
                    "Absolute error (MWh)", np.nan
                )
            ),
            float(
                errors_in_mwh.get(entity_code, {}).get("Demand (MWh)", np.nan)
            ),
        )
        for entity_code, rows in held_out["group"]
        .groupby(held_out["group"])
        .groups.items()
    ]
    return scores, get_scored_predictions(predictions, held_out)


def cross_validate(
    prepared_dataset: ml_models.data.PreparedDataset,
    n_jobs: int | None,
    algorithm: str,
    model_config: BaseModel,
    holdout: Literal["entity", "country"] = "entity",
    models_folder: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """
    Run the Leave-One-Group-Out cross-validation of a model.

    Each entity, or each country with its subdivisions, is held out in
    turn: a model is trained on the others, and scored on its training
    rows and on the rows of each held-out entity. The model of each fold
    can be saved, named after the fold.

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
    models_folder : str | None, optional
        The folder where the model of each fold is saved, as
        <fold><extension of the model>, none to not save them.

    Returns
    -------
    mapes : pandas.DataFrame
        The code of each held-out entity, the MAPE and WAPE of its model
        on the training rows and on the rows of the entity, the sums of
        the absolute errors and of the demand of the entity in MWh, and
        the holdout.
    predictions : pandas.DataFrame | None
        The predictions of the held-out rows in MW (see
        get_scored_predictions), or None if the rows have no load in MW.
    """
    # Check that the algorithm is supported.
    model_module = ml_models.registry.get_model_module(algorithm)

    group = prepared_dataset["group"]
    folds = group.map(lambda code: _get_fold(code, holdout))

    results = Parallel(n_jobs=n_jobs)(
        delayed(_score_fold)(
            algorithm,
            model_config,
            prepared_dataset,
            train,
            test,
            os.path.join(
                models_folder,
                f"{folds.iloc[test[0]]}{model_module.FILE_EXTENSION}",
            )
            if models_folder is not None
            else None,
        )
        for train, test in LeaveOneGroupOut().split(
            prepared_dataset["features"], prepared_dataset["target"], folds
        )
    )
    logging.info("Cross-validation completed successfully.")

    mapes = pd.DataFrame(
        [row for scores, _ in results for row in scores],
        columns=[
            "Entity code",
            "Training MAPE",
            "Testing MAPE",
            "Training WAPE",
            "Testing WAPE",
            "Testing absolute error (MWh)",
            "Testing demand (MWh)",
        ],
    )
    mapes["Holdout"] = holdout
    log_summary("Training", mapes["Training MAPE"])
    log_summary("Testing", mapes["Testing MAPE"])
    fold_predictions = [
        predictions for _, predictions in results if predictions is not None
    ]
    return mapes, (
        pd.concat(fold_predictions, ignore_index=True)
        if fold_predictions
        else None
    )

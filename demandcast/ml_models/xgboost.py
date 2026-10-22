"""
License: AGPL-3.0.

Description:

    This module contains functions to train and save an XGBoost model.
"""

import logging
from typing import cast, overload

import pandas as pd
import utils.ml
from pydantic import BaseModel
from xgboost import XGBRegressor

# The extension of the files of the saved models.
FILE_EXTENSION = ".json"


class ConfigModel(BaseModel):
    """Settings of the XGBoost model."""

    random_state: int = 42
    enable_categorical: bool | None = True
    evaluation_metric: str | None = "mape"


def load(model_path: str) -> XGBRegressor:
    """
    Load a trained XGBoost model.

    Parameters
    ----------
    model_path : str
        Path to the trained model file.

    Returns
    -------
    XGBRegressor
        Loaded XGBoost model.
    """
    xgb_model = XGBRegressor()
    xgb_model.load_model(model_path)

    logging.info(f"Trained model loaded from {model_path}")

    return xgb_model


def save(xgb_model: XGBRegressor, file_path: str) -> None:
    """
    Save the trained XGBoost model.

    Parameters
    ----------
    xgb_model : XGBRegressor
        Trained XGBoost model.
    file_path : str
        The path of the file, with the extension FILE_EXTENSION.
    """
    xgb_model.save_model(file_path)

    logging.info(f"Trained model saved to {file_path}")


def get_initialized_model(config: ConfigModel) -> XGBRegressor:
    """
    Get an initialized XGBoost model based on the configuration.

    Parameters
    ----------
    config : ConfigModel
        The settings of the model.

    Returns
    -------
    XGBRegressor
        Initialized XGBoost model.
    """
    # Initialize model with config parameters.
    xgb_model = XGBRegressor(
        random_state=config.random_state,
        enable_categorical=config.enable_categorical,
        eval_metric=config.evaluation_metric,
    )

    logging.info("XGBoost model initialized with configuration.")

    return xgb_model


def train(
    prepared_dataset: dict[str, utils.ml.PreparedDataset],
    config: ConfigModel,
) -> XGBRegressor:
    """
    Train XGBoost model.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared datasets for training, validation, and testing,
        produced by ``utils.ml.prepare_split_datasets``.
    config : ConfigModel
        The settings of the model.

    Returns
    -------
    XGBRegressor
        Trained model.
    """
    logging.info("Starting XGBoost model training.")

    # Get an initialized model.
    xgb_model = get_initialized_model(config)

    # Prepare evaluation set if the validation dataset is provided.
    eval_set = None
    if "validation" in prepared_dataset:
        eval_set = [
            (
                prepared_dataset["validation"]["features"],
                prepared_dataset["validation"]["target"],
            )
        ]

    # Train the model.
    xgb_model.fit(
        prepared_dataset["training"]["features"],
        prepared_dataset["training"]["target"],
        eval_set=eval_set,
        verbose=False,
    )

    logging.info("XGBoost model training completed.")

    return xgb_model


@overload
def predict(
    xgb_model: XGBRegressor, prepared_dataset: utils.ml.PreparedDataset
) -> pd.Series: ...


@overload
def predict(
    xgb_model: XGBRegressor,
    prepared_dataset: dict[str, utils.ml.PreparedDataset],
) -> dict[str, pd.Series]: ...


def predict(
    xgb_model: XGBRegressor,
    prepared_dataset: utils.ml.PreparedDataset
    | dict[str, utils.ml.PreparedDataset],
) -> pd.Series | dict[str, pd.Series]:
    """
    Make predictions using the trained XGBoost model.

    Parameters
    ----------
    xgb_model : XGBRegressor
        The trained XGBoost model.
    prepared_dataset : PreparedDataset | dict[str, PreparedDataset]
        A prepared dataset, or the prepared datasets for training,
        validation, and testing.

    Returns
    -------
    predictions : pandas.Series | dict[str, pandas.Series]
        The predictions for the dataset, or for each dataset split.
    """
    logging.info("Making predictions with the trained XGBoost model.")

    if "features" in prepared_dataset:
        # The prepared_dataset is a single dataset, not split into
        # training/validation/testing.
        dataset = cast("utils.ml.PreparedDataset", prepared_dataset)

        # Make predictions and return them.
        return pd.Series(xgb_model.predict(dataset["features"]))

    # Initialize predictions dictionary to store training,
    # validation, and testing predictions.
    predictions: dict[str, pd.Series] = {}

    for split_name, data in prepared_dataset.items():
        # Make predictions for the current split.
        preds = xgb_model.predict(data["features"])

        predictions[split_name] = pd.Series(preds)

        logging.info(
            f"Predictions made for {split_name} set: {len(preds)} records."
        )

    return predictions

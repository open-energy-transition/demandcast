"""
License: AGPL-3.0.

Description:

    This module contains functions to train and save an XGBoost model.
"""

import logging
import os
from typing import cast, overload

import pandas as pd
import utils.config
import utils.ml
import yaml
from pydantic import BaseModel, ValidationError
from xgboost import XGBRegressor

# The extension of the files of the saved models.
FILE_EXTENSION = ".json"

# The target ("Load (fraction of annual total)") is about 1/8760, and
# the gain of a split scales with the square of the target, so at that
# magnitude almost no split reaches XGBoost's minimum gain and the
# model barely splits (issue #145). train() therefore fits the target
# multiplied by this factor, which makes 1.0 an average hour, and
# predict() divides the predictions by it to return them in the units
# of the dataset. Models trained before this change must be retrained.
TARGET_SCALE_FACTOR = 8760.0


class ConfigModel(BaseModel):
    """Settings of the XGBoost model."""

    random_state: int = 42
    enable_categorical: bool | None = True
    evaluation_metric: str | None = "mape"


def _read_configuration() -> ConfigModel:
    """
    Read the configuration for XGBoost model training.

    Returns
    -------
    ConfigModel
        Configuration model.

    Raises
    ------
    ValueError
        If the configuration validation fails.
    """
    # Read the configuration.
    config_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "xgboost_config.yaml",
    )

    # Read the raw configuration.
    with open(config_path) as f:
        raw_config = yaml.safe_load(f)

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


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


def save(xgb_model: XGBRegressor, model_name: str) -> None:
    """
    Save the trained XGBoost model.

    Parameters
    ----------
    xgb_model : XGBRegressor
        Trained XGBoost model.
    model_name : str
        Name to identify the model when saving.
    """
    # Get the folder where to save the model.
    model_folder = utils.config.read_folders_structure()[
        "trained_ml_models_folder"
    ]
    os.makedirs(model_folder, exist_ok=True)

    # Define the output path for the model.
    output_path = os.path.join(
        model_folder,
        f"{model_name}{FILE_EXTENSION}",
    )

    # Save the trained model.
    xgb_model.save_model(output_path)

    logging.info(f"Trained model saved to {output_path}")


def get_initialized_model() -> XGBRegressor:
    """
    Get an initialized XGBoost model based on the configuration.

    Returns
    -------
    XGBRegressor
        Initialized XGBoost model.
    """
    # Read the algorithm configuration.
    config = _read_configuration()

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
) -> XGBRegressor:
    """
    Train XGBoost model.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared datasets for training, validation, and testing,
        produced by ``utils.ml.prepare_split_datasets``.

    Returns
    -------
    XGBRegressor
        Trained model.
    """
    logging.info("Starting XGBoost model training.")

    # Get an initialized model.
    xgb_model = get_initialized_model()

    # Prepare evaluation set if the validation dataset is provided.
    # Its target is scaled like the training target, so that the
    # evaluation metric compares values of the same magnitude.
    eval_set = None
    if "validation" in prepared_dataset:
        eval_set = [
            (
                prepared_dataset["validation"]["features"],
                prepared_dataset["validation"]["target"] * TARGET_SCALE_FACTOR,
            )
        ]

    # Train the model on the scaled target.
    xgb_model.fit(
        prepared_dataset["training"]["features"],
        prepared_dataset["training"]["target"] * TARGET_SCALE_FACTOR,
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

        # Make predictions and return them in the units of the dataset.
        preds = xgb_model.predict(dataset["features"])
        return pd.Series(preds) / TARGET_SCALE_FACTOR

    # Initialize predictions dictionary to store training,
    # validation, and testing predictions.
    predictions: dict[str, pd.Series] = {}

    for split_name, data in prepared_dataset.items():
        # Make predictions for the current split, in the units of the
        # dataset.
        preds = xgb_model.predict(data["features"]) / TARGET_SCALE_FACTOR

        predictions[split_name] = pd.Series(preds)

        logging.info(
            f"Predictions made for {split_name} set: {len(preds)} records."
        )

    return predictions

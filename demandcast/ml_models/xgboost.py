# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains funtions to train and save an XGBoost model.
"""

import os
from typing import Optional

import pandas
import utils.config
import yaml
from pydantic import BaseModel, ValidationError
from xgboost import XGBRegressor


def _read_configuration() -> BaseModel:
    """
    Read the configuration for XGBoost model training.

    Returns
    -------
    BaseModel
        Configuration model.

    Raises
    ------
    ValueError
        If the configuration validation fails.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        random_state: int = 42
        enable_categorical: Optional[bool] = True
        evaluation_metric: Optional[str] = "mape"

    # Read the configuration.
    config_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        "xgboost.yaml",
    )

    # Read the raw configuration.
    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f)

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


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
        f"{model_name}.json",
    )

    # Save the trained model.
    xgb_model.save_model(output_path)


def train(
    prepared_dataset: dict[str, dict[str, pandas.DataFrame | pandas.Series]],
) -> XGBRegressor:
    """
    Train XGBoost model.

    Parameters
    ----------
    prepared_dataset :
        dict[str, dict[str, pandas.DataFrame | pandas.Series]]
        A dictionary containing the prepared datasets for training,
        validation, and testing.

    Returns
    -------
    XGBRegressor
        Trained model.
    """
    # Read the algorithm configuration.
    config = _read_configuration()

    # Initialize model with config parameters.
    xgb_model = XGBRegressor(
        random_state=config.random_state,
        enable_categorical=config.enable_categorical,
        eval_metric=config.evaluation_metric,
    )

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

    return xgb_model

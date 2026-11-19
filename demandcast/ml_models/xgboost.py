"""
License: AGPL-3.0.

Description:

    Train, save and load an XGBoost model that forecasts the
    electricity demand.
"""

import logging
from typing import cast, overload

import pandas as pd
from pydantic import Field
from xgboost import XGBRegressor

import ml_models.data
import utils.config

# The extension of the files of the saved models.
FILE_EXTENSION = ".json"


class ConfigModel(utils.config.StrictSettings):
    """
    Settings of the XGBoost model.

    The hyperparameters that are not given keep the defaults of
    XGBoost.
    """

    random_state: int = 42
    enable_categorical: bool | None = True
    evaluation_metric: str | None = "mape"
    early_stopping_rounds: int | None = Field(default=None, ge=1)
    n_estimators: int | None = Field(default=None, ge=1)
    max_depth: int | None = Field(default=None, ge=0)
    learning_rate: float | None = Field(default=None, gt=0)
    subsample: float | None = Field(default=None, gt=0, le=1)
    colsample_bytree: float | None = Field(default=None, gt=0, le=1)
    min_child_weight: float | None = Field(default=None, ge=0)
    reg_alpha: float | None = Field(default=None, ge=0)
    reg_lambda: float | None = Field(default=None, ge=0)


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
    hyperparameters = config.model_dump(
        exclude={
            "random_state",
            "enable_categorical",
            "evaluation_metric",
            "early_stopping_rounds",
        },
        exclude_none=True,
    )
    xgb_model = XGBRegressor(
        random_state=config.random_state,
        enable_categorical=config.enable_categorical,
        eval_metric=config.evaluation_metric,
        **hyperparameters,
    )

    logging.info("XGBoost model initialized with configuration.")

    return xgb_model


def train(
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
    config: ConfigModel,
) -> XGBRegressor:
    """
    Train XGBoost model.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared datasets for training, validation, and testing,
        produced by ``ml_models.data.prepare_split_datasets``.
    config : ConfigModel
        The settings of the model.

    Returns
    -------
    XGBRegressor
        Trained model.

    Notes
    -----
    With a validation set and early_stopping_rounds, the training stops
    adding trees once the evaluation metric of the validation set has
    not improved for that many rounds, and the model predicts with the
    trees up to its best round. Without either, the training does not
    stop early, and a validation set only leaves its year out of the
    training.
    """
    logging.info("Starting XGBoost model training.")

    xgb_model = get_initialized_model(config)

    eval_set = None
    validation = prepared_dataset.get("validation")
    if validation is not None and config.early_stopping_rounds is not None:
        eval_set = [(validation["features"], validation["target"])]
        xgb_model.set_params(
            early_stopping_rounds=config.early_stopping_rounds
        )
    elif validation is not None:
        logging.warning(
            "Without early_stopping_rounds in the settings of XGBoost, the "
            "validation set does not stop the training: its year is only "
            "left out of the training."
        )
    elif config.early_stopping_rounds is not None:
        logging.warning(
            "Without a validation set, such as in a cross-validation or "
            "with use_validation_set false, the training does not stop "
            "early: early_stopping_rounds is not used."
        )

    xgb_model.fit(
        prepared_dataset["training"]["features"],
        prepared_dataset["training"]["target"],
        eval_set=eval_set,
        verbose=False,
    )
    if eval_set is not None:
        logging.info(
            f"The training stopped at round {xgb_model.best_iteration + 1}, "
            f"the best {config.evaluation_metric} of the validation set, "
            f"{xgb_model.best_score:.4g}."
        )

    logging.info("XGBoost model training completed.")

    return xgb_model


@overload
def predict(
    xgb_model: XGBRegressor, prepared_dataset: ml_models.data.PreparedDataset
) -> pd.Series: ...


@overload
def predict(
    xgb_model: XGBRegressor,
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
) -> dict[str, pd.Series]: ...


def predict(
    xgb_model: XGBRegressor,
    prepared_dataset: ml_models.data.PreparedDataset
    | dict[str, ml_models.data.PreparedDataset],
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
        dataset = cast("ml_models.data.PreparedDataset", prepared_dataset)

        return pd.Series(xgb_model.predict(dataset["features"]))

    predictions: dict[str, pd.Series] = {}

    for split_name, data in prepared_dataset.items():
        preds = xgb_model.predict(data["features"])

        predictions[split_name] = pd.Series(preds)

        logging.info(
            f"Predictions made for {split_name} set: {len(preds)} records."
        )

    return predictions

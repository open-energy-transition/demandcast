"""
License: AGPL-3.0.

Description:

    This module lists the machine learning models and defines the
    interface that their modules provide. To add a model, write its
    module and add it to MODEL_MODULES.
"""

import importlib
from typing import Any, Protocol, cast, overload

import pandas as pd
import utils.paths
import yaml
from pydantic import BaseModel, ValidationError

import ml_models.data

# The modules of the models, by algorithm name in lower case. Each
# module is imported only when its model is used, so the LSTM needs
# PyTorch only then.
MODEL_MODULES = {
    "xgboost": "ml_models.xgboost",
    "lstm": "ml_models.lstm",
}


class ModelModule(Protocol):
    """
    The interface of the module of a machine learning model.

    The models are scikit-learn regressors that keep the names of
    their features in ``feature_names_in_``.
    """

    # The extension of the files of the saved models, such as ".json".
    FILE_EXTENSION: str

    @property
    def ConfigModel(self) -> type[BaseModel]:  # noqa: N802
        """The settings of the model, in config/<model>_config.yaml."""

    def get_initialized_model(self, config: Any) -> Any:
        """Get an untrained model, set up with its settings."""

    def train(
        self,
        prepared_dataset: dict[str, ml_models.data.PreparedDataset],
        config: Any,
    ) -> Any:
        """Train a model, with its settings, on the training set."""

    @overload
    def predict(
        self, model: Any, prepared_dataset: ml_models.data.PreparedDataset
    ) -> pd.Series: ...

    @overload
    def predict(
        self,
        model: Any,
        prepared_dataset: dict[str, ml_models.data.PreparedDataset],
    ) -> dict[str, pd.Series]: ...

    def predict(
        self,
        model: Any,
        prepared_dataset: ml_models.data.PreparedDataset
        | dict[str, ml_models.data.PreparedDataset],
    ) -> pd.Series | dict[str, pd.Series]:
        """Make predictions for one prepared dataset or several."""

    def save(self, model: Any, file_path: str) -> None:
        """Save a model to a file, with the extension of the model."""

    def load(self, model_path: str) -> Any:
        """Load a model saved by ``save``."""


def get_model_module(algorithm: str) -> ModelModule:
    """
    Get the module of a machine learning model.

    Parameters
    ----------
    algorithm : str
        The name of the algorithm, in any case, such as "XGBoost".

    Returns
    -------
    ModelModule
        The module of the model.

    Raises
    ------
    ValueError
        If the algorithm is not supported.
    """
    module_name = MODEL_MODULES.get(algorithm.lower())
    if module_name is None:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    return cast("ModelModule", importlib.import_module(module_name))


def read_model_configuration(algorithm: str) -> BaseModel:
    """
    Read the settings of a machine learning model.

    Parameters
    ----------
    algorithm : str
        The name of the algorithm, in any case, such as "XGBoost".

    Returns
    -------
    pydantic.BaseModel
        The settings of the model, from config/<algorithm>_config.yaml,
        validated by the ConfigModel of its module. An empty file gives
        the default settings.

    Raises
    ------
    ValueError
        If the settings are invalid.
    """
    config_model = get_model_module(algorithm).ConfigModel
    file_path = utils.paths.get_config_file(f"{algorithm.lower()}_config.yaml")
    with open(file_path, encoding="utf-8") as file:
        raw_config = yaml.safe_load(file)
    try:
        return config_model(**(raw_config or {}))
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e

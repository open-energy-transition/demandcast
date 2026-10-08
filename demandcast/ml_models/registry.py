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
import utils.ml

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

    def get_initialized_model(self) -> Any:
        """Get an untrained model, set up with its configuration."""

    def train(
        self, prepared_dataset: dict[str, utils.ml.PreparedDataset]
    ) -> Any:
        """Train a model on the training set of the datasets."""

    @overload
    def predict(
        self, model: Any, prepared_dataset: utils.ml.PreparedDataset
    ) -> pd.Series: ...

    @overload
    def predict(
        self, model: Any, prepared_dataset: dict[str, utils.ml.PreparedDataset]
    ) -> dict[str, pd.Series]: ...

    def predict(
        self,
        model: Any,
        prepared_dataset: utils.ml.PreparedDataset
        | dict[str, utils.ml.PreparedDataset],
    ) -> pd.Series | dict[str, pd.Series]:
        """Make predictions for one prepared dataset or several."""

    def save(self, model: Any, model_name: str) -> None:
        """Save a model to the folder of the trained models."""

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

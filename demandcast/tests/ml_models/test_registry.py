"""
License: AGPL-3.0.

Description:

    Tests for the registry of machine learning models. The contract
    test runs every model of the registry through the functions of its
    interface.
"""

import os
from typing import TYPE_CHECKING

import ml_models.registry
import ml_models.xgboost
import numpy as np
import pandas as pd
import pytest
import utils.ml
from sklearn.exceptions import NotFittedError
from sklearn.utils.validation import check_is_fitted

if TYPE_CHECKING:
    import ml_models.lstm

    def _check_interface(module: ml_models.registry.ModelModule) -> None:
        """Check with mypy that the module provides the interface."""

    _check_interface(ml_models.xgboost)
    _check_interface(ml_models.lstm)


@pytest.fixture(params=sorted(ml_models.registry.MODEL_MODULES))
def model_module(request):
    """
    Get the module of each model, skipping missing optional packages.

    Returns
    -------
    ModelModule
        The module of the model.
    """
    pytest.importorskip(
        ml_models.registry.MODEL_MODULES[request.param],
        exc_type=ModuleNotFoundError,
    )
    return ml_models.registry.get_model_module(request.param)


def _prepared_dataset() -> utils.ml.PreparedDataset:
    """
    Make a small prepared dataset of two countries.

    Returns
    -------
    PreparedDataset
        The features, target, countries and time of the dataset.
    """
    rng = np.random.default_rng(0)
    hour = np.tile(np.arange(24), 4)
    return {
        "features": pd.DataFrame(
            {
                "Local hour of the day": pd.Categorical(hour),
                "Temperature - Top 1 (K)": 285 + rng.normal(0, 3, len(hour)),
            }
        ),
        "target": pd.Series(1 + 0.2 * np.sin(2 * np.pi * hour / 24)),
        "group": pd.Series(["AUT"] * 48 + ["DNK"] * 48),
        "time": pd.Series(pd.date_range("2023-01-01", periods=96, freq="h")),
    }


def test_get_model_module():
    """Test that the name of the algorithm can be in any case."""
    assert ml_models.registry.get_model_module("XGBoost") is ml_models.xgboost


def test_get_model_module_errors():
    """Test that an unknown algorithm raises an error."""
    with pytest.raises(ValueError, match="Unsupported algorithm: Unknown"):
        ml_models.registry.get_model_module("Unknown")


def test_model_module(model_module, tmp_folders):
    """Test that the model trains, saves, loads and predicts."""
    dataset = _prepared_dataset()

    # The initialised model is not trained yet.
    with pytest.raises(NotFittedError):
        check_is_fitted(model_module.get_initialized_model())

    # The trained model is the same after saving and loading it.
    model = model_module.train({"training": dataset})
    model_module.save(model, "model")
    loaded_model = model_module.load(
        os.path.join(
            tmp_folders["trained_ml_models_folder"],
            f"model{model_module.FILE_EXTENSION}",
        )
    )
    assert (
        loaded_model.feature_names_in_.tolist()
        == dataset["features"].columns.tolist()
    )
    predictions = model_module.predict(loaded_model, dataset)
    assert len(predictions) == len(dataset["features"])
    assert predictions.tolist() == pytest.approx(
        model_module.predict(model, dataset).tolist()
    )

    # The predictions of several datasets are by dataset.
    split_predictions = model_module.predict(model, {"training": dataset})
    assert list(split_predictions) == ["training"]
    assert split_predictions["training"].tolist() == pytest.approx(
        predictions.tolist()
    )

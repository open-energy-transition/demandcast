"""
License: AGPL-3.0.

Description:

    Unit tests for the Leave-One-Group-Out cross-validation of
    cross_validate.py. The entity codes must reach both the training
    and the predictions, so that the sequences of the LSTM never cross
    the boundaries between entities.
"""

from unittest.mock import patch

import cross_validate
import ml_models.registry
import numpy as np
import pandas as pd
import pytest
import utils.ml
from pydantic import BaseModel

_ENTITIES = ["DEU", "FRA", "GBR"]
_SCORING_METRIC = "neg_mean_absolute_percentage_error"


@pytest.fixture(params=sorted(ml_models.registry.MODEL_MODULES))
def algorithm(request):
    """
    Get each algorithm, skipping missing optional packages.

    Returns
    -------
    str
        The name of the algorithm.
    """
    pytest.importorskip(
        ml_models.registry.MODEL_MODULES[request.param],
        exc_type=ModuleNotFoundError,
    )
    return request.param


def _model_config(algorithm: str) -> BaseModel:
    """
    Get the settings of a model, small for the LSTM.

    Parameters
    ----------
    algorithm : str
        The algorithm.

    Returns
    -------
    pydantic.BaseModel
        The settings, with which the LSTM trains in under a second.
    """
    config_model = ml_models.registry.get_model_module(algorithm).ConfigModel
    if algorithm.lower() == "lstm":
        return config_model(n_timesteps=4, n_units=8, epochs=1, batch_size=32)
    return config_model()


def _make_prepared_dataset() -> utils.ml.PreparedDataset:
    """
    Build a flat prepared dataset spanning three entities.

    Returns
    -------
    PreparedDataset
        The features, target and entity codes, like the output of
        ``utils.ml.prepare_dataset()``.
    """
    rng = np.random.default_rng(0)
    n_per = 20
    total = len(_ENTITIES) * n_per
    features = pd.DataFrame(
        rng.standard_normal((total, 3)), columns=["a", "b", "c"]
    )
    target = pd.Series(
        2 + features["a"] + rng.uniform(-0.1, 0.1, total), name="target"
    )
    group = pd.Series(np.repeat(_ENTITIES, n_per), name="Entity code")
    return {"features": features, "target": target, "group": group}


def test_cross_validate_returns_one_row_per_entity(algorithm):
    """Test that there is one row of MAPEs per held-out entity."""
    mapes = cross_validate._cross_validate(
        _make_prepared_dataset(),
        _SCORING_METRIC,
        1,
        algorithm,
        _model_config(algorithm),
    )

    assert mapes["Entity Code"].tolist() == _ENTITIES
    assert (mapes[["Training MAPE", "Testing MAPE"]] >= 0).all().all()


def test_cross_validate_forwards_groups(algorithm):
    """
    Test that the entity codes reach the training and the predictions.

    Regression test for the bug where sklearn's cross_validate() never
    forwarded ``groups`` into ``estimator.fit()``, so that the LSTM
    built sequences across the boundaries between entities.
    """
    model_module = ml_models.registry.get_model_module(algorithm)
    real_train, real_predict = model_module.train, model_module.predict
    training_groups: list[pd.Series] = []
    predicted_datasets: list[utils.ml.PreparedDataset] = []

    def spy_train(prepared_dataset, config):
        training_groups.append(prepared_dataset["training"]["group"])
        return real_train(prepared_dataset, config)

    def spy_predict(model, prepared_dataset):
        predicted_datasets.append(prepared_dataset)
        return real_predict(model, prepared_dataset)

    with (
        patch.object(model_module, "train", side_effect=spy_train),
        patch.object(model_module, "predict", side_effect=spy_predict),
    ):
        cross_validate._cross_validate(
            _make_prepared_dataset(),
            _SCORING_METRIC,
            1,
            algorithm,
            _model_config(algorithm),
        )

    # Each model is trained on all the entities but the held-out one.
    assert [sorted(set(group)) for group in training_groups] == [
        [entity for entity in _ENTITIES if entity != held_out]
        for held_out in _ENTITIES
    ]

    # Each prediction gets the entity codes of its own rows.
    assert len(predicted_datasets) == 2 * len(_ENTITIES)
    for dataset in predicted_datasets:
        assert dataset["group"].index.equals(dataset["features"].index)


def test_cross_validate_in_parallel():
    """Test that the results are the same with parallel folds."""
    dataset = _make_prepared_dataset()

    sequential_mapes = cross_validate._cross_validate(
        dataset, _SCORING_METRIC, 1, "XGBoost", _model_config("XGBoost")
    )
    parallel_mapes = cross_validate._cross_validate(
        dataset, _SCORING_METRIC, 2, "XGBoost", _model_config("XGBoost")
    )

    pd.testing.assert_frame_equal(parallel_mapes, sequential_mapes)

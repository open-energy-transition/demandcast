"""
License: AGPL-3.0.

Description:

    Unit tests of the evaluation of the models: the MAPE of each
    country or subdivision and of each set, and the Leave-One-Group-Out
    cross-validation, whose entity codes must reach both the training
    and the predictions, so that the sequences of the LSTM never cross
    the boundaries between entities.
"""

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from pydantic import BaseModel

import ml_models.data
import ml_models.evaluation
import ml_models.registry

_ENTITIES = ["DEU", "FRA", "GBR"]


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


def _make_prepared_dataset(
    entities: list[str] | None = None,
) -> ml_models.data.PreparedDataset:
    """
    Build a flat prepared dataset spanning several entities.

    Parameters
    ----------
    entities : list[str] | None, optional
        The entity codes, by default three countries.

    Returns
    -------
    PreparedDataset
        The features, target, entity codes and times, like the output
        of ``ml_models.data.prepare_dataset()``.
    """
    entities = entities or _ENTITIES
    rng = np.random.default_rng(0)
    n_per = 20
    total = len(entities) * n_per
    features = pd.DataFrame(
        rng.standard_normal((total, 3)), columns=["a", "b", "c"]
    )
    target = pd.Series(
        2 + features["a"] + rng.uniform(-0.1, 0.1, total), name="target"
    )
    group = pd.Series(np.repeat(entities, n_per), name="Entity code")
    time = pd.Series(
        np.tile(
            pd.date_range("2024-01-01", periods=n_per, freq="h"), len(entities)
        ),
        name="Time (UTC)",
    )
    return {
        "features": features,
        "target": target,
        "group": group,
        "time": time,
    }


def test_cross_validate_returns_one_row_per_entity(algorithm):
    """Test that there is one row of MAPEs per held-out entity."""
    mapes = ml_models.evaluation.cross_validate(
        _make_prepared_dataset(),
        1,
        algorithm,
        _model_config(algorithm),
    )

    assert mapes["Entity code"].tolist() == _ENTITIES
    assert (mapes[["Training MAPE", "Testing MAPE"]] >= 0).all().all()
    assert mapes["Holdout"].eq("entity").all()


def test_cross_validate_by_country():
    """
    Test that a country is held out with its subdivisions.

    The model scored on Argentina and its provinces is trained on Brazil
    only, and each held-out entity has its own row.
    """
    model_module = ml_models.registry.get_model_module("XGBoost")
    real_train = model_module.train
    training_groups: list[list[str]] = []

    def spy_train(prepared_dataset, config):
        training_groups.append(
            sorted(set(prepared_dataset["training"]["group"]))
        )
        return real_train(prepared_dataset, config)

    with patch.object(model_module, "train", side_effect=spy_train):
        mapes = ml_models.evaluation.cross_validate(
            _make_prepared_dataset(["ARG", "ARG_B", "ARG_C", "BRA"]),
            1,
            "XGBoost",
            _model_config("XGBoost"),
            holdout="country",
        )

    assert training_groups == [["BRA"], ["ARG", "ARG_B", "ARG_C"]]
    assert mapes["Entity code"].tolist() == ["ARG", "ARG_B", "ARG_C", "BRA"]
    assert mapes["Holdout"].eq("country").all()


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
    predicted_datasets: list[ml_models.data.PreparedDataset] = []

    def spy_train(prepared_dataset, config):
        training_groups.append(prepared_dataset["training"]["group"])
        # The other fields of the rows, such as their times, reach the
        # training, as in a validation.
        assert prepared_dataset["training"]["time"].index.equals(
            prepared_dataset["training"]["group"].index
        )
        return real_train(prepared_dataset, config)

    def spy_predict(model, prepared_dataset):
        predicted_datasets.append(prepared_dataset)
        return real_predict(model, prepared_dataset)

    with (
        patch.object(model_module, "train", side_effect=spy_train),
        patch.object(model_module, "predict", side_effect=spy_predict),
    ):
        ml_models.evaluation.cross_validate(
            _make_prepared_dataset(),
            1,
            algorithm,
            _model_config(algorithm),
        )

    # Each model is trained on all the entities but the held-out one.
    assert [sorted(set(group)) for group in training_groups] == [
        [entity for entity in _ENTITIES if entity != held_out]
        for held_out in _ENTITIES
    ]

    # Each prediction gets the entity codes and times of its own rows.
    assert len(predicted_datasets) == 2 * len(_ENTITIES)
    for dataset in predicted_datasets:
        assert dataset["group"].index.equals(dataset["features"].index)
        assert dataset["time"].index.equals(dataset["features"].index)


def test_cross_validate_in_parallel():
    """Test that the results are the same with parallel folds."""
    dataset = _make_prepared_dataset()

    sequential_mapes = ml_models.evaluation.cross_validate(
        dataset, 1, "XGBoost", _model_config("XGBoost")
    )
    parallel_mapes = ml_models.evaluation.cross_validate(
        dataset, 2, "XGBoost", _model_config("XGBoost")
    )

    pd.testing.assert_frame_equal(parallel_mapes, sequential_mapes)


def test_calculate_mape_by_entity():
    """Test that the MAPE is calculated on the rows of each entity."""
    actual = pd.Series([1.0, 2.0, 4.0, 4.0])
    predictions = pd.Series([1.1, 1.8, 4.0, 2.0])
    entity_codes = pd.Series(["FRA", "FRA", "DEU", "DEU"], name="Entity code")

    mapes = ml_models.evaluation.calculate_mape_by_entity(
        predictions, actual, entity_codes
    )

    assert mapes.index.name == "Entity code"
    assert mapes.to_dict() == pytest.approx({"DEU": 0.25, "FRA": 0.1})


def test_calculate_mapes(caplog):
    """Test that the MAPEs of each set are columns, and are logged."""
    entity_codes = pd.Series(["FRA", "DEU"], name="Entity code")
    prepared_dataset: dict[str, ml_models.data.PreparedDataset] = {
        split: {
            "features": pd.DataFrame({"a": [0.0, 0.0]}),
            "target": pd.Series([1.0, 2.0]),
            "group": entity_codes,
        }
        for split in ("training", "testing")
    }
    predictions = {
        "training": pd.Series([1.0, 1.0]),
        "testing": pd.Series([1.5, 2.0]),
    }

    with caplog.at_level("INFO"):
        mapes = ml_models.evaluation.calculate_mapes(
            prepared_dataset, predictions
        )

    assert mapes.columns.tolist() == [
        "Entity code",
        "Training MAPE",
        "Testing MAPE",
    ]
    assert mapes["Entity code"].tolist() == ["DEU", "FRA"]
    assert mapes["Training MAPE"].tolist() == pytest.approx([0.5, 0.0])
    assert mapes["Testing MAPE"].tolist() == pytest.approx([0.0, 0.5])
    assert "Testing set:" in caplog.text
    assert " - Median MAPE = 0.2500" in caplog.text


def test_calculate_mapes_of_the_profile_scaled_to_annual_totals():
    """
    Test the MAPE of the profile that forecasting gives.

    A prediction of 1.2 times a target of 1 in a complete year has a
    MAPE of 20%, but none once scaled to the annual total, as forecasts
    are. An entity without a complete year has no such MAPE.
    """
    hours = pd.date_range("2023-01-01", periods=8760, freq="h")
    group = pd.Series(["FRA"] * 8760 + ["DEU"] * 10, name="Entity code")
    prepared_dataset: dict[str, ml_models.data.PreparedDataset] = {
        "testing": {
            "features": pd.DataFrame({"a": np.zeros(8770)}),
            "target": pd.Series(np.ones(8770)),
            "group": group,
            "time": pd.Series(list(hours) + list(hours[:10])),
            "local_year": pd.Series([2023] * 8770),
        }
    }

    mapes = ml_models.evaluation.calculate_mapes(
        prepared_dataset, {"testing": pd.Series(np.full(8770, 1.2))}
    ).set_index("Entity code")

    assert mapes["Testing MAPE"].to_dict() == pytest.approx(
        {"DEU": 0.2, "FRA": 0.2}
    )
    scaled = mapes[
        "Testing MAPE of the complete years scaled to their annual totals"
    ]
    assert scaled["FRA"] == pytest.approx(0.0)
    assert np.isnan(scaled["DEU"])

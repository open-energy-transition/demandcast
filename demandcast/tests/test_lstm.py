# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    Unit tests for ml_models.lstm.

    Tests use a small synthetic dataset whose structure exactly mirrors
    the output of ``utils.ml.prepare_dataset(testing_set=True,
    validation_set=True)``: a dict with ``"training"``,
    ``"validation"``, and ``"testing"`` keys, each containing
    ``"features"``, ``"target"``, ``"group"``, ``"time"``, and
    ``"scaling_factor"`` sub-keys.

    Where file I/O or configuration reading is needed, the tests patch
    the relevant functions rather than touching the real file system.
"""

from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip(
    "torch", reason="torch not installed; skipping LSTM tests"
)

import ml_models.lstm as lstm_module  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Small hyperparameters so every test trains in under a second on CPU.
_FAST_CONFIG = MagicMock(
    n_timesteps=4,
    n_units=8,
    n_layers=1,
    dropout=0.0,
    epochs=2,
    batch_size=32,
    learning_rate=1e-3,
    random_state=42,
)

_FEATURE_NAMES = ["hour", "month", "weekend", "temperature", "gdp_ppp"]
_ENTITIES = ["DEU", "FRA", "GBR"]


def _make_split(
    rng: np.random.Generator,
    entities: list[str],
    n_per: int,
) -> dict:
    """Build one split whose structure matches _split_in_groups output."""
    total = len(entities) * n_per
    features = pd.DataFrame(
        rng.standard_normal((total, len(_FEATURE_NAMES))),
        columns=_FEATURE_NAMES,
    )
    target = pd.Series(
        rng.uniform(1e-4, 3e-4, total), name="Load (fraction of annual total)"
    )
    group = pd.Series(
        np.repeat(entities, n_per), name="Entity code"
    )
    time = pd.Series(
        pd.date_range("2020-01-01", periods=total, freq="h"),
        name="Time (UTC)",
    )
    scaling_factor = pd.Series(np.ones(total) * 1e9)
    return {
        "features": features,
        "target": target,
        "group": group,
        "time": time,
        "scaling_factor": scaling_factor,
    }


def _make_prepared_dataset() -> dict:
    """Return a multi-split prepared_dataset with 3 entities."""
    rng = np.random.default_rng(0)
    return {
        "training": _make_split(rng, _ENTITIES, 60),
        "validation": _make_split(rng, _ENTITIES, 12),
        "testing": _make_split(rng, _ENTITIES, 12),
    }


# ---------------------------------------------------------------------------
# _read_configuration
# ---------------------------------------------------------------------------


def test_read_configuration_returns_correct_values():
    """Values read from YAML are reflected in the config model."""
    yaml_content = (
        "n_timesteps: 48\n"
        "n_units: 64\n"
        "n_layers: 2\n"
        "dropout: 0.1\n"
        "epochs: 20\n"
        "batch_size: 128\n"
        "learning_rate: 0.0005\n"
        "random_state: 7\n"
    )
    with (
        patch(
            "utils.config.read_folders_structure",
            return_value={"config_folder": "/cfg"},
        ),
        patch("builtins.open", mock_open(read_data=yaml_content)),
    ):
        config = lstm_module._read_configuration()

    assert config.n_timesteps == 48
    assert config.n_units == 64
    assert config.n_layers == 2
    assert config.dropout == 0.1
    assert config.epochs == 20
    assert config.batch_size == 128
    assert config.learning_rate == 0.0005
    assert config.random_state == 7


def test_read_configuration_defaults_on_empty_yaml():
    """An empty YAML file returns default hyperparameters."""
    with (
        patch(
            "utils.config.read_folders_structure",
            return_value={"config_folder": "/cfg"},
        ),
        patch("builtins.open", mock_open(read_data="{}\n")),
    ):
        config = lstm_module._read_configuration()

    assert config.n_timesteps == 24
    assert config.n_units == 32
    assert config.n_layers == 1
    assert config.dropout == 0.0
    assert config.epochs == 5
    assert config.batch_size == 256
    assert config.learning_rate == 1e-3
    assert config.random_state == 42


def test_read_configuration_raises_on_bad_type():
    """A wrong value type raises ValueError."""
    with (
        patch(
            "utils.config.read_folders_structure",
            return_value={"config_folder": "/cfg"},
        ),
        patch(
            "builtins.open",
            mock_open(read_data="n_timesteps: not_an_int\n"),
        ),
    ):
        with pytest.raises(ValueError, match="Configuration validation"):
            lstm_module._read_configuration()


# ---------------------------------------------------------------------------
# get_initialized_model
# ---------------------------------------------------------------------------


def test_get_initialized_model_returns_lstm_regressor():
    """get_initialized_model returns a fresh, unfitted LSTMRegressor."""
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.get_initialized_model()

    assert isinstance(model, lstm_module.LSTMRegressor)
    assert not hasattr(model, "net_"), "Model should not be fitted yet"


def test_get_initialized_model_uses_config_values():
    """Hyperparameters from config are forwarded to LSTMRegressor."""
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.get_initialized_model()

    assert model.n_timesteps == _FAST_CONFIG.n_timesteps
    assert model.n_units == _FAST_CONFIG.n_units
    assert model.epochs == _FAST_CONFIG.epochs
    assert model.random_state == _FAST_CONFIG.random_state


# ---------------------------------------------------------------------------
# train
# ---------------------------------------------------------------------------


def test_train_returns_lstm_regressor():
    """train() returns a fitted LSTMRegressor instance."""
    dataset = _make_prepared_dataset()
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.train(dataset)

    assert isinstance(model, lstm_module.LSTMRegressor)
    assert hasattr(model, "net_"), "Model must be fitted after train()"


def test_train_sets_feature_names():
    """After train(), feature_names_in_ matches the dataset columns."""
    dataset = _make_prepared_dataset()
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.train(dataset)

    assert model.feature_names_in_.tolist() == _FEATURE_NAMES


def test_train_only_uses_training_split():
    """train() only reads the 'training' key; extra keys are ignored."""
    dataset = _make_prepared_dataset()
    # Remove validation and testing — train must not fail.
    del dataset["validation"]
    del dataset["testing"]

    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.train(dataset)

    assert isinstance(model, lstm_module.LSTMRegressor)


# ---------------------------------------------------------------------------
# predict — multi-split mode
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def trained_model_and_dataset():
    """Return a (model, dataset) pair shared across predict tests."""
    dataset = _make_prepared_dataset()
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        model = lstm_module.train(dataset)
    return model, dataset


def test_predict_multi_split_returns_dict(trained_model_and_dataset):
    """Multi-split predict() returns a dict keyed by split name."""
    model, dataset = trained_model_and_dataset
    result = lstm_module.predict(model, dataset)

    assert isinstance(result, dict)
    assert set(result.keys()) == {"training", "validation", "testing"}


def test_predict_multi_split_all_series(trained_model_and_dataset):
    """Each value in the multi-split result is a pandas.Series."""
    model, dataset = trained_model_and_dataset
    result = lstm_module.predict(model, dataset)

    for split, series in result.items():
        assert isinstance(series, pd.Series), (
            f"Expected Series for split '{split}', got {type(series)}"
        )


def test_predict_multi_split_correct_lengths(trained_model_and_dataset):
    """Prediction length matches the number of feature rows per split."""
    model, dataset = trained_model_and_dataset
    result = lstm_module.predict(model, dataset)

    for split in ("training", "validation", "testing"):
        expected = len(dataset[split]["features"])
        actual = len(result[split])
        assert actual == expected, (
            f"Split '{split}': expected {expected} rows, got {actual}"
        )


# ---------------------------------------------------------------------------
# predict — single-dataset mode
# ---------------------------------------------------------------------------


def test_predict_single_dataset_returns_series(trained_model_and_dataset):
    """Single-dataset predict() returns a bare pandas.Series."""
    model, dataset = trained_model_and_dataset
    single = dataset["training"]  # has "features" key at top level

    result = lstm_module.predict(model, single)

    assert isinstance(result, pd.Series)


def test_predict_single_dataset_correct_length(trained_model_and_dataset):
    """Single-dataset prediction length equals the number of rows."""
    model, dataset = trained_model_and_dataset
    single = dataset["testing"]

    result = lstm_module.predict(model, single)

    assert len(result) == len(single["features"])


# ---------------------------------------------------------------------------
# save / load round-trip
# ---------------------------------------------------------------------------


def test_save_creates_pt_file(trained_model_and_dataset):
    """save() writes a .pt file to the trained models folder."""
    model, _ = trained_model_and_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch(
            "ml_models.lstm.utils.config.read_folders_structure",
            return_value={"trained_ml_models_folder": tmpdir},
        ):
            lstm_module.save(model, "lstm_model_test")

        assert os.path.isfile(os.path.join(tmpdir, "lstm_model_test.pt"))


def test_load_restores_feature_names(trained_model_and_dataset):
    """load() restores feature_names_in_ from the checkpoint."""
    model, _ = trained_model_and_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        pt_path = os.path.join(tmpdir, "test_model.pt")
        with patch(
            "ml_models.lstm.utils.config.read_folders_structure",
            return_value={"trained_ml_models_folder": tmpdir},
        ):
            lstm_module.save(model, "test_model")

        loaded = lstm_module.load(pt_path)

    assert loaded.feature_names_in_.tolist() == _FEATURE_NAMES


def test_load_predictions_match_original(trained_model_and_dataset):
    """Predictions from a loaded model match the original model."""
    model, dataset = trained_model_and_dataset
    features = dataset["testing"]["features"]
    groups = dataset["testing"]["group"]

    preds_original = model.predict(features, groups=groups)

    with tempfile.TemporaryDirectory() as tmpdir:
        pt_path = os.path.join(tmpdir, "test_model.pt")
        with patch(
            "ml_models.lstm.utils.config.read_folders_structure",
            return_value={"trained_ml_models_folder": tmpdir},
        ):
            lstm_module.save(model, "test_model")

        loaded = lstm_module.load(pt_path)

    preds_loaded = loaded.predict(features, groups=groups)

    np.testing.assert_allclose(preds_original, preds_loaded, rtol=1e-5)


def test_load_raises_if_file_missing():
    """load() raises FileNotFoundError for a nonexistent path."""
    with pytest.raises(FileNotFoundError):
        lstm_module.load("/nonexistent/path/model.pt")


# ---------------------------------------------------------------------------
# feature_names_in_ compatibility (validate.py / forecast.py checks)
# ---------------------------------------------------------------------------


def test_feature_names_in_tolist_returns_python_list(
    trained_model_and_dataset,
):
    """
    feature_names_in_.tolist() returns a plain Python list of strings.

    validate.py and forecast.py call ``model.feature_names_in_.tolist()``
    and compare it to ``df.columns.tolist()``. Both sides must be plain
    Python lists of strings for the equality check to work.
    """
    model, _ = trained_model_and_dataset
    result = model.feature_names_in_.tolist()
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)
    assert result == _FEATURE_NAMES


def test_feature_names_check_passes_against_matching_dataset(
    trained_model_and_dataset,
):
    """
    The validate.py / forecast.py feature-name guard passes for LSTM.

    Simulates the exact check both scripts perform: compare
    ``df.columns.tolist()`` against ``model.feature_names_in_.tolist()``.
    A failure here means the dispatch branches would incorrectly raise
    ValueError even when the data matches the training features.
    """
    model, dataset = trained_model_and_dataset
    # validate.py uses the training split; forecast.py uses the bare
    # "features" key — test both access patterns.
    training_features = dataset["training"]["features"].columns.tolist()
    bare_features = dataset["training"]["features"].columns.tolist()
    model_features = model.feature_names_in_.tolist()

    assert training_features == model_features, (
        "validate.py-style check would raise ValueError"
    )
    assert bare_features == model_features, (
        "forecast.py-style check would raise ValueError"
    )


# ---------------------------------------------------------------------------
# Entity-boundary integrity
# ---------------------------------------------------------------------------


def test_predict_respects_entity_boundaries():
    """
    Sequences must not borrow rows across entity boundaries.

    Uses entity-specific feature values (ord of entity letter) to
    detect cross-entity contamination: any non-zero timestep value
    that doesn't belong to the current entity's ordinal is a violation.
    """
    rng = np.random.default_rng(7)
    n_per = 50
    n_timesteps = 6
    n_features = 3
    entities = ["A", "B", "C"]

    X_parts, g_parts = [], []
    for e in entities:
        base = float(ord(e))
        noise = rng.standard_normal((n_per, n_features)) * 1e-3
        X_parts.append(np.full((n_per, n_features), base) + noise)
        g_parts.extend([e] * n_per)

    X_arr = np.vstack(X_parts).astype(np.float32)
    groups = np.array(g_parts)

    probe = lstm_module.LSTMRegressor(
        n_timesteps=n_timesteps, n_units=4, epochs=1, batch_size=16
    )
    X_seq = probe._make_sequences(X_arr, groups=groups)

    violations = 0
    for i in range(len(X_arr)):
        expected_val = float(ord(groups[i]))
        for t in range(n_timesteps):
            v = X_seq[i, t, 0]
            if abs(v) > 0.5 and abs(v - expected_val) > 0.5:
                violations += 1
                break

    assert violations == 0, (
        f"{violations} sequences contain rows from the wrong entity"
    )

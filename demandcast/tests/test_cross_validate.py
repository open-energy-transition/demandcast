# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    Unit tests for cross_validate.py, focused on the manual
    Leave-One-Group-Out cross-validation path used for the LSTM
    algorithm (``_cross_validate_lstm``). Unlike sklearn's
    ``cross_validate()``, this path must forward ``groups`` into
    both training and prediction so that sequences never cross
    entity boundaries.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("torch", reason="torch not installed; skipping LSTM tests")

import cross_validate  # noqa: E402
import ml_models.lstm as lstm_module  # noqa: E402

# Small hyperparameters so every test trains in under a second on CPU.
_FAST_CONFIG = MagicMock(
    n_timesteps=4,
    n_units=8,
    n_layers=1,
    dropout=0.0,
    epochs=1,
    batch_size=32,
    learning_rate=1e-3,
    random_state=42,
)

_ENTITIES = ["DEU", "FRA", "GBR"]


def _make_prepared_dataset() -> dict:
    """
    Build a flat prepared_dataset spanning three entities.

    Returns
    -------
    dict
        Dict with "features", "target", and "group" keys, matching
        the output of ``utils.ml.prepare_dataset(testing_set=False,
        validation_set=False)``.
    """
    rng = np.random.default_rng(0)
    n_per = 20
    total = len(_ENTITIES) * n_per
    features = pd.DataFrame(
        rng.standard_normal((total, 3)), columns=["a", "b", "c"]
    )
    target = pd.Series(rng.uniform(1e-4, 3e-4, total), name="target")
    group = pd.Series(np.repeat(_ENTITIES, n_per), name="Entity code")
    return {"features": features, "target": target, "group": group}


def test_cross_validate_lstm_returns_one_row_per_entity():
    """One MAPE row is produced per held-out entity."""
    dataset = _make_prepared_dataset()
    with patch(
        "ml_models.lstm._read_configuration", return_value=_FAST_CONFIG
    ):
        mapes = cross_validate._cross_validate_lstm(
            dataset, "neg_mean_absolute_percentage_error"
        )

    assert sorted(mapes["Entity Code"].tolist()) == sorted(_ENTITIES)
    assert mapes["Training MAPE"].notna().all()
    assert mapes["Testing MAPE"].notna().all()


def test_cross_validate_lstm_forwards_groups_to_train():
    """
    Training folds carry group labels that exclude the held-out entity.

    Regression test for the bug where sklearn's cross_validate()
    never forwarded ``groups`` into ``estimator.fit()``, so the LSTM
    silently received ``groups=None`` and built sequences across
    country boundaries during cross-validation.
    """
    dataset = _make_prepared_dataset()
    seen_calls: list[pd.Series] = []
    real_train = lstm_module.train

    def spy_train(prepared_dataset):
        seen_calls.append(prepared_dataset["training"]["group"])
        return real_train(prepared_dataset)

    with (
        patch("ml_models.lstm._read_configuration", return_value=_FAST_CONFIG),
        patch("ml_models.lstm.train", side_effect=spy_train),
    ):
        cross_validate._cross_validate_lstm(
            dataset, "neg_mean_absolute_percentage_error"
        )

    assert len(seen_calls) == len(_ENTITIES)
    for group_arg in seen_calls:
        assert group_arg is not None
        missing_entities = set(_ENTITIES) - set(group_arg.unique())
        assert missing_entities, (
            "Training fold groups included every entity; the held-out "
            "entity was not excluded from the group labels passed to "
            "train()."
        )
        assert len(missing_entities) == 1

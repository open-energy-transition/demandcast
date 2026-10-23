"""
License: AGPL-3.0.

Description:

    Tests for the XGBoost model on a target of the real magnitude,
    converted by ml_models.data to the load relative to the annual mean
    (issue #145).
"""

from typing import cast

import ml_models.data
import ml_models.registry
import ml_models.xgboost
import numpy as np
import pandas as pd


def _prepared_dataset() -> ml_models.data.PreparedDataset:
    """
    Make a dataset whose target is prepared like the real one.

    The load is a daily cycle plus a response to temperature, as a
    fraction of the annual total of about 1/8760 like the real target,
    and converted to the load relative to the annual mean like
    ml_models.data.prepare_dataset does. A model has to split on both
    features to fit it.

    Returns
    -------
    PreparedDataset
        The features, target, countries, time and local years of the
        dataset.
    """
    rng = np.random.default_rng(0)
    hour = np.tile(np.arange(24), 40)
    temperature = 285 + rng.normal(0, 3, len(hour))
    load_fraction = pd.Series(
        (
            1
            + 0.2 * np.sin(2 * np.pi * hour / 24)
            + 0.005 * np.abs(temperature - 288)
        )
        / 8760
    )
    local_year = pd.Series([2023] * len(hour))
    return {
        "features": pd.DataFrame(
            {
                "Local hour of the day": pd.Categorical(hour),
                "Temperature - Top 1 (K)": temperature,
            }
        ),
        "target": ml_models.data.to_load_relative_to_annual_mean(
            load_fraction, local_year
        ),
        "group": pd.Series(["AUT"] * 480 + ["DNK"] * 480),
        "time": pd.Series(pd.date_range("2023-01-01", periods=960, freq="h")),
        "local_year": local_year,
    }


def test_train_splits_on_the_prepared_target():
    """Test that the model splits on the prepared target."""
    dataset = _prepared_dataset()

    model = ml_models.xgboost.train(
        {"training": dataset},
        cast(
            ml_models.xgboost.ConfigModel,
            ml_models.registry.read_model_configuration("xgboost"),
        ),
    )
    trees = model.get_booster().trees_to_dataframe()
    splits = trees[trees["Feature"] != "Leaf"]

    # The model splits, and on both features. On the fraction of the
    # annual total itself, about 1/8760, nearly every tree is a single
    # leaf (issue #145).
    assert set(splits["Feature"]) == set(dataset["features"].columns)

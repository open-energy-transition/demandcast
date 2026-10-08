"""
License: AGPL-3.0.

Description:

    Tests for the XGBoost model, and in particular for the scaling of
    the target that lets the model split on it (issue #145).
"""

import ml_models.xgboost
import numpy as np
import pandas as pd
import utils.ml

# The order of magnitude of the real target, "Load (fraction of annual
# total)": one hour out of the hours of a year.
AVERAGE_HOUR = 1 / 8760


def _prepared_dataset() -> utils.ml.PreparedDataset:
    """
    Make a dataset whose target has the magnitude of the real one.

    The target is a daily cycle plus a response to temperature, around
    the fraction of the annual load of an average hour, so that a
    model has to split on both features to fit it.

    Returns
    -------
    PreparedDataset
        The features, target, countries and time of the dataset.
    """
    rng = np.random.default_rng(0)
    hour = np.tile(np.arange(24), 40)
    temperature = 285 + rng.normal(0, 3, len(hour))
    return {
        "features": pd.DataFrame(
            {
                "Local hour of the day": pd.Categorical(hour),
                "Temperature - Top 1 (K)": temperature,
            }
        ),
        "target": pd.Series(
            AVERAGE_HOUR
            * (
                1
                + 0.2 * np.sin(2 * np.pi * hour / 24)
                + 0.005 * np.abs(temperature - 288)
            )
        ),
        "group": pd.Series(["AUT"] * 480 + ["DNK"] * 480),
        "time": pd.Series(pd.date_range("2023-01-01", periods=960, freq="h")),
    }


def test_train_splits_on_a_small_target():
    """Test that the model splits on a target of about 1/8760."""
    dataset = _prepared_dataset()

    model = ml_models.xgboost.train({"training": dataset})
    trees = model.get_booster().trees_to_dataframe()
    splits = trees[trees["Feature"] != "Leaf"]

    # The model splits, and on both features. Without the scaling of
    # the target, every tree of this dataset is a single leaf and the
    # model splits on nothing at all.
    assert set(splits["Feature"]) == set(dataset["features"].columns)


def test_predict_returns_the_units_of_the_target():
    """Test that the predictions are in the units of the target."""
    dataset = _prepared_dataset()

    model = ml_models.xgboost.train({"training": dataset})
    predictions = ml_models.xgboost.predict(model, dataset)

    # The predictions follow the target. If predict() did not invert
    # the scaling of train(), they would be about 8760 times larger.
    target = dataset["target"].to_numpy()
    mape = np.abs((predictions.to_numpy() - target) / target).mean()
    assert mape < 0.01

"""
License: AGPL-3.0.

Description:

    This module contains functions to train and save an LSTM model
    for electricity demand forecasting. The ``LSTMRegressor`` wrapper
    implements the sklearn estimator interface, enabling direct use
    with ``cross_validate()`` and ``LeaveOneGroupOut()``.

    Sequence construction respects entity boundaries and time gaps:
    rows from different entities (identified by the ``"group"`` column
    of the prepared dataset), or separated by more or less than an hour
    (by the ``"time"`` column), never share a lookback window, which is
    padded with zeros instead. The windows are built batch by batch,
    so that the windows of all the rows are never in memory at once.

    The features are standardized with the mean and standard deviation
    of each feature in the training rows, which are saved with the
    model: features of different magnitudes, such as the GDP per capita
    and the temperature, would otherwise saturate the gates of the
    LSTM. The categorical features, such as the hour of the day, are
    standardized as the ordinal numbers that they are.
"""

from __future__ import annotations

import logging
import os
from typing import cast, overload

# isort: off
# torch must be imported before pandas — pandas side-effects corrupt
# the Windows DLL loader state for torch's c10.dll initialisation.
import ml_models.torch_windows

ml_models.torch_windows.enable_torch_dll_directory()
import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402
import pandas as pd  # noqa: E402

# isort: on
from pydantic import Field  # noqa: E402
from sklearn.base import BaseEstimator, RegressorMixin  # noqa: E402
from sklearn.utils.validation import check_is_fitted  # noqa: E402

import ml_models.data  # noqa: E402
import utils.config  # noqa: E402

# The extension of the files of the saved models.
FILE_EXTENSION = ".pt"

# ----------------------------------------------------------------------
# Private PyTorch network
# ----------------------------------------------------------------------


class _LSTMNet(nn.Module):
    """Stacked LSTM with a single linear output layer."""

    def __init__(
        self,
        n_features: int,
        n_units: int,
        n_layers: int,
        dropout: float,
    ) -> None:
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=n_units,
            num_layers=n_layers,
            batch_first=True,
            # Dropout is applied between layers only; ignored for
            # single-layer networks.
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.fc = nn.Linear(n_units, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute a forward pass.

        Parameters
        ----------
        x : torch.Tensor
            Shape ``(batch, n_timesteps, n_features)``.

        Returns
        -------
        torch.Tensor
            Shape ``(batch,)`` — one scalar per sample.
        """
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :]).squeeze(-1)


# ----------------------------------------------------------------------
# sklearn-compatible wrapper
# ----------------------------------------------------------------------


class LSTMRegressor(BaseEstimator, RegressorMixin):
    """
    LSTM regressor with an sklearn-compatible interface.

    Uses a PyTorch ``nn.LSTM`` backend. Compatible with
    ``sklearn.model_selection.cross_validate`` and
    ``LeaveOneGroupOut``.

    Parameters
    ----------
    n_timesteps : int
        Lookback window length. Zero-padding (or group-boundary
        padding when ``groups`` is supplied) ensures that every
        sample maps to exactly one prediction.
    n_units : int
        LSTM hidden units per layer.
    n_layers : int
        Number of stacked LSTM layers.
    dropout : float
        Dropout rate between LSTM layers (meaningful only when
        ``n_layers > 1``).
    epochs : int
        Training epochs over the full dataset.
    batch_size : int
        Mini-batch size used for training and inference.
    learning_rate : float
        Adam optimiser learning rate.
    random_state : int
        Seed passed to ``torch.manual_seed`` for reproducibility.
    """

    def __init__(
        self,
        n_timesteps: int = 24,
        n_units: int = 32,
        n_layers: int = 1,
        dropout: float = 0.0,
        epochs: int = 5,
        batch_size: int = 256,
        learning_rate: float = 1e-3,
        random_state: int = 42,
    ) -> None:
        # sklearn convention: store constructor args unchanged.
        self.n_timesteps = n_timesteps
        self.n_units = n_units
        self.n_layers = n_layers
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.random_state = random_state

    # ------------------------------------------------------------------
    # Sequence construction
    # ------------------------------------------------------------------

    @staticmethod
    def _get_run_starts(
        n_samples: int,
        groups: pd.Series | np.ndarray | None = None,
        times: pd.Series | np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Get the first row of the run of consecutive hours of each row.

        A run starts at the first row, at each change of entity, and at
        each row that is not one hour after the row before it.

        Parameters
        ----------
        n_samples : int
            The number of rows.
        groups : pandas.Series or np.ndarray or None
            Entity label per row.
        times : pandas.Series or np.ndarray or None
            Time per row.

        Returns
        -------
        np.ndarray
            The position of the first row of the run of each row.
        """
        starts = np.zeros(n_samples, dtype=bool)
        if n_samples:
            starts[0] = True
        if groups is not None:
            labels = np.asarray(groups)
            starts[1:] |= labels[1:] != labels[:-1]
        if times is not None:
            steps = np.diff(pd.DatetimeIndex(times).to_numpy())
            starts[1:] |= steps != np.timedelta64(1, "h")
        return np.maximum.accumulate(np.where(starts, np.arange(n_samples), 0))

    def _make_sequences(
        self,
        X: np.ndarray,
        run_starts: np.ndarray,
        rows: np.ndarray,
    ) -> np.ndarray:
        """
        Build the ``(len(rows), n_timesteps, n_features)`` windows.

        The window of a row has the rows of its run before it, at most
        ``n_timesteps - 1``, and zeros before them.

        Parameters
        ----------
        X : np.ndarray
            Shape ``(n_samples, n_features)``.
        run_starts : np.ndarray
            The first row of the run of each row.
        rows : np.ndarray
            The positions of the rows whose windows are built.

        Returns
        -------
        np.ndarray
            Shape ``(len(rows), n_timesteps, n_features)``.
        """
        offsets = np.arange(-self.n_timesteps + 1, 1)
        positions = rows[:, None] + offsets[None, :]
        valid = positions >= run_starts[rows][:, None]
        windows = X[np.where(valid, positions, 0)]
        windows[~valid] = 0.0
        return windows

    def _standardize(self, X: pd.DataFrame | np.ndarray) -> np.ndarray:
        """
        Standardize the features with the statistics of the training.

        Parameters
        ----------
        X : pandas.DataFrame or np.ndarray of shape \
(n_samples, n_features)
            The features.

        Returns
        -------
        np.ndarray
            The standardized features, as float32.
        """
        X_arr = np.array(X, dtype=np.float32)
        return ((X_arr - self.mean_) / self.scale_).astype(np.float32)

    # ------------------------------------------------------------------
    # sklearn estimator interface
    # ------------------------------------------------------------------

    def fit(
        self,
        X: pd.DataFrame | np.ndarray,
        y: pd.Series | np.ndarray,
        groups: pd.Series | np.ndarray | None = None,
        times: pd.Series | np.ndarray | None = None,
    ) -> LSTMRegressor:
        """
        Fit the LSTM model.

        Parameters
        ----------
        X : pandas.DataFrame or np.ndarray of shape \
(n_samples, n_features)
            Training features. Column names are stored in
            ``feature_names_in_`` when X is a DataFrame.
        y : pandas.Series or np.ndarray of shape (n_samples,)
            Target values.
        groups : array-like of shape (n_samples,), optional
            Entity labels per row. When supplied, sequences are
            built without crossing group boundaries.
        times : array-like of shape (n_samples,), optional
            Time per row. When supplied, sequences are built without
            crossing the gaps between rows that are not an hour apart.

        Returns
        -------
        LSTMRegressor
            This estimator.
        """
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())

        X_raw = np.array(X, dtype=np.float32)
        self.n_features_in_ = X_raw.shape[1]
        self.mean_ = X_raw.mean(axis=0)
        # A constant feature keeps its values, shifted to zero.
        standard_deviation = X_raw.std(axis=0)
        self.scale_ = np.where(standard_deviation > 0, standard_deviation, 1)
        X_arr = self._standardize(X_raw)
        y_tensor = torch.from_numpy(np.array(y, dtype=np.float32).ravel())
        run_starts = self._get_run_starts(len(X_arr), groups, times)

        torch.manual_seed(self.random_state)
        self.net_ = _LSTMNet(
            self.n_features_in_,
            self.n_units,
            self.n_layers,
            self.dropout,
        )
        optimizer = torch.optim.Adam(
            self.net_.parameters(), lr=self.learning_rate
        )
        criterion = nn.MSELoss()
        generator = torch.Generator().manual_seed(self.random_state)

        self.net_.train()
        for _ in range(self.epochs):
            order = torch.randperm(len(X_arr), generator=generator).numpy()
            for i in range(0, len(order), self.batch_size):
                rows = order[i : i + self.batch_size]
                X_batch = torch.from_numpy(
                    self._make_sequences(X_arr, run_starts, rows)
                )
                optimizer.zero_grad()
                loss = criterion(self.net_(X_batch), y_tensor[rows])
                loss.backward()
                optimizer.step()

        self.net_.eval()
        return self

    def predict(
        self,
        X: pd.DataFrame | np.ndarray,
        groups: pd.Series | np.ndarray | None = None,
        times: pd.Series | np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Predict with the trained LSTM.

        Parameters
        ----------
        X : pandas.DataFrame or np.ndarray of shape \
(n_samples, n_features)
            Input features.
        groups : array-like of shape (n_samples,), optional
            Entity labels. Pass the same groups used in ``fit`` to
            apply entity-boundary padding during inference.
        times : array-like of shape (n_samples,), optional
            Time per row, to break the sequences at the gaps.

        Returns
        -------
        np.ndarray
            Shape ``(n_samples,)`` — one prediction per row.
        """
        check_is_fitted(self, "net_")

        X_arr = self._standardize(X)
        run_starts = self._get_run_starts(len(X_arr), groups, times)

        self.net_.eval()
        parts: list[np.ndarray] = [np.empty(0, dtype=np.float32)]
        with torch.no_grad():
            for i in range(0, len(X_arr), self.batch_size):
                rows = np.arange(i, min(i + self.batch_size, len(X_arr)))
                batch = torch.from_numpy(
                    self._make_sequences(X_arr, run_starts, rows)
                )
                parts.append(self.net_(batch).numpy())
        return np.concatenate(parts).flatten()

    # get_params() and set_params() are inherited from BaseEstimator.


# ----------------------------------------------------------------------
# Module-level API  (mirrors ml_models/xgboost.py)
# ----------------------------------------------------------------------


class ConfigModel(utils.config.StrictSettings):
    """Settings of the LSTM model."""

    n_timesteps: int = Field(default=24, ge=1)
    n_units: int = Field(default=32, ge=1)
    n_layers: int = Field(default=1, ge=1)
    dropout: float = Field(default=0.0, ge=0, lt=1)
    epochs: int = Field(default=5, ge=1)
    batch_size: int = Field(default=256, ge=1)
    learning_rate: float = Field(default=1e-3, gt=0)
    random_state: int = 42


def load(model_path: str) -> LSTMRegressor:
    """
    Load a trained LSTM model from a checkpoint file.

    Parameters
    ----------
    model_path : str
        Path to a ``.pt`` checkpoint created by :func:`save`.

    Returns
    -------
    LSTMRegressor
        Fitted LSTM model ready for inference.

    Raises
    ------
    FileNotFoundError
        If ``model_path`` does not exist.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    checkpoint = torch.load(model_path, weights_only=True)

    lstm_model = LSTMRegressor(**checkpoint["params"])
    lstm_model.n_features_in_ = checkpoint["n_features_in_"]
    # A model saved before the features were standardized has no
    # statistics, and takes the features as they are.
    if "mean_" not in checkpoint:
        logging.warning(
            f"The model {model_path} has no statistics of its features, "
            "which are not standardized."
        )
    lstm_model.mean_ = np.array(
        checkpoint.get("mean_", [0.0] * lstm_model.n_features_in_),
        dtype=np.float32,
    )
    lstm_model.scale_ = np.array(
        checkpoint.get("scale_", [1.0] * lstm_model.n_features_in_),
        dtype=np.float32,
    )

    if "feature_names_in_" in checkpoint:
        lstm_model.feature_names_in_ = np.array(
            checkpoint["feature_names_in_"]
        )

    lstm_model.net_ = _LSTMNet(
        lstm_model.n_features_in_,
        lstm_model.n_units,
        lstm_model.n_layers,
        lstm_model.dropout,
    )
    lstm_model.net_.load_state_dict(checkpoint["state_dict"])
    lstm_model.net_.eval()

    logging.info(f"Trained model loaded from {model_path}")

    return lstm_model


def save(lstm_model: LSTMRegressor, file_path: str) -> None:
    """
    Save a trained LSTM model to a checkpoint file.

    Parameters
    ----------
    lstm_model : LSTMRegressor
        Fitted LSTM model to serialise.
    file_path : str
        The path of the file, with the extension FILE_EXTENSION.
    """
    output_path = file_path

    checkpoint: dict = {
        "params": lstm_model.get_params(),
        "n_features_in_": int(lstm_model.n_features_in_),
        "mean_": lstm_model.mean_.tolist(),
        "scale_": lstm_model.scale_.tolist(),
        "state_dict": lstm_model.net_.state_dict(),
    }
    if hasattr(lstm_model, "feature_names_in_"):
        checkpoint["feature_names_in_"] = lstm_model.feature_names_in_.tolist()

    torch.save(checkpoint, output_path)

    logging.info(f"Trained model saved to {output_path}")


def get_initialized_model(config: ConfigModel) -> LSTMRegressor:
    """
    Return an LSTM model initialised from its settings.

    Parameters
    ----------
    config : ConfigModel
        The settings of the model.

    Returns
    -------
    LSTMRegressor
        Un-fitted LSTM regressor with config-derived hyperparameters.
    """
    lstm_model = LSTMRegressor(
        n_timesteps=config.n_timesteps,
        n_units=config.n_units,
        n_layers=config.n_layers,
        dropout=config.dropout,
        epochs=config.epochs,
        batch_size=config.batch_size,
        learning_rate=config.learning_rate,
        random_state=config.random_state,
    )

    logging.info("LSTM model initialised with configuration.")

    return lstm_model


def train(
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
    config: ConfigModel,
) -> LSTMRegressor:
    """
    Train an LSTM model on the prepared dataset.

    Only the ``"training"`` split is used to fit the model. Group
    labels from ``prepared_dataset["training"]["group"]`` are passed
    to ``fit()`` so that sequences never cross entity boundaries.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        Datasets produced by
        ``ml_models.data.prepare_split_datasets`` with at least a
        ``"training"`` key containing ``"features"``, ``"target"``, and
        ``"group"`` sub-keys.
    config : ConfigModel
        The settings of the model.

    Returns
    -------
    LSTMRegressor
        Fitted LSTM model.
    """
    logging.info("Starting LSTM model training.")

    lstm_model = get_initialized_model(config)

    training = prepared_dataset["training"]
    lstm_model.fit(
        training["features"],
        training["target"],
        groups=training.get("group"),
        times=training.get("time"),
    )

    logging.info("LSTM model training completed.")

    return lstm_model


@overload
def predict(
    lstm_model: LSTMRegressor, prepared_dataset: ml_models.data.PreparedDataset
) -> pd.Series: ...


@overload
def predict(
    lstm_model: LSTMRegressor,
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
) -> dict[str, pd.Series]: ...


def predict(
    lstm_model: LSTMRegressor,
    prepared_dataset: ml_models.data.PreparedDataset
    | dict[str, ml_models.data.PreparedDataset],
) -> pd.Series | dict[str, pd.Series]:
    """
    Make predictions with a trained LSTM model.

    Supports two calling modes:

    *Single-dataset mode*: ``prepared_dataset`` contains a
    ``"features"`` key at the top level (no train/val/test split).
    Returns a bare ``pandas.Series``.

    *Multi-split mode*: ``prepared_dataset`` contains
    ``"training"``, ``"validation"``, and/or ``"testing"`` keys,
    each with their own ``"features"`` and ``"group"`` sub-keys.
    Returns a ``dict`` mapping split name to ``pandas.Series``.

    Parameters
    ----------
    lstm_model : LSTMRegressor
        Fitted LSTM model.
    prepared_dataset : PreparedDataset | dict[str, PreparedDataset]
        Dataset produced by ``ml_models.data.prepare_dataset``, or
        datasets produced by
        ``ml_models.data.prepare_split_datasets``.

    Returns
    -------
    pandas.Series or dict[str, pandas.Series]
        Predictions in single-dataset or multi-split mode
        respectively.
    """
    logging.info("Making predictions with the trained LSTM model.")

    if "features" in prepared_dataset:
        dataset = cast("ml_models.data.PreparedDataset", prepared_dataset)
        preds = lstm_model.predict(
            dataset["features"],
            groups=dataset.get("group"),
            times=dataset.get("time"),
        )
        return pd.Series(preds)

    predictions: dict[str, pd.Series] = {}
    for split_name, data in prepared_dataset.items():
        preds = lstm_model.predict(
            data["features"],
            groups=data.get("group"),
            times=data.get("time"),
        )
        predictions[split_name] = pd.Series(preds)
        logging.info(
            f"Predictions made for {split_name} set: {len(preds)} records."
        )
    return predictions

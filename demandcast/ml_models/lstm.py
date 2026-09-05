# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module contains functions to train and save an LSTM model
    for electricity demand forecasting. The ``LSTMRegressor`` wrapper
    implements the sklearn estimator interface, enabling direct use
    with ``cross_validate()`` and ``LeaveOneGroupOut()``.

    Sequence construction respects entity boundaries: rows from
    different entities (identified by the ``"group"`` column of the
    prepared dataset) never share a lookback window.
"""

from __future__ import annotations

import logging
import os

# isort: off
# torch must be imported before pandas — pandas side-effects corrupt
# the Windows DLL loader state for torch's c10.dll initialisation.
import utils.torch_windows  # noqa: E402

_dll_dir_tokens = utils.torch_windows.enable_torch_dll_directory()
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import pandas  # noqa: E402

# isort: on
import utils.config  # noqa: E402
import yaml  # noqa: E402
from pydantic import BaseModel, ValidationError  # noqa: E402
from sklearn.base import BaseEstimator, RegressorMixin  # noqa: E402
from sklearn.utils.validation import check_is_fitted  # noqa: E402

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

    def _make_sequences(
        self,
        X: np.ndarray,
        groups: np.ndarray | None = None,
    ) -> np.ndarray:
        """
        Build ``(n_samples, n_timesteps, n_features)`` sequences.

        Without groups, prepends ``n_timesteps - 1`` zero rows so
        every sample maps to exactly one output. With groups, sequences
        never cross entity boundaries: zero-padding is inserted at the
        start of each new contiguous run instead of borrowing rows from
        the preceding entity.

        Parameters
        ----------
        X : np.ndarray
            Shape ``(n_samples, n_features)``.
        groups : np.ndarray or None
            Entity label per row. Only contiguous run boundaries are
            treated as entity boundaries; non-contiguous recurrence of
            a label starts a fresh run.

        Returns
        -------
        np.ndarray
            Shape ``(n_samples, n_timesteps, n_features)``.
        """
        n_samples, n_features = X.shape

        if groups is None:
            pad = np.zeros((self.n_timesteps - 1, n_features), dtype=X.dtype)
            X_padded = np.concatenate([pad, X], axis=0)
            idx = (
                np.arange(n_samples)[:, None]
                + np.arange(self.n_timesteps)[None, :]
            )
            return X_padded[idx]

        groups = np.asarray(groups)
        run_start = np.empty(n_samples, dtype=int)
        run_start[0] = 0
        for i in range(1, n_samples):
            run_start[i] = (
                i if groups[i] != groups[i - 1] else run_start[i - 1]
            )

        X_seq = np.zeros(
            (n_samples, self.n_timesteps, n_features), dtype=X.dtype
        )
        # Builds one row at a time: fine for the current 3-country
        # benchmark, but may be worth vectorizing for full-scale
        # datasets with 40+ countries.
        for i in range(n_samples):
            window_start = max(run_start[i], i - self.n_timesteps + 1)
            n_valid = i - window_start + 1
            X_seq[i, self.n_timesteps - n_valid :] = X[window_start : i + 1]
        return X_seq

    # ------------------------------------------------------------------
    # sklearn estimator interface
    # ------------------------------------------------------------------

    def fit(
        self,
        X: pandas.DataFrame | np.ndarray,
        y: pandas.Series | np.ndarray,
        groups: pandas.Series | np.ndarray | None = None,
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

        Returns
        -------
        LSTMRegressor
            This estimator.
        """
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns.tolist())

        X_arr = np.array(X, dtype=np.float32)
        y_arr = np.array(y, dtype=np.float32).ravel()
        self.n_features_in_ = X_arr.shape[1]

        groups_arr = np.asarray(groups) if groups is not None else None
        X_seq = self._make_sequences(X_arr, groups_arr)

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

        dataset = torch.utils.data.TensorDataset(
            torch.from_numpy(X_seq), torch.from_numpy(y_arr)
        )
        loader = torch.utils.data.DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.random_state),
        )

        self.net_.train()
        for _ in range(self.epochs):
            for X_batch, y_batch in loader:
                optimizer.zero_grad()
                loss = criterion(self.net_(X_batch), y_batch)
                loss.backward()
                optimizer.step()

        self.net_.eval()
        return self

    def predict(
        self,
        X: pandas.DataFrame | np.ndarray,
        groups: pandas.Series | np.ndarray | None = None,
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

        Returns
        -------
        np.ndarray
            Shape ``(n_samples,)`` — one prediction per row.
        """
        check_is_fitted(self, "net_")

        X_arr = np.array(X, dtype=np.float32)
        groups_arr = np.asarray(groups) if groups is not None else None
        X_seq = self._make_sequences(X_arr, groups_arr)
        X_tensor = torch.from_numpy(X_seq)

        self.net_.eval()
        parts: list[np.ndarray] = []
        with torch.no_grad():
            for i in range(0, len(X_tensor), self.batch_size):
                batch = X_tensor[i : i + self.batch_size]
                parts.append(self.net_(batch).numpy())
        return np.concatenate(parts).flatten()

    # get_params() and set_params() are inherited from BaseEstimator.


# ----------------------------------------------------------------------
# Module-level API  (mirrors ml_models/xgboost.py)
# ----------------------------------------------------------------------


def _read_configuration() -> BaseModel:
    """
    Read and validate the LSTM configuration file.

    Returns
    -------
    BaseModel
        Validated configuration model with all LSTM hyperparameters.

    Raises
    ------
    ValueError
        If the configuration file contains invalid values.
    """

    class ConfigModel(BaseModel):
        n_timesteps: int = 24
        n_units: int = 32
        n_layers: int = 1
        dropout: float = 0.0
        epochs: int = 5
        batch_size: int = 256
        learning_rate: float = 1e-3
        random_state: int = 42

    config_path = os.path.join(
        utils.config.read_folders_structure()["config_folder"],
        "lstm_config.yaml",
    )

    with open(config_path, "r") as f:
        raw_config = yaml.safe_load(f)

    try:
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


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


def save(lstm_model: LSTMRegressor, model_name: str) -> None:
    """
    Save a trained LSTM model to the trained models folder.

    Parameters
    ----------
    lstm_model : LSTMRegressor
        Fitted LSTM model to serialise.
    model_name : str
        File stem for the output file (the ``.pt`` extension is
        appended automatically).
    """
    model_folder = utils.config.read_folders_structure()[
        "trained_ml_models_folder"
    ]
    os.makedirs(model_folder, exist_ok=True)

    output_path = os.path.join(model_folder, f"{model_name}.pt")

    checkpoint: dict = {
        "params": lstm_model.get_params(),
        "n_features_in_": int(lstm_model.n_features_in_),
        "state_dict": lstm_model.net_.state_dict(),
    }
    if hasattr(lstm_model, "feature_names_in_"):
        checkpoint["feature_names_in_"] = lstm_model.feature_names_in_.tolist()

    torch.save(checkpoint, output_path)

    logging.info(f"Trained model saved to {output_path}")


def get_initialized_model() -> LSTMRegressor:
    """
    Return an LSTM model initialised from the YAML configuration.

    Returns
    -------
    LSTMRegressor
        Un-fitted LSTM regressor with config-derived hyperparameters.
    """
    config = _read_configuration()

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
    prepared_dataset: dict[str, dict[str, pandas.DataFrame | pandas.Series]],
) -> LSTMRegressor:
    """
    Train an LSTM model on the prepared dataset.

    Only the ``"training"`` split is used to fit the model. Group
    labels from ``prepared_dataset["training"]["group"]`` are passed
    to ``fit()`` so that sequences never cross entity boundaries.

    Parameters
    ----------
    prepared_dataset :
        dict[str, dict[str, pandas.DataFrame | pandas.Series]]
        Dataset produced by ``utils.ml.prepare_dataset`` with at
        least a ``"training"`` key containing ``"features"``,
        ``"target"``, and ``"group"`` sub-keys.

    Returns
    -------
    LSTMRegressor
        Fitted LSTM model.
    """
    logging.info("Starting LSTM model training.")

    lstm_model = get_initialized_model()

    training = prepared_dataset["training"]
    lstm_model.fit(
        training["features"],
        training["target"],
        groups=training.get("group"),
    )

    logging.info("LSTM model training completed.")

    return lstm_model


def predict(
    lstm_model: LSTMRegressor,
    prepared_dataset: dict[
        str,
        pandas.Series
        | pandas.DataFrame
        | dict[str, pandas.DataFrame | pandas.Series],
    ],
) -> pandas.Series | dict[str, pandas.Series]:
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
    prepared_dataset :
        dict[str, pandas.Series | pandas.DataFrame |
        dict[str, pandas.DataFrame | pandas.Series]]
        Dataset produced by ``utils.ml.prepare_dataset``.

    Returns
    -------
    pandas.Series or dict[str, pandas.Series]
        Predictions in single-dataset or multi-split mode
        respectively.
    """
    logging.info("Making predictions with the trained LSTM model.")

    if "features" in prepared_dataset:
        preds = lstm_model.predict(
            prepared_dataset["features"],
            groups=prepared_dataset.get("group"),
        )
        return pandas.Series(preds)

    predictions: dict[str, pandas.Series] = {}
    for split_name, data in prepared_dataset.items():
        preds = lstm_model.predict(
            data["features"],
            groups=data.get("group"),
        )
        predictions[split_name] = pandas.Series(preds)
        logging.info(
            f"Predictions made for {split_name} set: {len(preds)} records."
        )
    return predictions

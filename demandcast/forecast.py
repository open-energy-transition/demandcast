"""
License: AGPL-3.0.

Description:

    This script produces forecasts using a trained machine learning
    model and input features, saving the predictions to a specified
    output file.
"""

import logging
import os

import ml_models.xgboost
import pandas as pd
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError


class ConfigModel(BaseModel):
    """Settings of forecast.py."""

    model_path: str | None = None
    data_path: str | None = None


def _read_and_check_configuration() -> ConfigModel:
    """
    Read and check the configuration for forecasting.

    Returns
    -------
    config : ConfigModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """
    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "forecast",
        "Produce forecasts using the specified preprocessed data "
        "and trained model.",
    )

    # Validate the configuration.
    try:
        config = ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e

    logging.info("Configuration validated successfully:")
    for field, value in config.model_dump().items():
        logging.info(f" - {field}: {value}")

    return config


def _construct_output_dataset(
    prepared_dataset: utils.ml.PreparedDataset,
    predictions: pd.Series,
) -> pd.DataFrame:
    """
    Construct the output dataset containing forecasts.

    Parameters
    ----------
    prepared_dataset : PreparedDataset
        The prepared dataset containing features and other relevant
        data.
    predictions : pandas.Series
        The predicted values from the model.

    Returns
    -------
    output_dataset : pandas.DataFrame
        The output dataset with forecasts.
    """
    # Scale the predictions to MW using the annual electricity demand
    # per capita (kWh) and population.
    predictions = predictions * prepared_dataset["scaling_factor"] / 1000

    # Construct the output dataset.
    columns: list[pd.Series | pd.DataFrame] = [
        prepared_dataset["time"],
        prepared_dataset["group"],
        prepared_dataset["features"],
    ]
    if "others" in prepared_dataset:
        columns.append(prepared_dataset["others"])
    columns.append(predictions.rename("Forecast load (MW)"))

    return pd.concat(columns, axis=1)


def run_forecasting(
    model_path: str | None,
    data_path: str | None,
    algorithm: str,
) -> None:
    """
    Run the model forecasting process.

    Parameters
    ----------
    model_path : str | None
        The path to the trained model file. If None, the latest file
        in the default directory will be used.
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.
    algorithm : str
        The machine learning algorithm to use for validation.

    Raises
    ------
    ValueError
        If an unsupported algorithm is specified or if there is a
        mismatch between model features and data features.
    """
    logging.info("Starting model validation process.")

    # Get the assembled data path.
    data_path = utils.ml.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(data_path, target=False)

    if algorithm.lower() == "xgboost":
        # Get the trained model path.
        trained_model_path = utils.ml.get_trained_model_path(
            model_path, algorithm.lower()
        )

        # Load the trained model.
        model = ml_models.xgboost.load(trained_model_path)

        # Check that the model was trained with the same features of the
        # prepared dataset.
        data_features = prepared_dataset["features"].columns.tolist()
        model_features = model.feature_names_in_.tolist()
        if data_features != model_features:
            raise ValueError(
                "The features used in the prepared dataset do not match "
                "those used during model training."
            )

        # Make predictions.
        predictions = ml_models.xgboost.predict(model, prepared_dataset)

        logging.info("Forecasting completed successfully.")

    elif algorithm.lower() == "lstm":
        # The LSTM model needs the optional lstm extra.
        from ml_models import lstm  # noqa: PLC0415

        # Get the trained model path.
        trained_model_path = utils.ml.get_trained_model_path(
            model_path, algorithm.lower(), extension=".pt"
        )

        # Load the trained model.
        model = lstm.load(trained_model_path)

        # Check that the model was trained with the same features of the
        # prepared dataset.
        data_features = prepared_dataset["features"].columns.tolist()
        model_features = model.feature_names_in_.tolist()
        if data_features != model_features:
            raise ValueError(
                "The features used in the prepared dataset do not match "
                "those used during model training."
            )

        # Make predictions.
        predictions = lstm.predict(model, prepared_dataset)

        logging.info("Forecasting completed successfully.")

    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    # Construct the output dataset.
    output_dataset = _construct_output_dataset(
        prepared_dataset,
        predictions,
    )

    # Save the output dataset.
    utils.ml.save_results(
        "forecasts",
        output_dataset,
        os.path.basename(trained_model_path).split(".")[0],
        os.path.basename(data_path).split(".")[0],
        "all",
    )


if __name__ == "__main__":
    # Set up the logging configuration.
    utils.config.set_up_logging("model_validation")

    # Read and check the configuration.
    config = _read_and_check_configuration()

    # Read and check machine learning configuration.
    ml_config = utils.ml.read_and_check_ml_configuration()

    # Run the forecasting process.
    run_forecasting(
        config.model_path,
        config.data_path,
        ml_config.algorithm,
    )

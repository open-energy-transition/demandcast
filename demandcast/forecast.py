"""
License: AGPL-3.0.

Description:

    This script produces forecasts using a trained machine learning
    model and input features, saving the predictions to a specified
    output file.
"""

import logging
import os

import ml_models.registry
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
        The machine learning algorithm to use for forecasting.
    """
    logging.info("Starting model forecasting process.")

    # Get the module of the model.
    model_module = ml_models.registry.get_model_module(algorithm)

    # Get the assembled data path.
    data_path = utils.ml.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = utils.ml.prepare_dataset(data_path, target=False)

    # Load the trained model, and check that it was trained with the
    # features of the prepared dataset.
    trained_model_path = utils.ml.get_trained_model_path(
        model_path, algorithm.lower(), model_module.FILE_EXTENSION
    )
    model = model_module.load(trained_model_path)
    utils.ml.check_model_features(model, prepared_dataset["features"])

    # Make predictions.
    predictions = model_module.predict(model, prepared_dataset)
    logging.info("Forecasting completed successfully.")

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
    utils.config.set_up_logging("model_forecasting")

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

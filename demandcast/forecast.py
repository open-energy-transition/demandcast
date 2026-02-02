# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script produces forecasts using a trained machine learning
    model and input features, saving the predictions to a specified
    output file.
"""

import logging
import os
from typing import Optional

import ml_models.xgboost
import pandas
import utils.config
import utils.ml
from pydantic import BaseModel, ValidationError


def _read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for forecasting.

    Returns
    -------
    config : BaseModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        model_path: Optional[str] = None
        data_path: Optional[str] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        "forecast",
        "Produce forecasts using the specified preprocessed data "
        "and trained model.",
    )

    try:
        # Validate the configuration.
        config = ConfigModel(**raw_config)

        logging.info("Configuration validated successfully:")
        for field, value in config.model_dump().items():
            logging.info(f" - {field}: {value}")

        return config
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


def _construct_output_dataset(
    prepared_dataset: dict[str, pandas.Series | pandas.DataFrame],
    predictions: pandas.Series,
) -> pandas.DataFrame:
    """
    Construct the output dataset containing forecasts.

    Parameters
    ----------
    prepared_dataset : dict[str, pandas.Series | pandas.DataFrame]
        The prepared dataset containing features and other relevant
        data.
    predictions : pandas.Series
        The predicted values from the model.

    Returns
    -------
    output_dataset : pandas.DataFrame
        The output dataset with forecasts.
    """
    # Scale the prodictions to MW using the annual electricity demand
    # per capita (kWh) and population.
    predictions = predictions * prepared_dataset["scaling_factor"] / 1000

    # Construct the output dataset.
    output_dataset = prepared_dataset["time"].copy()
    output_dataset = pandas.concat(
        [output_dataset, prepared_dataset["group"]], axis=1
    )
    output_dataset = pandas.concat(
        [output_dataset, prepared_dataset["features"]], axis=1
    )
    if "others" in prepared_dataset:
        output_dataset = pandas.concat(
            [output_dataset, prepared_dataset["others"]], axis=1
        )
    output_dataset = pandas.concat(
        [output_dataset, predictions.rename("Forecast load (MW)")], axis=1
    )

    return output_dataset


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
    prepared_dataset: dict[str, pandas.Series | pandas.DataFrame] = (
        utils.ml.prepare_dataset(
            data_path,
            False,
            False,
            False,
        )
    )

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

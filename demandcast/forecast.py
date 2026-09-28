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
import pandas as pd
import numpy as np


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


def _normalize_predictions(
    raw_predictions: pandas.Series,
    entity_codes: pandas.Series,
    local_years: pandas.Series,
) -> pandas.Series:
    """
    Normalize the predictions for each entity and local year.

    The predicted fractions of each entity are rescaled so that they sum
    to the share of the hours of the local year that are in the dataset,
    which is 1.0 for a complete year. This is the same definition as the
    load fraction used as target during training (see assemble.py), and
    it avoids assigning the energy of a whole year to a partial year.

    Parameters
    ----------
    raw_predictions : pandas.Series
        The predicted load fractions from the model.
    entity_codes : pandas.Series
        The entity code of each prediction.
    local_years : pandas.Series
        The local year of each prediction.

    Returns
    -------
    pandas.Series
        The normalized load fractions, with the same index as the raw
        predictions.
    """
    logging.info(
        "Normalizing the predictions so that the hourly fractions of each "
        "entity sum to 1.0 over each local year."
    )

    # Group the predictions by entity and local year.
    keys = [
        np.asarray(entity_codes),
        np.asarray(local_years).astype(int),
    ]
    groups = raw_predictions.groupby(keys)

    # Get the share of the hours of each local year in the dataset.
    years = keys[1]
    is_leap_year = (years % 4 == 0) & ((years % 100 != 0) | (years % 400 == 0))
    hours_in_year = np.where(is_leap_year, 8784, 8760)
    share_of_hours = groups.transform("count") / hours_in_year

    return raw_predictions / groups.transform("sum") * share_of_hours


def _construct_output_dataset(
    prepared_dataset: dict[str, pandas.Series | pandas.DataFrame],
    raw_predictions: pandas.Series,
    normalized_predictions: pandas.Series
) -> pandas.DataFrame:
    """
    Construct the output dataset containing forecasts.

    Parameters
    ----------
    prepared_dataset : dict[str, pandas.Series | pandas.DataFrame]
        The prepared dataset containing features and other relevant
        data.
    raw_predictions : pandas.Series
        The predicted values from the model, before normalization.
    normalized_predictions: pandas.Series 
        The normalized values, such that the sum of them equals to 1 for each local year

    Returns
    -------
    output_dataset : pandas.DataFrame
        The output dataset with forecasts.
    """
    # Scale the normalized predictions to MW using the annual electricity
    # demand per capita (kWh) and population, so that the hourly load of
    # each entity adds up to its annual demand.
    forecasted_demand = (
        normalized_predictions * prepared_dataset["scaling_factor"] / 1000
    )

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
        [output_dataset, raw_predictions.rename("Raw forecast load fraction (%)")], axis=1
    )

    output_dataset = pandas.concat(
       [output_dataset, normalized_predictions.rename("Normalized forecast load fraction (%)")], axis=1
    )

    output_dataset = pandas.concat(
        [output_dataset, forecasted_demand.rename('Forecast Load (MW)')],axis= 1
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
        raw_predictions = ml_models.xgboost.predict(model, prepared_dataset)

        # Normalize the predictions so that the hourly fractions of each
        # entity sum to 1.0 over each local year. This prevents the model
        # from predicting more or less than 100% of the annual demand.
        normalized_predictions = _normalize_predictions(
            raw_predictions,
            prepared_dataset["group"],
            prepared_dataset["others"]["Local year"],
        )
        logging.info("Forecasting completed successfully.")

    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    # Construct the output dataset.
    #output_dataset = _construct_output_dataset(
    #    prepared_dataset,
    #    predictions,
    #)

    # Construct the output dataset 
    output_dataset = _construct_output_dataset(
        prepared_dataset,
        raw_predictions,
        normalized_predictions,
    )

    # Save the output dataset.
    utils.ml.save_results(
        "forecasts",
        output_dataset,
        os.path.basename(trained_model_path).split(".")[0],
        os.path.basename(data_path).split(".")[0],
        "all_raw_normalized",
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

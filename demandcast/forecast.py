"""
License: AGPL-3.0.

Description:

    This script produces forecasts using a trained machine learning
    model and input features, saving the predictions to a specified
    output file.
"""

import logging
import os

import ml_models.data
import ml_models.files
import ml_models.registry
import pandas as pd
import utils.config
from pydantic import BaseModel


class ConfigModel(BaseModel):
    """Settings of forecast.py."""

    model_path: str | None = None
    data_path: str | None = None


def _construct_output_dataset(
    prepared_dataset: ml_models.data.PreparedDataset,
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
    # Convert the predictions from the load relative to the annual mean
    # to MW.
    predictions = ml_models.data.to_megawatts(
        predictions,
        prepared_dataset["local_year"],
        prepared_dataset["scaling_factor"],
    )

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
    ml_config: ml_models.data.ConfigModel,
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
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models, with the
        algorithm.
    """
    logging.info("Starting model forecasting process.")

    # Get the module of the model.
    algorithm = ml_config.algorithm
    model_module = ml_models.registry.get_model_module(algorithm)

    # Get the assembled data path.
    data_path = ml_models.files.get_assemble_data_path(data_path)

    # Read and prepare the dataset.
    prepared_dataset = ml_models.data.prepare_dataset(
        data_path, ml_config, target=False
    )

    # Load the trained model, and check that it was trained with the
    # features of the prepared dataset.
    trained_model_path = ml_models.files.get_trained_model_path(
        model_path, algorithm.lower(), model_module.FILE_EXTENSION
    )
    model = model_module.load(trained_model_path)
    ml_models.data.check_model_features(model, prepared_dataset["features"])

    # Make predictions.
    predictions = model_module.predict(model, prepared_dataset)
    logging.info("Forecasting completed successfully.")

    # Construct the output dataset.
    output_dataset = _construct_output_dataset(
        prepared_dataset,
        predictions,
    )

    # Save the output dataset.
    ml_models.files.save_results(
        "forecasts",
        output_dataset,
        os.path.basename(trained_model_path).split(".")[0],
        os.path.basename(data_path).split(".")[0],
        "all",
    )


def main(config: ConfigModel) -> None:
    """
    Forecast with the model of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("model_forecasting")
    utils.config.log_configuration(config)

    # Read and check machine learning configuration.
    ml_config = ml_models.data.read_and_check_ml_configuration()

    run_forecasting(
        config.model_path,
        config.data_path,
        ml_config,
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "forecast",
            ConfigModel,
            "Produce forecasts using the specified preprocessed data and "
            "trained model.",
        )
    )

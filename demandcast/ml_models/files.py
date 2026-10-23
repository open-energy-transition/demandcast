"""
License: AGPL-3.0.

Description:

    This module finds and writes the files of the machine learning
    models: the latest trained model of an algorithm and the latest
    assembled data, unless a path is given, and the results of the
    validation, cross-validation and forecasts, in CSV and Parquet
    files named after the model, the data and the time.
"""

import logging
import os
from typing import Literal

import pandas as pd
import utils.paths


def _get_latest_file(folder: str, prefix: str, extension: str) -> str | None:
    """
    Get the latest file of a folder by the time in its name.

    The names of the files end with the time of their creation, in the
    format YYYYMMDD_HHMMSS, before the extension.

    Parameters
    ----------
    folder : str
        The folder to search.
    prefix : str
        The start of the names of the files.
    extension : str
        The extension of the files, such as ".parquet".

    Returns
    -------
    latest_path : str | None
        The path of the latest file, or None if there is no file.
    """
    latest_path = None
    latest_time = "00000000_000000"
    for file_name in os.listdir(folder):
        time = file_name[-len(latest_time) - len(extension) : -len(extension)]
        if (
            file_name.startswith(prefix)
            and file_name.endswith(extension)
            and time > latest_time
        ):
            latest_time = time
            latest_path = os.path.join(folder, file_name)

    return latest_path


def get_trained_model_path(
    model_path: str | None,
    algorithm_name: str,
    extension: str = ".json",
) -> str:
    """
    Get the path to the trained model file.

    Parameters
    ----------
    model_path : str | None
        The path to the trained model file. If None, the latest file
        in the default directory will be used.
    algorithm_name : str
        The name of the machine learning algorithm.
    extension : str, optional
        File extension of the saved model, e.g. ``".json"`` for
        XGBoost or ``".pt"`` for LSTM. Defaults to ``".json"``.

    Returns
    -------
    model_path : str
        The path to the trained model file.

    Raises
    ------
    FileNotFoundError
        If no trained model files are found.
    """
    # Get the folder containing trained model files.
    trained_models_folder = utils.paths.get_models_folder(algorithm_name)

    # If no model path is provided, find the latest trained model file.
    if model_path is None:
        model_path = _get_latest_file(
            trained_models_folder, f"{algorithm_name}_model", extension
        )
        if model_path is None:
            raise FileNotFoundError(
                f"No trained model files found in '{trained_models_folder}'."
            )

    logging.info(f"Using trained model file: {model_path}")

    return model_path


def get_assemble_data_path(data_path: str | None) -> str:
    """
    Get the path to the assembled data file.

    Parameters
    ----------
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        in the default directory will be used.

    Returns
    -------
    data_path : str
        The path to the assembled data file.

    Raises
    ------
    FileNotFoundError
        If no assembled data files are found.
    """
    # Get the folder containing assembled data files.
    assembled_data_folder = utils.paths.get_assembled_folder()

    # If no data path is provided, find the latest assembled data file.
    if data_path is None:
        data_path = _get_latest_file(
            assembled_data_folder, "assembled_data", ".parquet"
        )
        if data_path is None:
            raise FileNotFoundError(
                f"No assembled data files found in '{assembled_data_folder}'."
            )

    logging.info(f"Using assembled data file: {data_path}")

    return data_path


def save_results(
    case: Literal["validation", "cross_validation", "forecasts"],
    output_dataset: pd.DataFrame,
    trained_model_name: str,
    assembled_data_file_name: str,
    file_name_prefix: str,
) -> None:
    """
    Save the model results to CSV and Parquet files.

    Parameters
    ----------
    output_dataset : pandas.DataFrame
        The dataset containing the model results to save.
    trained_model_name : str
        The name of the trained model used for obtaining the results.
    case : str
        The case of the results.

    Raises
    ------
    ValueError
        If the case is invalid.
    """
    # Check that the case is valid.
    if case not in ["validation", "cross_validation", "forecasts"]:
        raise ValueError(f"Invalid case: {case}")

    # Determine the content type for logging.
    output_dataset_content = "MAPEs" if "validation" in case else "forecasts"

    logging.info(f"Saving model {output_dataset_content}.")

    # Get the folder where to save the model results.
    results_folder = utils.paths.get_results_folder(case)

    # Construct the model results folder path.
    model_results_folder = os.path.join(
        results_folder,
        f"with_{trained_model_name}",
        f"using_{assembled_data_file_name}",
    )
    os.makedirs(model_results_folder, exist_ok=True)

    # Construct the results file name.
    results_file_name = os.path.join(
        model_results_folder,
        f"{file_name_prefix}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}",
    )

    # Save the results to CSV and Parquet files.
    output_dataset.to_csv(results_file_name + ".csv", index=False)
    output_dataset.to_parquet(results_file_name + ".parquet", index=False)

    logging.info(
        f"Model {case} saved to {results_file_name}.csv and "
        f"{results_file_name}.parquet"
    )

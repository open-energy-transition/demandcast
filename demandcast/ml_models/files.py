"""
License: AGPL-3.0.

Description:

    This module finds and writes the files of the machine learning
    models: the latest trained model of an algorithm and the latest
    assembled data, unless a path is given, and the results of the
    validation, cross-validation and forecasts, in CSV and Parquet
    files named after the model, the data and the time.

    Each trained model and each result has a manifest (see
    utils/manifest.py). That of a model records its dataset and its
    checksum, its settings, its features in their order, its target and
    its transformation, the statistics of its fitted preprocessing, and
    the countries and subdivisions and local years of each of its sets.
    A validation reads the dataset of the model by default, and stops
    if the dataset, the target or the sets differ from those of the
    training; a forecast stops if the target differs. That of a result
    records its model and dataset, and the metric of the errors.
"""

import logging
import os
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel

import ml_models.data
import utils.manifest
import utils.paths

# The metric of the errors of the validations and cross-validations.
METRIC = {
    "name": "MAPE",
    "description": "mean absolute percentage error, as a fraction",
    "direction": "lower is better",
    "of": ml_models.data.TARGET_TRANSFORMATION,
}


def _get_latest_file(folder: str, prefix: str, extension: str) -> str | None:
    """
    Get the latest file of a folder by the time in its name.

    The names of the files end with the time of their creation, in the
    format YYYYMMDD_HHMMSS, before the extension. The manifests of the
    files are not files of the folder.

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
            and not file_name.endswith(utils.manifest.MANIFEST_EXTENSION)
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


def get_assemble_data_path(
    data_path: str | None,
    target_use: Literal["training", "forecasting"] = "training",
) -> str:
    """
    Get the path to the assembled data file.

    Parameters
    ----------
    data_path : str | None
        The path to the assembled data file. If None, the latest file
        assembled for the use in the default directory will be used.
    target_use : str, optional
        The use of the assembled data, "training" or "forecasting".

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
            assembled_data_folder,
            f"assembled_data_for_{target_use}_",
            ".parquet",
        )
        if data_path is None:
            raise FileNotFoundError(
                f"No data assembled for {target_use} found in "
                f"'{assembled_data_folder}'."
            )

    logging.info(f"Using assembled data file: {data_path}")

    return data_path


def save_results(
    case: Literal["validation", "cross_validation", "forecasts"],
    output_dataset: pd.DataFrame,
    trained_model_name: str,
    assembled_data_file_name: str,
    file_name_prefix: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Save the model results to CSV and Parquet files, with a manifest.

    Parameters
    ----------
    output_dataset : pandas.DataFrame
        The dataset containing the model results to save.
    trained_model_name : str
        The name of the trained model used for obtaining the results.
    case : str
        The case of the results.
    assembled_data_file_name : str
        The name of the assembled data, without its extension.
    file_name_prefix : str
        The start of the names of the files.
    extra : dict[str, Any] | None, optional
        What else the manifest of the results tells, such as the
        holdout of a cross-validation.

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

    # Save the results to CSV and Parquet files, with the manifest of
    # their model, data and metric.
    output_dataset.to_csv(results_file_name + ".csv", index=False)
    output_dataset.to_parquet(results_file_name + ".parquet", index=False)
    utils.manifest.write_manifest(
        results_file_name + ".parquet",
        "results",
        {
            "case": case,
            "model": trained_model_name,
            "dataset": assembled_data_file_name,
            "columns": [str(column) for column in output_dataset.columns],
            **(
                {"metric": METRIC}
                if "validation" in case
                else {
                    "units": "MW",
                    "annual_totals": (
                        "the forecasts of each complete year sum to its "
                        "annual demand"
                    ),
                }
            ),
            **(extra or {}),
        },
    )

    logging.info(
        f"Model {case} saved to {results_file_name}.csv and "
        f"{results_file_name}.parquet"
    )


def get_split_membership(
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
) -> dict[str, list[list[Any]]]:
    """
    Get the countries and subdivisions and local years of each set.

    Parameters
    ----------
    prepared_dataset : dict[str, PreparedDataset]
        The prepared dataset of each set.

    Returns
    -------
    dict[str, list[list[Any]]]
        The sorted pairs of entity code and local year of each set.
    """
    return {
        name: sorted(
            [str(code), int(year)]
            for code, year in set(
                zip(split["group"], split["local_year"], strict=True)
            )
        )
        for name, split in prepared_dataset.items()
    }


def write_model_manifest(
    model_path: str,
    model: Any,
    data_path: str,
    prepared_dataset: dict[str, ml_models.data.PreparedDataset],
    ml_config: ml_models.data.ConfigModel,
    model_config: BaseModel,
) -> str:
    """
    Write the manifest of a trained model.

    Parameters
    ----------
    model_path : str
        The path of the saved model.
    model : Any
        The trained model, with the statistics of its standardization
        of the features in ``mean_`` and ``scale_``, if any.
    data_path : str
        The path of the assembled data of the training.
    prepared_dataset : dict[str, PreparedDataset]
        The prepared dataset of each set.
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models.
    model_config : pydantic.BaseModel
        The settings of the model of the algorithm.

    Returns
    -------
    str
        The path of the manifest.
    """
    features = prepared_dataset["training"]["features"]
    preprocessing: dict[str, Any] = {}
    if hasattr(model, "mean_"):
        preprocessing = {
            "standardization": {
                "mean": [float(value) for value in model.mean_],
                "scale": [float(value) for value in model.scale_],
            }
        }
    return utils.manifest.write_manifest(
        model_path,
        "model",
        {
            "algorithm": ml_config.algorithm,
            "dataset": {
                "path": os.path.abspath(data_path),
                "sha256": utils.manifest.get_checksum(data_path),
            },
            "ml_settings": ml_config.model_dump(),
            "model_settings": model_config.model_dump(),
            "features": [
                {"name": str(name), "dtype": str(dtype)}
                for name, dtype in features.dtypes.items()
            ],
            "target": {
                "column": ml_config.target,
                "transformation": ml_models.data.TARGET_TRANSFORMATION,
            },
            "preprocessing": preprocessing,
            "splits": get_split_membership(prepared_dataset),
        },
    )


def check_model_manifest(
    manifest: dict[str, Any] | None,
    ml_config: ml_models.data.ConfigModel,
    data_path: str | None = None,
    prepared_dataset: dict[str, ml_models.data.PreparedDataset] | None = None,
) -> None:
    """
    Check that a model is used as it was trained.

    Parameters
    ----------
    manifest : dict[str, Any] | None
        The manifest of the model, None for a model trained before the
        manifests, which is not checked.
    ml_config : ml_models.data.ConfigModel
        The settings of the machine learning models.
    data_path : str | None, optional
        The path of the assembled data of a validation, which must be
        that of the training.
    prepared_dataset : dict[str, PreparedDataset] | None, optional
        The prepared dataset of each set of a validation, whose sets
        must be those of the training.

    Raises
    ------
    ValueError
        If the target, its transformation, the dataset or the sets
        differ from those of the training.
    """
    if manifest is None:
        logging.warning(
            "The model has no manifest, so its training cannot be checked."
        )
        return
    target = manifest["target"]
    if (target["column"], target["transformation"]) != (
        ml_config.target,
        ml_models.data.TARGET_TRANSFORMATION,
    ):
        raise ValueError(
            f"The model was trained on the target {target['column']} as "
            f"the {target['transformation']}, not on {ml_config.target} as "
            f"the {ml_models.data.TARGET_TRANSFORMATION}."
        )
    if data_path is not None and (
        utils.manifest.get_checksum(data_path) != manifest["dataset"]["sha256"]
    ):
        raise ValueError(
            f"The data {data_path} is not the data of the training of the "
            f"model, {manifest['dataset']['path']}."
        )
    if prepared_dataset is not None:
        membership = get_split_membership(prepared_dataset)
        if any(
            membership[name] != manifest["splits"].get(name)
            for name in membership
        ):
            raise ValueError(
                "The sets of the validation differ from those of the "
                "training of the model: check used_validation_set."
            )


def get_validation_data_path(
    data_path: str | None, manifest: dict[str, Any] | None
) -> str:
    """
    Get the assembled data of a validation.

    Parameters
    ----------
    data_path : str | None
        The path given, if any.
    manifest : dict[str, Any] | None
        The manifest of the model.

    Returns
    -------
    str
        The path given, or the data of the training of the model, or
        the latest data assembled for training for a model without
        manifest.
    """
    if data_path is None and manifest is not None:
        data_path = manifest["dataset"]["path"]
        logging.info(
            f"Using the data of the training of the model: {data_path}"
        )
        return data_path
    return get_assemble_data_path(data_path)

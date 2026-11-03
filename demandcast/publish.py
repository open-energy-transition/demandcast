"""
License: AGPL-3.0.

Description:

    This script uploads a release of DemandCast to Zenodo: the trained
    model, its settings and its forecasts, as a draft new version of a
    record, or of a new record, to check and publish on the website of
    Zenodo (see publishing.zenodo). The manifest of each file (see
    utils/manifest.py), which tells how the model was trained and which
    model and data gave the forecasts, is uploaded with it, and so is
    the README of the release (publishing/release/README.md), with the
    sources, licences and attributions of the data and how to replicate
    the results.

    A release with forecasts also has their compact file
    (COMPACT_FORECASTS_FILE), made from them at the upload, with the
    time, the code and the forecast of each hour of each country and
    subdivision, without the inputs of the model. It has the name and
    the columns of the file of the first release of DemandCast, which
    PyPSA-Earth downloads.

    A release cannot have the electricity demand, whose redistribution
    the licences of many data sources do not allow: the files of the
    electricity demand, the assembled data for training and the
    predictions of the validations and cross-validations, which have
    the actual demand of their hours, stop the release before anything
    is uploaded.
"""

import logging
import os
import tempfile

import pandas as pd
from pydantic import field_validator

import publishing.zenodo
import utils.config
import utils.manifest
import utils.paths

# The README of the releases.
README_FILE = os.path.join(
    os.path.dirname(publishing.zenodo.__file__), "release", "README.md"
)

# The starts of the names of the files with the electricity demand.
DEMAND_FILE_PREFIXES = ("assembled_data_for_training_", "predictions_")

# The compact file of the forecasts, and its columns.
COMPACT_FORECASTS_FILE = "forecasts_on_historical_period.parquet"
COMPACT_FORECASTS_COLUMNS = ["Time (UTC)", "Entity code", "Forecast load (MW)"]


class ConfigModel(utils.config.StrictSettings):
    """Settings of publish.py."""

    zenodo_record: int | str | None
    version: str
    files: list[str]
    metadata_file: str = "oet_zenodo_metadata.yaml"
    sandbox: bool = False

    @field_validator("zenodo_record")
    @classmethod
    def _check_record(cls, record: int | str | None) -> int | str:
        """
        Check that the record is a number or "new".

        Parameters
        ----------
        record : int | str | None
            The record.

        Returns
        -------
        int | str
            The record.

        Raises
        ------
        ValueError
            If the record is missing, or neither a number nor "new".
        """
        if record is None or (isinstance(record, str) and record != "new"):
            raise ValueError(
                "The zenodo_record must be the number of a version of your "
                "record on Zenodo, as in https://zenodo.org/records/<number>, "
                "or 'new' to create a record."
            )
        return record

    @field_validator("files")
    @classmethod
    def _check_files(cls, files: list[str]) -> list[str]:
        """
        Check that files are given.

        Parameters
        ----------
        files : list[str]
            The files of the release.

        Returns
        -------
        list[str]
            The files.

        Raises
        ------
        ValueError
            If no file is given.
        """
        if not files:
            raise ValueError(
                "The files of the release must be given: the trained "
                "model, its settings and its forecasts."
            )
        return files


def _check_publishable(file_paths: list[str]) -> None:
    """
    Check that no file of a release has the electricity demand.

    Parameters
    ----------
    file_paths : list[str]
        The paths of the files.

    Raises
    ------
    ValueError
        If a file is in the folder of the electricity demand, or is the
        assembled data for training or predictions of scored hours,
        with their actual demand.
    """
    demand_folder = os.path.realpath(
        utils.paths.get_data_folder("electricity_demand")
    )
    for file_path in file_paths:
        in_demand_folder = (
            os.path.commonpath([os.path.realpath(file_path), demand_folder])
            == demand_folder
        )
        if in_demand_folder or os.path.basename(file_path).startswith(
            DEMAND_FILE_PREFIXES
        ):
            raise ValueError(
                f"The file {file_path} has the electricity demand, whose "
                "redistribution the licences of many data sources do not "
                "allow, so it cannot be in a release."
            )


def _with_manifests(file_paths: list[str]) -> list[str]:
    """
    Add the manifests of the files of a release, after checking them.

    Each file with a manifest is checked against it (see
    utils.manifest.verify_file), and each manifest is added once, even
    for the CSV and Parquet files of the same results, which share it.
    The results whose model is not the model of the release, if the
    release has one, stop the release before anything is uploaded.

    Parameters
    ----------
    file_paths : list[str]
        The paths of the files.

    Returns
    -------
    list[str]
        The paths of the files, each followed by that of its manifest,
        if it has one and it is not already in the release.

    Raises
    ------
    ValueError
        If a file differs from its manifest, or results are not those of
        the model of the release.
    """
    with_manifests: list[str] = []
    manifests: dict[str, dict] = {}
    for file_path in file_paths:
        if file_path not in with_manifests:
            with_manifests.append(file_path)
        if file_path.endswith(utils.manifest.MANIFEST_EXTENSION):
            continue
        manifest = utils.manifest.verify_file(file_path, None)
        if manifest is None:
            logging.warning(f"The file {file_path} has no manifest.")
            continue
        manifest_path = utils.manifest.get_manifest_path(file_path)
        manifests[file_path] = manifest
        if manifest_path not in with_manifests:
            with_manifests.append(manifest_path)

    # The results must be those of the model of the release.
    models = {
        manifest["sha256"]
        for manifest in manifests.values()
        if manifest["kind"] == "model"
    }
    for file_path, manifest in manifests.items():
        model = manifest.get("model")
        if (
            models
            and manifest["kind"] == "results"
            and isinstance(model, dict)
            and model.get("sha256")
            and model["sha256"] not in models
        ):
            raise ValueError(
                f"The results {file_path} are not those of the model of the "
                "release."
            )
    return with_manifests


def _write_compact_forecasts(file_paths: list[str], folder: str) -> list[str]:
    """
    Write the compact file of the forecasts of a release.

    Parameters
    ----------
    file_paths : list[str]
        The paths of the files of the release.
    folder : str
        The folder where to write the compact file.

    Returns
    -------
    list[str]
        The path of the compact file, or none if the
        release has no forecasts in a Parquet file.

    Raises
    ------
    ValueError
        If the release has the forecasts of several Parquet files.
    """
    forecasts = []
    for file_path in file_paths:
        if not file_path.endswith(".parquet"):
            continue
        manifest = utils.manifest.read_manifest(file_path)
        if (
            manifest is not None
            and manifest["kind"] == "results"
            and manifest.get("case") == "forecasts"
        ):
            forecasts.append(file_path)
    if not forecasts:
        return []
    if len(forecasts) > 1:
        raise ValueError(
            f"The release has several files of forecasts: {forecasts}."
        )

    file_path = os.path.join(folder, COMPACT_FORECASTS_FILE)
    pd.read_parquet(
        forecasts[0], columns=COMPACT_FORECASTS_COLUMNS
    ).to_parquet(file_path, index=False)
    logging.info(f"The forecasts of {forecasts[0]} are in {file_path}.")
    return [file_path]


def main(config: ConfigModel) -> None:
    """
    Upload the release of the settings to Zenodo.

    The paths of the files are relative to the data folder, unless they
    are absolute.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("publication")
    utils.config.log_configuration(config)

    file_paths = [
        os.path.join(utils.paths.get_data_folder(), file_path)
        for file_path in config.files
    ]
    _check_publishable(file_paths)
    release_files = _with_manifests(file_paths)
    with tempfile.TemporaryDirectory() as folder:
        publishing.zenodo.publish_release(
            [
                *release_files,
                *_write_compact_forecasts(file_paths, folder),
                README_FILE,
            ],
            config.version,
            # The settings check that the record is a number or "new".
            config.zenodo_record
            if isinstance(config.zenodo_record, int)
            else None,
            config.metadata_file,
            config.sandbox,
        )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "publish",
            ConfigModel,
            "Upload a release of DemandCast to Zenodo as a draft.",
        )
    )

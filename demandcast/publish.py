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

    The forecasts are uploaded as their compact file
    (COMPACT_FORECASTS_FILE), made from them at the upload, with the
    name and the columns of the file of the first release of
    DemandCast, which PyPSA-Earth downloads.

    A release cannot have the electricity demand, whose redistribution
    the licences of many data sources do not allow: the files of the
    electricity demand, the assembled data for training and the
    predictions of the validations and cross-validations, which have
    the actual demand of their hours, stop the release before anything
    is uploaded.
"""

import logging
import os
import re
import tempfile
import zipfile

import pandas as pd
from pydantic import Field, field_validator

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
    folders: dict[str, list[str]] = Field(default_factory=dict)
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

    @field_validator("folders")
    @classmethod
    def _check_folders(
        cls, folders: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        """
        Check that each folder has a simple name and files.

        Parameters
        ----------
        folders : dict[str, list[str]]
            The files of each folder of the release.

        Returns
        -------
        dict[str, list[str]]
            The folders.

        Raises
        ------
        ValueError
            If a name has other characters than letters, digits, "_" and
            "-", or a folder has no file.
        """
        for name, files in folders.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
                raise ValueError(
                    f"The name of the folder {name!r} must have only "
                    "letters, digits, '_' and '-'."
                )
            if not files:
                raise ValueError(f"The folder {name} has no file.")
        return folders


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


def _use_compact_forecasts(file_paths: list[str], folder: str) -> list[str]:
    """
    Replace the forecasts of a release with their compact file.

    The compact file has the time, the code and the forecast of each
    hour of each country and subdivision, without the inputs of the
    model, which the assembled data for forecasting has. Its manifest
    has the model, the data and the units of the forecasts, and the
    name, checksum and code version of the forecasts that it comes
    from, after they are checked against their manifest.

    Parameters
    ----------
    file_paths : list[str]
        The paths of the files of the release.
    folder : str
        The folder where to write the compact file and its manifest.

    Returns
    -------
    list[str]
        The paths of the files of the release, with the compact file in
        place of the Parquet file of the forecasts, if it has one.

    Raises
    ------
    ValueError
        If the release has the forecasts of several Parquet files.
    """
    forecasts = {}
    for file_path in file_paths:
        if not file_path.endswith(".parquet"):
            continue
        manifest = utils.manifest.read_manifest(file_path)
        if (
            manifest is not None
            and manifest["kind"] == "results"
            and manifest.get("case") == "forecasts"
        ):
            forecasts[file_path] = manifest
    if not forecasts:
        return file_paths
    if len(forecasts) > 1:
        raise ValueError(
            f"The release has several files of forecasts: {list(forecasts)}."
        )
    [(forecasts_path, manifest)] = forecasts.items()
    utils.manifest.verify_file(forecasts_path, "results")

    compact_path = os.path.join(folder, COMPACT_FORECASTS_FILE)
    pd.read_parquet(
        forecasts_path, columns=COMPACT_FORECASTS_COLUMNS
    ).to_parquet(compact_path, index=False)
    utils.manifest.write_manifest(
        compact_path,
        "results",
        {
            "case": "forecasts",
            "model": manifest.get("model"),
            "dataset": manifest.get("dataset"),
            "columns": COMPACT_FORECASTS_COLUMNS,
            "units": manifest.get("units"),
            "annual_totals": manifest.get("annual_totals"),
            "forecasts": {
                "file": manifest["file"],
                "sha256": manifest["sha256"],
                "code": manifest.get("code"),
            },
        },
    )
    logging.info(
        f"The forecasts of {forecasts_path} are uploaded as {compact_path}."
    )
    return [
        compact_path if file_path == forecasts_path else file_path
        for file_path in file_paths
    ]


def _archive_folder(name: str, file_paths: list[str], folder: str) -> str:
    """
    Write the files of a folder of a release to a ZIP archive.

    Parameters
    ----------
    name : str
        The name of the folder, which is that of the archive and of the
        folder of the files in it.
    file_paths : list[str]
        The paths of the files, with their manifests.
    folder : str
        The folder where to write the archive.

    Returns
    -------
    str
        The path of the archive.

    Raises
    ------
    ValueError
        If two files have the same name.

    Notes
    -----
    Zenodo has no folders, so the files of a folder of a release, such
    as those of a validation, are uploaded in this archive.
    """
    names = [os.path.basename(file_path) for file_path in file_paths]
    if len(set(names)) < len(names):
        raise ValueError(
            f"The files of the folder {name} have the same names: {names}."
        )
    archive_path = os.path.join(folder, f"{name}.zip")
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path, file_name in zip(file_paths, names, strict=True):
            archive.write(file_path, f"{name}/{file_name}")
    logging.info(f"The files of the folder {name} are in {archive_path}.")
    return archive_path


def main(config: ConfigModel) -> None:
    """
    Upload the release of the settings to Zenodo.

    The paths of the files are relative to the data folder, unless they
    are absolute. The files of each folder are uploaded in a ZIP archive
    named after it.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging("publication")
    utils.config.log_configuration(config)

    data_folder = utils.paths.get_data_folder()
    file_paths = [
        os.path.join(data_folder, file_path) for file_path in config.files
    ]
    folder_paths = {
        name: [os.path.join(data_folder, file_path) for file_path in files]
        for name, files in config.folders.items()
    }
    _check_publishable(
        [
            *file_paths,
            *(path for paths in folder_paths.values() for path in paths),
        ]
    )
    with tempfile.TemporaryDirectory() as folder:
        release_files = _with_manifests(
            _use_compact_forecasts(file_paths, folder)
        )
        for name, paths in folder_paths.items():
            release_files.append(
                _archive_folder(name, _with_manifests(paths), folder)
            )
        publishing.zenodo.publish_release(
            [*release_files, README_FILE],
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

"""
License: AGPL-3.0.

Description:

    This script uploads a release of DemandCast to Zenodo: the trained
    model, its settings and its forecasts, as a draft new version of a
    record, or of a new record, to check and publish on the website of
    Zenodo (see publishing.zenodo). The manifest of each file (see
    utils/manifest.py), which tells how the model was trained and which
    model and data gave the forecasts, is uploaded with it.
"""

import logging
import os

from pydantic import field_validator

import publishing.zenodo
import utils.config
import utils.manifest
import utils.paths


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

    publishing.zenodo.publish_release(
        _with_manifests(
            [
                os.path.join(utils.paths.get_data_folder(), file_path)
                for file_path in config.files
            ]
        ),
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

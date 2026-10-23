"""
License: AGPL-3.0.

Description:

    This script uploads a release of DemandCast to Zenodo: the trained
    model, its settings and its forecasts, as a draft new version of a
    record, or of a new record, to check and publish on the website of
    Zenodo (see publishing.zenodo).
"""

import os

import publishing.zenodo
import utils.config
import utils.paths
from pydantic import BaseModel, field_validator


class ConfigModel(BaseModel):
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
        [
            os.path.join(utils.paths.get_data_folder(), file_path)
            for file_path in config.files
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

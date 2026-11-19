"""
License: AGPL-3.0.

Description:

    This script copies the data folder to a private bucket of Google
    Cloud Storage, or the bucket to the data folder, without overwriting
    or deleting any file at the destination: only the missing files are
    copied, and the files that differ are reported in the log (see
    publishing.gcs). The copy can be limited to some folders, such as
    "assembled" to download only the assembled data. The script exits
    with the status 1 if files differ or objects of the bucket are not
    paths inside the data folder, so that a scheduled copy shows it.
"""

import sys
from typing import Literal

from pydantic import Field, field_validator

import publishing.gcs
import utils.config
import utils.paths


class ConfigModel(utils.config.StrictSettings):
    """Settings of sync.py."""

    direction: Literal["upload", "download"]
    bucket: str | None
    excluded_folders: list[str] = Field(default_factory=lambda: ["logs"])
    included_folders: list[str] | None = None
    dry_run: bool = False

    @field_validator("bucket")
    @classmethod
    def _check_bucket(cls, bucket: str | None) -> str:
        """
        Check that a bucket is given.

        Parameters
        ----------
        bucket : str | None
            The name of the bucket.

        Returns
        -------
        str
            The name of the bucket.

        Raises
        ------
        ValueError
            If no bucket is given.
        """
        if not bucket:
            raise ValueError(
                "The bucket must be given: the name of your bucket of "
                "Google Cloud Storage, such as demandcast-data."
            )
        return bucket


def main(config: ConfigModel) -> publishing.gcs.SyncReport:
    """
    Copy the data folder to or from the bucket of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.

    Returns
    -------
    publishing.gcs.SyncReport
        The files copied, identical, different and unsafe.
    """
    utils.config.set_up_logging(f"sync_{config.direction}")
    utils.config.log_configuration(config)

    return publishing.gcs.sync(
        str(config.bucket),
        config.direction,
        utils.paths.get_data_folder(),
        config.excluded_folders,
        config.dry_run,
        included_folders=config.included_folders,
    )


def get_exit_status(report: publishing.gcs.SyncReport) -> int:
    """
    Get the exit status of a copy.

    Parameters
    ----------
    report : publishing.gcs.SyncReport
        The files of the copy.

    Returns
    -------
    int
        1 if files differ between the two ends or objects were not
        downloaded, so that a scheduled copy shows it, else 0.
    """
    return 1 if report.different or report.unsafe else 0


if __name__ == "__main__":
    sys.exit(
        get_exit_status(
            main(
                utils.config.read_and_check_configuration(
                    "sync",
                    ConfigModel,
                    "Copy the data folder to or from a bucket of Google "
                    "Cloud Storage, without overwriting or deleting files.",
                )
            )
        )
    )

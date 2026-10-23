"""
License: AGPL-3.0.

Description:

    This script copies the data folder to a private bucket of Google
    Cloud Storage, or the bucket to the data folder, without overwriting
    or deleting any file at the destination: only the missing files are
    copied, and the files that differ are reported in the log (see
    publishing.gcs).
"""

from typing import Literal

import publishing.gcs
import utils.config
import utils.paths
from pydantic import BaseModel, field_validator


class ConfigModel(BaseModel):
    """Settings of sync.py."""

    direction: Literal["upload", "download"]
    bucket: str | None
    excluded_folders: list[str] = ["logs"]
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


def main(config: ConfigModel) -> None:
    """
    Copy the data folder to or from the bucket of the settings.

    Parameters
    ----------
    config : ConfigModel
        The settings.
    """
    utils.config.set_up_logging(f"sync_{config.direction}")
    utils.config.log_configuration(config)

    publishing.gcs.sync(
        str(config.bucket),
        config.direction,
        utils.paths.get_data_folder(),
        config.excluded_folders,
        config.dry_run,
    )


if __name__ == "__main__":
    main(
        utils.config.read_and_check_configuration(
            "sync",
            ConfigModel,
            "Copy the data folder to or from a bucket of Google Cloud "
            "Storage, without overwriting or deleting files.",
        )
    )

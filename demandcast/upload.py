# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This script uploads processed electricity demand data to a
    specified destination, such as Google Cloud Storage or Zenodo.
"""

import importlib
import logging
import os
from typing import Optional

import pandas
import utils.config
import utils.entities
import utils.uploader
from pydantic import BaseModel, ValidationError


def read_and_check_configuration() -> BaseModel:
    """
    Read and check the configuration for data retrieval.

    Returns
    -------
    ConfigModel : BaseModel
        A Pydantic model containing the validated configuration.

    Raises
    ------
    ValueError
        If the configuration is invalid.
    """

    # Define the configuration model.
    class ConfigModel(BaseModel):
        target_platform: str
        data_directory: str
        gcs_bucket_name: Optional[str] = None
        publish_to_zenodo: Optional[bool] = None
        made_by_oet: Optional[bool] = None

    # Read the configuration.
    raw_config = utils.config.read_configuration(
        os.path.basename(__file__),
        "Upload the processed electricity demand data to the "
        "specified destination.",
    )

    try:
        # Validate the configuration.
        return ConfigModel(**raw_config)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e


if __name__ == "__main__":
    # Read and check the configuration.
    config = read_and_check_configuration()

    # Set up the logging configuration.
    utils.config.set_up_logging("upload_of_processed_electricity_demand_data_")

    # Get the date of upload.
    date_of_upload = pandas.Timestamp.today().strftime("%Y-%m-%d")

    for file_name in os.listdir(config.data_directory):
        if file_name.endswith(".parquet"):
            # Define the full path to the file to be uploaded.
            file_path = os.path.join(config.data_directory, file_name)

            if config.target_platform == "gcs":
                # Upload the parquet file of the electricity demand time
                # series to GCS.
                utils.uploader.upload_to_gcs(
                    file_path,
                    config.gcs_bucket_name,
                    f"upload_{date_of_upload}/{file_name}",
                )
            elif config.target_platform == "zenodo":
                # Get the data source from the file name.
                for data_source in utils.entities.read_data_sources():
                    if data_source in file_name:
                        break

                # Import the retrieval module for the data source.
                retrieval_module = importlib.import_module(
                    f"retrievals.electricity_demand_data_sources.{data_source}"
                )

                # Upload the parquet file of the electricity demand time
                # series to Zenodo.
                if retrieval_module.redistribute():
                    utils.uploader.upload_to_zenodo(
                        file_path,
                        data_type="actual",
                        made_by_oet=config.made_by_oet,
                        publish=config.publish_to_zenodo,
                        testing=True,
                    )
                else:
                    logging.warning(
                        f"The data source {data_source} does not allow "
                        "redistribution. The data will not be "
                        "uploaded to Zenodo."
                    )

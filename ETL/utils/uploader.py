# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module provides functions to upload files to Google Cloud
    Storage (GCS) and Zenodo.
"""

import json
import logging
import os

import pandas
import requests
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

import utils.directories


def upload_to_gcs(
    file_path: str,
    bucket_name: str,
    destination_blob_name: str,
) -> None:
    """
    Upload a file to Google Cloud Storage (GCS).

    This function uploads a file to a specified GCS bucket. It uses the
    Google Cloud Storage client library to handle the upload process.

    Parameters
    ----------
    file_path : str
        The path to the file to be uploaded.
    bucket_name : str
        The name of the GCS bucket.
    destination_blob_name : str
        The name of the blob in the GCS bucket.

    Raises
    ------
    OSError
        If there is an error reading the file.
    GoogleCloudError
        If there is an error uploading the file to GCS.
    """
    # Create a GCS client.
    storage_client = storage.Client()

    # Get the bucket.
    bucket = storage_client.bucket(bucket_name)

    # Create a new blob.
    blob = bucket.blob(destination_blob_name)

    # Upload the file to GCS.
    try:
        blob.upload_from_filename(file_path)
    except (OSError, GoogleCloudError) as e:
        logging.error(
            f"Failed to upload file {file_path} to GCS bucket {bucket_name} "
            f"as {destination_blob_name}: {e}"
        )
        raise


def upload_to_zenodo(
    file_path: str, data_type: str, publish: bool = False, testing: bool = True
) -> None:
    """
    Upload a file to Zenodo.

    This function uploads files to Zenodo using the Zenodo API. It
    requires an access token for authentication.

    Parameters
    ----------
    file_path : str
        The path to the file to be uploaded.
    data_type : str
        The type of data being uploaded. It can be either "actual" or
        "synthetic".
    publish : bool, optional
        If True, the function will publish the deposition in Zenodo.
    testing : bool, optional
        If True, the function will use the testing environment for
        Zenodo. If False, it will use the production environment.

    Raises
    ------
    ValueError
        If the `data_type` is not 'actual' or 'synthetic'.
    Exception
        If there is an error uploading a file to Zenodo or if the
        response from Zenodo is not successful.
    """
    # Get the root directory of the project.
    root_directory = utils.directories.read_folders_structure()["root_folder"]

    # Load the environment variables.
    load_dotenv(dotenv_path=os.path.join(root_directory, ".env"))

    # Get the Zenodo access token from environment variables.
    if testing:
        access_token = os.getenv("SANDBOX_ZENODO_API_KEY")
        sandbox_url = "sandbox."
    else:
        access_token = os.getenv("ZENODO_API_KEY")
        sandbox_url = ""

    if data_type == "actual":
        # Define the deposition title and description for the actual
        # dataset.
        title = (
            "Global Dataset of Hourly or Sub-Hourly Historical Electricity "
            "Demand"
        )
        description = (
            "This dataset contains historical electricity demand data "
            "at hourly or sub-hourly resolution for various countries and "
            "subdivisions. The data is retrieved from various sources, and "
            "the retrieval scripts are available in the GitHub "
            "repository "
            "https://github.com/open-energy-transition/demandcast."
        )
    elif data_type == "synthetic":
        # Define the deposition title and description for the synthetic
        # dataset.
        title = "Global Dataset of Hourly Synthetic Electricity Demand"
        description = (
            "This dataset contains synthetic electricity demand data at "
            "hourly resolution for various countries. The data is "
            "generated using machine learning models trained on "
            "historical demand data, weather data, and socioeconomic "
            "indicators. Details on the generation process and the models "
            "used can be found in the GitHub repository "
            "https://github.com/open-energy-transition/demandcast."
        )
    else:
        raise ValueError(
            "Invalid data_type. Expected 'actual' or 'synthetic'."
        )

    # Define the deposition metadata for the dataset.
    data = {
        "metadata": {
            "title": title,
            "upload_type": "dataset",
            "publication_date": pandas.Timestamp.now().strftime("%Y-%m-%d"),
            "description": description,
            "creators": [
                {
                    "name": "Antonini, Enrico G. A.",
                    "affiliation": "Open Energy Transition",
                    "orcid": "0000-0002-5573-0954",
                },
                {
                    "name": "Vamsi Priya, Goli",
                    "affiliation": "Open Energy Transition",
                },
                {
                    "name": "Steijn, Kevin",
                },
            ],
            "contributors": [
                {
                    "name": "Open Energy Transition",
                    "type": "HostingInstitution",
                },
                {
                    "name": "Breakthrough Energy",
                    "type": "Sponsor",
                },
            ],
            "access_right": "open",
            "license": "agpl-1.0-or-later",
            "keywords": [
                "electricity demand",
                "synthetic data",
                "machine learning",
            ],
            "related_identifiers": [
                {
                    "relation": "isDerivedFrom",
                    "identifier": (
                        "https://github.com/open-energy-transition/demandcast"
                    ),
                    "resource_type": "software",
                }
            ],
            "custom": {
                "code:codeRepository": (
                    "https://github.com/open-energy-transition/demandcast/"
                ),
                "code:programmingLanguage": [
                    {"id": "python", "title": {"en": "Python"}}
                ],
                "code:developmentStatus": {
                    "id": "active",
                    "title": {"en": "Active"},
                },
            },
            "language": "eng",
        }
    }

    # Get all the depositions from Zenodo.
    response = requests.get(
        f"https://{sandbox_url}zenodo.org/api/deposit/depositions",
        params={"access_token": access_token},
    )

    # Check if the response is successful.
    if response.status_code != 200:
        logging.error(
            f"Failed to retrieve depositions from Zenodo: {response.text}"
        )
        raise Exception(f"Zenodo deposition retrieval failed: {response.text}")

    # Check if a deposition with the same title already exists.
    new_version = False
    add_to_draft = False
    for deposition in response.json():
        if deposition["metadata"]["title"] == data["metadata"]["title"]:
            if deposition["submitted"]:
                # If the deposition is already submitted (published),
                # set new_version to True
                new_version = True
            else:
                # If the deposition is not submitted (published), set
                # add_to_draft to True
                add_to_draft = True

            # Extract the deposition ID from the response.
            deposition_id = deposition["id"]
            break

    if new_version:
        # Create a new version of the existing deposition in Zenodo.
        response = requests.post(
            (
                f"https://{sandbox_url}zenodo.org/api/deposit/depositions/"
                f"{deposition_id}/actions/newversion"
            ),
            params={"access_token": access_token},
        )

        # Check if the response is successful.
        if response.status_code != 201:
            logging.error(
                f"Failed to create new version in Zenodo: {response.text}"
            )
            raise Exception(
                f"Zenodo new version creation failed: {response.text}"
            )

        # Extract the deposition ID of the new version from the
        # response.
        deposition_id = response.json()["id"]

        # Update the metadata for the new version.
        response = requests.put(
            (
                f"https://{sandbox_url}zenodo.org/api/deposit/"
                f"depositions/{deposition_id}"
            ),
            params={"access_token": access_token},
            data=json.dumps(data),
        )

        # Check if the response is successful.
        if response.status_code != 200:
            logging.error(
                "Failed to update metadata for new version in Zenodo: "
                f"{response.text}"
            )
            raise Exception(f"Zenodo metadata update failed: {response.text}")

        # Get the list of files in the deposition.
        response = requests.get(
            f"https://{sandbox_url}zenodo.org/api/deposit/"
            f"depositions/{deposition_id}/files",
            params={"access_token": access_token},
        )

        # Check if the response is successful.
        if response.status_code != 200:
            logging.error(
                f"Failed to retrieve files from Zenodo deposition: "
                f"{response.text}"
            )
            raise Exception(f"Zenodo file retrieval failed: {response.text}")

        # Delete all files inherited from the previous version.
        for file_info in response.json():
            file_id = file_info["id"]
            response = requests.delete(
                f"https://{sandbox_url}zenodo.org/api/deposit/depositions/"
                f"{deposition_id}/files/{file_id}",
                params={"access_token": access_token},
            )

            # Check if the response is successful.
            if response.status_code != 204:
                logging.error(
                    f"Failed to delete file {file_info['filename']} "
                    f"from Zenodo deposition: {response.text}"
                )
                raise Exception(
                    f"Zenodo file deletion failed: {response.text}"
                )
    elif add_to_draft:
        # Update the metadata for the draft deposition in Zenodo.
        response = requests.put(
            (
                f"https://{sandbox_url}zenodo.org/api/deposit/"
                f"depositions/{deposition_id}"
            ),
            params={"access_token": access_token},
            data=json.dumps(data),
        )

        # Check if the response is successful.
        if response.status_code != 200:
            logging.error(
                f"Failed to update metadata for draft deposition in Zenodo: "
                f"{response.text}"
            )
            raise Exception(f"Zenodo metadata update failed: {response.text}")
    else:
        # Create a new deposition in Zenodo.
        response = requests.post(
            f"https://{sandbox_url}zenodo.org/api/deposit/depositions",
            params={"access_token": access_token},
            data=json.dumps(data),
        )

        # Check if the response is successful.
        if response.status_code != 201:
            logging.error(
                f"Failed to create deposition in Zenodo: {response.text}"
            )
            raise Exception(
                f"Zenodo deposition creation failed: {response.text}"
            )

        # Extract the deposition ID from the response.
        deposition_id = response.json()["id"]

    # Upload the file to Zenodo.
    with open(file_path, "rb") as file_to_upload:
        response = requests.post(
            f"https://{sandbox_url}zenodo.org/api/deposit/depositions/"
            f"{deposition_id}/files",
            data={"name": os.path.basename(file_path)},
            files={"file": file_to_upload},
            params={"access_token": access_token},
        )

        if response.status_code != 201:
            logging.error(
                f"Failed to upload file {file_path} to Zenodo: {response.text}"
            )
            raise Exception(f"Zenodo upload failed: {response.text}")

    if not publish:
        logging.info(
            "File uploaded to Zenodo but not published. "
            "Set 'publish' to True to publish the deposition or "
            "use the Zenodo web interface to publish it."
        )
    else:
        # Publish the deposition in Zenodo.
        response = requests.post(
            (
                f"https://{sandbox_url}zenodo.org/api/deposit/depositions/"
                f"{deposition_id}/actions/publish"
            ),
            params={"access_token": access_token},
        )

        # Check if the response is successful.
        if response.status_code != 202:
            logging.error(
                f"Failed to publish deposition in Zenodo: {response.text}"
            )
            raise Exception(f"Zenodo publication failed: {response.text}")

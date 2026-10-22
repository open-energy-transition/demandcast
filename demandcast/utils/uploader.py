"""
License: AGPL-3.0.

Description:

    This module provides functions to upload files to Google Cloud
    Storage (GCS) and Zenodo.
"""

import json
import logging
import os
from typing import Any

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

import utils.paths


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
        e.add_note(
            f"Failed to upload file {file_path} to GCS bucket {bucket_name} "
            f"as {destination_blob_name}."
        )
        raise


class ZenodoError(RuntimeError):
    """Error returned by the Zenodo API."""


# The address of the API of Zenodo, with "sandbox." for its sandbox.
ZENODO_API = "https://{sandbox}zenodo.org/api/deposit/depositions"

# The title, description and license of each type of dataset. The data
# of some sources may be redistributed only for non-commercial
# purposes, so the dataset of actual data keeps that condition.
DATASETS = {
    "actual": {
        "title": (
            "Global Dataset of Hourly or Sub-Hourly Historical Electricity "
            "Demand"
        ),
        "description": (
            "<p>This dataset contains historical electricity demand data "
            "at hourly or sub-hourly resolution for various countries and "
            "subdivisions.</p>\n"
            "<p>The Python code to retrieve the data is available in the "
            "GitHub repository "
            '<a href="https://github.com/open-energy-transition/demandcast">'
            "https://github.com/open-energy-transition/demandcast</a>.</p>\n"
            "<p>This dataset includes only electricity demand data that is "
            "permissible to redistribute, based on the licensing terms of the "
            "original data sources. At a minimum, the data shared here may be "
            "redistributed for non-commercial purposes, while some other data "
            "is available under more permissive, open licenses. A complete "
            "list of original data sources and their associated license terms "
            "is available in the GitHub repository "
            '<a href="https://github.com/open-energy-transition/Awesome-Electric-Demand">'
            "https://github.com/open-energy-transition/Awesome-Electric-Demand</a>.</p>\n"
            "<p>The dataset is therefore published under the Creative "
            "Commons Attribution Non Commercial 4.0 International "
            "license.</p>"
        ),
        "license": "cc-by-nc-4.0",
    },
    "synthetic": {
        "title": "Global Dataset of Hourly Synthetic Electricity Demand",
        "description": (
            "<p>This dataset contains synthetic electricity demand data at "
            "hourly resolution for various countries.</p>\n"
            "<p>The data is generated using machine learning models trained "
            "on historical demand data, weather data, and socioeconomic "
            "indicators.</p>\n"
            "<p>Details on the generation process and the models "
            "used can be found in the GitHub repository "
            '<a href="https://github.com/open-energy-transition/demandcast">'
            "https://github.com/open-energy-transition/demandcast</a>.</p>"
        ),
        "license": "CC-BY-4.0",
    },
}


def build_zenodo_metadata(data_type: str, made_by_oet: bool) -> dict:
    """
    Build the metadata of a deposition of a dataset on Zenodo.

    Parameters
    ----------
    data_type : str
        The type of data, "actual" or "synthetic".
    made_by_oet : bool
        Whether the data was made by Open Energy Transition, whose
        authors are in config/oet_zenodo_metadata.yaml; those of others
        are in config/zenodo_metadata.yaml.

    Returns
    -------
    dict
        The metadata, as the API of Zenodo takes it.

    Raises
    ------
    ValueError
        If the `data_type` is not 'actual' or 'synthetic'.
    """
    if data_type not in DATASETS:
        raise ValueError(
            "Invalid data_type. Expected 'actual' or 'synthetic'."
        )
    dataset = DATASETS[data_type]
    title, description, license_id = (
        dataset["title"],
        dataset["description"],
        dataset["license"],
    )

    # Read the creators and contributors of the dataset.
    author_metadata_path = utils.paths.get_config_file(
        "oet_zenodo_metadata.yaml" if made_by_oet else "zenodo_metadata.yaml"
    )
    with open(author_metadata_path, encoding="utf-8") as file:
        author_metadata = yaml.safe_load(file)
    creators = author_metadata["creators"]
    contributors = author_metadata["contributors"]

    return {
        "metadata": {
            "title": title,
            "upload_type": "dataset",
            "publication_date": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "description": description,
            "creators": creators,
            "contributors": contributors,
            "access_right": "open",
            "license": license_id,
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


class _ZenodoApi:
    """The requests to the depositions of the API of Zenodo."""

    def __init__(self, testing: bool) -> None:
        """
        Set up the address and the key of the API.

        Parameters
        ----------
        testing : bool
            Whether to use the sandbox of Zenodo, with the key in
            SANDBOX_ZENODO_API_KEY, instead of Zenodo, with the key in
            ZENODO_API_KEY.
        """
        load_dotenv(dotenv_path=utils.paths.ENV_FILE)
        self.url = ZENODO_API.format(sandbox="sandbox." if testing else "")
        self.access_token = os.getenv(
            "SANDBOX_ZENODO_API_KEY" if testing else "ZENODO_API_KEY"
        )

    def request(
        self,
        method: str,
        path: str,
        expected_status: int,
        action: str,
        timeout: int = 60,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Send a request to the API and check its status.

        Parameters
        ----------
        method : str
            The method, "GET", "POST", "PUT" or "DELETE".
        path : str
            The path after the address of the depositions.
        expected_status : int
            The status of a success.
        action : str
            The action of the request, for the message of its failure.
        timeout : int, optional
            The timeout of the request in seconds.
        **kwargs : Any
            The other arguments of the request, such as its data.

        Returns
        -------
        requests.Response
            The response.

        Raises
        ------
        ZenodoError
            If the status of the response is not the expected one.
        """
        send = getattr(requests, method.lower())
        response = send(
            self.url + path,
            params={"access_token": self.access_token},
            timeout=timeout,
            **kwargs,
        )
        if response.status_code != expected_status:
            raise ZenodoError(f"Zenodo {action} failed: {response.text}")
        return response


def _prepare_deposition(api: _ZenodoApi, metadata: dict) -> int:
    """
    Get the deposition of a dataset, ready for its file.

    A published deposition with the title of the dataset gets a new
    version, without the files of the previous one, a draft with the
    title gets the metadata, and otherwise a deposition is created.

    Parameters
    ----------
    api : _ZenodoApi
        The API of Zenodo.
    metadata : dict
        The metadata of the deposition.

    Returns
    -------
    int
        The identifier of the deposition.
    """
    depositions = api.request("GET", "", 200, "deposition retrieval").json()
    deposition = next(
        (
            deposition
            for deposition in depositions
            if deposition["metadata"]["title"] == metadata["metadata"]["title"]
        ),
        None,
    )

    if deposition is None:
        response = api.request(
            "POST", "", 201, "deposition creation", data=json.dumps(metadata)
        )
        return response.json()["id"]

    deposition_id = deposition["id"]
    if deposition["submitted"]:
        response = api.request(
            "POST",
            f"/{deposition_id}/actions/newversion",
            201,
            "new version creation",
        )
        deposition_id = response.json()["id"]
    api.request(
        "PUT",
        f"/{deposition_id}",
        200,
        "metadata update",
        data=json.dumps(metadata),
    )
    if deposition["submitted"]:
        # Delete all files inherited from the previous version.
        files = api.request(
            "GET", f"/{deposition_id}/files", 200, "file retrieval"
        ).json()
        for file_info in files:
            api.request(
                "DELETE",
                f"/{deposition_id}/files/{file_info['id']}",
                204,
                f"deletion of the file {file_info['filename']}",
            )
    return deposition_id


def upload_to_zenodo(
    file_path: str,
    data_type: str,
    made_by_oet: bool,
    publish: bool = False,
    testing: bool = True,
) -> None:
    """
    Upload a file to Zenodo.

    The file goes to the deposition of its dataset (see
    _prepare_deposition), which is published if asked.

    Parameters
    ----------
    file_path : str
        The path to the file to be uploaded.
    data_type : str
        The type of data being uploaded. It can be either "actual" or
        "synthetic".
    made_by_oet : bool
        If True, the function will indicate that the deposition was made
        by Open Energy Transition.
    publish : bool, optional
        If True, the function will publish the deposition in Zenodo.
    testing : bool, optional
        If True, the function will use the testing environment for
        Zenodo. If False, it will use the production environment.
    """
    metadata = build_zenodo_metadata(data_type, made_by_oet)
    api = _ZenodoApi(testing)
    deposition_id = _prepare_deposition(api, metadata)

    with open(file_path, "rb") as file_to_upload:
        api.request(
            "POST",
            f"/{deposition_id}/files",
            201,
            f"upload of the file {file_path}",
            # Zenodo answers once it has processed the whole file.
            timeout=600,
            data={"name": os.path.basename(file_path)},
            files={"file": file_to_upload},
        )

    if publish:
        api.request(
            "POST", f"/{deposition_id}/actions/publish", 202, "publication"
        )
    else:
        logging.info(
            "File uploaded to Zenodo but not published. "
            "Set 'publish' to True to publish the deposition or "
            "use the Zenodo web interface to publish it."
        )

# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This file contains unit tests for the uploader module in the ETL
    utility package.
"""

from unittest.mock import Mock, mock_open, patch

import pytest
import utils.uploader
from google.cloud.exceptions import GoogleCloudError


def test_upload_to_gcs():
    """
    Test the upload_to_gcs function by mocking GCS interactions.

    This test checks if the function correctly uploads a file to a
    Google Cloud Storage (GCS) bucket. It uses mocking to simulate the
    GCS interactions, ensuring that the function behaves as expected
    without requiring actual GCS access. It also tests the error
    handling for OSError and GoogleCloudError.
    """
    # Define a mock for the GCS bucket and blob.
    mock_bucket = Mock()
    mock_blob = Mock()

    with patch("google.cloud.storage.Client") as mock_storage_client:
        # Mock the bucket and blob.
        mock_storage_client.return_value.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob

        # Call the function.
        utils.uploader.upload_to_gcs(
            "dummy/path.txt", "test-bucket", "dest/path.txt"
        )

        # Assert the file was uploaded.
        mock_blob.upload_from_filename.assert_called_once_with(
            "dummy/path.txt"
        )

        # Check if the OSError is handled correctly.
        mock_blob.upload_from_filename.side_effect = OSError("file not found")
        with pytest.raises(OSError):
            utils.uploader.upload_to_gcs(
                "bad/path.txt", "test-bucket", "dest/path.txt"
            )

        # Check if the GoogleCloudError is handled correctly.
        mock_blob.upload_from_filename.side_effect = GoogleCloudError(
            "GCS failure"
        )
        with pytest.raises(GoogleCloudError):
            utils.uploader.upload_to_gcs(
                "bad/path.txt", "test-bucket", "dest/path.txt"
            )


def _zenodo_request(
    request_type: str = "",
    response_type: str = "",
    submitted: bool = True,
    error: bool = False,
):
    """
    Mock Zenodo API requests.

    This function simulates the responses from the Zenodo API based on
    the request type and response type specified. It returns a mock
    response object that mimics the behavior of the requests library.

    Parameters
    ----------
    request_type : str
        The type of request being made (e.g., "get", "post", "put",
        "delete").
    response_type : str
        The type of response expected (e.g., "actual", "synthetic",
        "file", "no_depositions", "new_deposition", "upload_file",
        "publish").
    submitted : bool
        Indicates whether the deposition is submitted or not.
    error : bool
        If True, simulates an error response from the Zenodo API.

    Returns
    -------
    response : Mock
        A mock response object that simulates the behavior of the
        requests library.
    """
    # Create a mock response object.
    response = Mock()

    # Set the status code  and JSON return value based on the request
    # and response types.
    if error:
        response.status_code = 500
    else:
        if request_type == "get":
            response.status_code = 200
            if response_type == "actual":
                response.json.return_value = [
                    {
                        "id": "12345",
                        "metadata": {
                            "title": (
                                "Global Dataset of Hourly or Sub-Hourly "
                                "Historical Electricity Demand"
                            )
                        },
                        "submitted": submitted,
                    }
                ]
            elif response_type == "synthetic":
                response.json.return_value = [
                    {
                        "id": "12345",
                        "metadata": {
                            "title": (
                                "Global Dataset of Hourly Synthetic "
                                "Electricity Demand"
                            )
                        },
                        "submitted": submitted,
                    }
                ]
            elif response_type == "file":
                response.json.return_value = [
                    {"id": "12345", "filename": "file.csv"}
                ]
            elif response_type == "no_depositions":
                response.json.return_value = []
        elif request_type == "post":
            if response_type == "new_deposition":
                response.status_code = 201
                response.json.return_value = {"id": "12345"}
            elif response_type == "upload_file":
                response.status_code = 201
            elif response_type == "publish":
                response.status_code = 202
        elif request_type == "put":
            response.status_code = 200
        elif request_type == "delete":
            response.status_code = 204

    return response


def test_upload_file_to_new_deposition_on_zenodo():
    """
    Test upload_to_zenodo for creating a new deposition.

    This test checks if the function correctly creates a new deposition
    on Zenodo and uploads a file to it. It uses mocking to simulate the
    Zenodo API interactions.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="no_depositions"
        )

        # Mock the response for creating a new deposition.
        mock_post_1 = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for uploading a new file in the deposition.
        mock_post_2 = _zenodo_request(
            request_type="post", response_type="upload_file"
        )

        # Mock the response for publishing the deposition.
        mock_post_3 = _zenodo_request(
            request_type="post", response_type="publish"
        )

        # Combine the mock responses for the post requests.
        mock_post.side_effect = [mock_post_1, mock_post_2, mock_post_3]

        # Call the function to upload a file to a new deposition.
        utils.uploader.upload_to_zenodo(
            "/fake/root/file1.csv",
            "actual",
            publish=True,
            testing=True,
            made_by_oet=False,
        )


def test_upload_file_to_draft_version_on_zenodo():
    """
    Test upload_to_zenodo for uploading a file to a draft version.

    This test checks if the function correctly uploads a file to an
    existing draft of a new version of a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.put") as mock_put,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="actual", submitted=False
        )

        # Mock the response for updating the deposition metadata.
        mock_put.return_value = _zenodo_request(request_type="put")

        # Mock the response for uploading a new file in the deposition.
        mock_post.return_value = _zenodo_request(
            request_type="post", response_type="upload_file"
        )

        # Call the function to upload a file to a draft version.
        utils.uploader.upload_to_zenodo(
            "/fake/root/file1.csv",
            "actual",
            publish=False,
            testing=True,
            made_by_oet=True,
        )


def test_upload_file_to_new_version_on_zenodo():
    """
    Test upload_to_zenodo for uploading a file to a new version.

    This test checks if the function correctly uploads a file to a new
    version of a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.put") as mock_put,
        patch("requests.post") as mock_post,
        patch("requests.delete") as mock_delete,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Mock the response for getting depositions.
        mock_get_1 = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=True
        )

        # Mock the response for creating a new deposition.
        mock_post_1 = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for updating the deposition metadata.
        mock_put.return_value = _zenodo_request(request_type="put")

        # Mock the response for getting the files in the deposition.
        mock_get_2 = _zenodo_request(request_type="get", response_type="file")

        # Mock the response for deleting the existing files in the
        # deposition.
        mock_delete.return_value = _zenodo_request(request_type="delete")

        # Mock the response for uploading a new file in the deposition.
        mock_post_2 = _zenodo_request(
            request_type="post", response_type="upload_file"
        )

        # Combine the mock responses for the get requests.
        mock_get.side_effect = [mock_get_1, mock_get_2]

        # Combine the mock responses for the post requests.
        mock_post.side_effect = [mock_post_1, mock_post_2]

        # Call the function to upload a file to a new version.
        utils.uploader.upload_to_zenodo(
            "/fake/root/file1.csv",
            "synthetic",
            publish=False,
            testing=False,
            made_by_oet=True,
        )


def test_zenodo_error_invalid_input():
    """
    Test error handling for invalid input in upload_to_zenodo.

    This test checks if the function raises appropriate exceptions for
    invalid inputs.
    """
    with pytest.raises(ValueError):
        utils.uploader.upload_to_zenodo(
            "/fake/root/file1.csv",
            "invalid_type",
            publish=False,
            testing=False,
            made_by_oet=True,
        )


def test_zenodo_error_get_depositions():
    """
    Test error handling when getting depositions from Zenodo.

    This test checks if the function raises an exception when it fails
    to retrieve depositions from Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting depositions to simulate an
        # error.
        mock_get.return_value = _zenodo_request(error=True)

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "actual",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_new_version_of_deposition():
    """
    Test error handling when creating a new version of a deposition.

    This test checks if the function raises an exception when it fails
    to create a new version of a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=True
        )

        # Mock the response for creating a new deposition with an error.
        mock_post.return_value = _zenodo_request(error=True)

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "synthetic",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_update_new_version_of_deposition():
    """
    Test error handling when updating metadata.

    This test checks if the function raises an exception when it fails
    to update the metadata of a new version of a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=True
        )

        # Mock the response for creating a new deposition.
        mock_post.return_value = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for updating the deposition metadata with an
        # error.
        mock_put.return_value = _zenodo_request(error=True)

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "synthetic",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_get_files_in_draft():
    """
    Test error handling when getting files in a draft deposition.

    This test checks if the function raises an exception when it fails
    to retrieve the files in a draft deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting depositions.
        mock_get_1 = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=True
        )

        # Mock the response for creating a new deposition.
        mock_post.return_value = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for updating the deposition metadata.
        mock_put.return_value = _zenodo_request(request_type="put")

        # Mock the response for getting the files in the deposition with
        # an error.
        mock_get_2 = _zenodo_request(error=True)

        # Combine the mock responses for the get requests.
        mock_get.side_effect = [mock_get_1, mock_get_2]

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "synthetic",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_delete_files_in_draft():
    """
    Test error handling when deleting files in a draft deposition.

    This test checks if the function raises an exception when it fails
    to delete existing files in a draft deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("requests.put") as mock_put,
        patch("requests.delete") as mock_delete,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting the depositions.
        mock_get_1 = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=True
        )

        # Mock the response for creating a new deposition.
        mock_post.return_value = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for updating the deposition metadata.
        mock_put.return_value = _zenodo_request(request_type="put")

        # Mock the response for getting the files in the deposition.
        mock_get_2 = _zenodo_request(request_type="get", response_type="file")

        # Mock the response for deleting the existing files in the
        # deposition with an error.
        mock_delete.return_value = _zenodo_request(error=True)

        # Combine the mock responses for the get requests.
        mock_get.side_effect = [mock_get_1, mock_get_2]

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "synthetic",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_update_draft_metadata():
    """
    Test error handling when updating draft metadata.

    This test checks if the function raises an exception when it fails
    to update the metadata of a draft deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.put") as mock_put,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Moch the response for getting the depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="synthetic", submitted=False
        )

        # Mock the response for updating the deposition metadata with an
        # error.
        mock_put.return_value = _zenodo_request(error=True)

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "synthetic",
                publish=False,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_create_new_deposition():
    """
    Test error handling when creating a new deposition.

    This test checks if the function raises an exception when it fails
    to create a new deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="no_depositions"
        )

        # Mock the response for creating a new deposition with an error.
        mock_post.return_value = _zenodo_request(error=True)

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "actual",
                publish=True,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_upload_file_to_deposition():
    """
    Test error handling when uploading a file to a deposition.

    This test checks if the function raises an exception when it fails
    to upload a file to a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="no_depositions"
        )

        # Mock the response for creating a new deposition.
        mock_post_1 = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for uploading a new file in the deposition
        # with an error.
        mock_post_2 = _zenodo_request(error=True)

        # Combine the mock responses for the post requests.
        mock_post.side_effect = [mock_post_1, mock_post_2]

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "actual",
                publish=True,
                testing=True,
                made_by_oet=True,
            )


def test_zenodo_error_publish_deposition():
    """
    Test error handling when publishing a deposition.

    This test checks if the function raises an exception when it fails
    to publish a deposition on Zenodo.
    """
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("utils.directories.read_folders_structure"),
        patch("dotenv.load_dotenv"),
        patch("os.getenv"),
        patch("builtins.open", mock_open(read_data="test data")),
    ):
        # Mock the response for getting depositions.
        mock_get.return_value = _zenodo_request(
            request_type="get", response_type="no_depositions"
        )

        # Mock the response for creating a new deposition.
        mock_post_1 = _zenodo_request(
            request_type="post", response_type="new_deposition"
        )

        # Mock the response for uploading a new file in the deposition.
        mock_post_2 = _zenodo_request(
            request_type="post", response_type="upload_file"
        )

        # Mock the response for publishing the deposition with an error.
        mock_post_3 = _zenodo_request(error=True)

        # Combine the mock responses for the post requests.
        mock_post.side_effect = [mock_post_1, mock_post_2, mock_post_3]

        with pytest.raises(Exception):
            utils.uploader.upload_to_zenodo(
                "/fake/root/file1.csv",
                "actual",
                publish=True,
                testing=True,
                made_by_oet=True,
            )

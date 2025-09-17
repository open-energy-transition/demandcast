# -*- coding: utf-8 -*-
"""
License: AGPL-3.0.

Description:

    This module includes functions to download hourly or sub-hourly
    electricity demand data from various data sources. The retrieved
    data is cleaned and saved in a structured format for further
    analysis. The module also supports uploading the data to Google
    Cloud Storage (GCS) if a bucket name is provided and to Zenodo for
    open access sharing.
"""

import importlib
import logging
import os

import pandas
import utils.directories
import utils.entities
import utils.time_series
import utils.uploader
from tqdm import tqdm


def _retrieve_data(data_source: str, code: str) -> pandas.Series:
    """
    Retrieve the electricity demand data.

    This function retrieves the electricity demand time series from the
    specified data source.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    """
    # Check if there is only one code in the data source.
    one_code_in_data_source = (
        len(utils.entities.read_codes_in(data_source=data_source)) == 1
    )

    # Import the retrieval module for the data source.
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    # Get the list of requests to retrieve the electricity demand time
    # series.
    if one_code_in_data_source:
        # If there is only one code in the data source, there is no need
        # to specify the code.
        requests = retrieval_module.get_available_requests()
    else:
        # If there are multiple codes in the data source, the code needs
        # to be specified.
        requests = retrieval_module.get_available_requests(code)

    if requests is None:
        # If there are no requests (requests is None), it means that the
        # electricity demand time series can be retrieved all at once.
        # Get the retrieval function to download and extract the data.
        retrieval_function = retrieval_module.download_and_extract_data

        if one_code_in_data_source:
            # If there is only one code in the data source, there is no
            # need to specify the code.
            electricity_demand_time_series = retrieval_function()
        else:
            # If there are multiple codes in the data source, the code
            # needs to be specified.
            electricity_demand_time_series = retrieval_function(code)

    else:
        # If there are multiple requests (request is not None), loop
        # over the requests to retrieve the electricity demand time
        # series of each request.
        # Get the retrieval function to download and extract the data.
        retrieval_function = (
            retrieval_module.download_and_extract_data_for_request
        )

        if one_code_in_data_source:
            # If there is only one code in the data source, there is no
            # need to specify the code.
            # Loop over the requests to retrieve the electricity demand
            # time series of each request.
            electricity_demand_time_series_list = [
                retrieval_function(*request)
                if isinstance(request, tuple)
                else retrieval_function(request)
                for request in requests
            ]
        else:
            # If there are multiple codes in the data source, the code
            # needs to be specified.
            # Loop over the requests to retrieve the electricity demand
            # time series of each request.
            electricity_demand_time_series_list = [
                retrieval_function(*request, code)
                if isinstance(request, tuple)
                else retrieval_function(request, code)
                for request in requests
            ]

        # Remove empty time series.
        electricity_demand_time_series_list = [
            time_series
            for time_series in electricity_demand_time_series_list
            if not time_series.empty
        ]

        # Concatenate the electricity demand time series of all periods.
        electricity_demand_time_series = pandas.concat(
            electricity_demand_time_series_list
        )

    # Clean the data.
    electricity_demand_time_series = utils.time_series.clean_data(
        electricity_demand_time_series, "Load (MW)"
    )

    return electricity_demand_time_series


def _save_data(
    electricity_demand_time_series: pandas.Series,
    code: str,
    data_source: str,
    upload_to_gcs: str | None,
    upload_to_zenodo: bool,
    publish_to_zenodo: bool,
    made_by_oet: bool,
) -> None:
    """
    Save the electricity demand time series.

    This function saves the electricity demand time series to a file in
    the parquet and csv formats. If a Google Cloud Storage (GCS) bucket
    name is provided, it uploads the parquet file to the specified GCS
    bucket.

    Parameters
    ----------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    upload_to_gcs : str | None
        The bucket name of the Google Cloud Storage (GCS) to upload the
        data.
    upload_to_zenodo : bool
        Whether to upload the data to Zenodo.
    publish_to_zenodo : bool
        Whether to publish the data to Zenodo.
    made_by_oet : bool
        Whether the data was made by Open Energy Transition.
    """
    # Get the date of retrieval.
    date_of_retrieval = pandas.Timestamp.today().strftime("%Y-%m-%d")

    # Get the directory to store the electricity demand time series.
    result_directory = utils.directories.read_folders_structure()[
        "electricity_demand_folder"
    ]
    result_directory = os.path.join(result_directory, date_of_retrieval)
    os.makedirs(result_directory, exist_ok=True)

    # Define the identifier of the file to be saved.
    identifier = code + "_" + data_source

    # Define the path to the file to be saved without the extension.
    file_path = os.path.join(result_directory, identifier)

    # Save the time series to both parquet and csv files.
    electricity_demand_time_series.to_frame().to_parquet(
        file_path + ".parquet"
    )
    electricity_demand_time_series.to_csv(file_path + ".csv")

    if upload_to_gcs:
        # Upload the parquet file of the electricity demand time series
        # to GCS.
        utils.uploader.upload_to_gcs(
            file_path + ".parquet",
            upload_to_gcs,
            "upload_" + date_of_retrieval + "/" + identifier + ".parquet",
        )

    # Import the retrieval module for the data source.
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    if upload_to_zenodo and retrieval_module.redistribute():
        # Upload the parquet file of the electricity demand time series
        # to Zenodo.
        utils.uploader.upload_to_zenodo(
            file_path + ".parquet",
            data_type="actual",
            made_by_oet=made_by_oet,
            publish=publish_to_zenodo,
            testing=True,
        )
    elif upload_to_zenodo and not retrieval_module.redistribute():
        logging.warning(
            f"The data source {data_source} does not support redistribution "
            "to Zenodo. The data will not be uploaded to Zenodo."
        )


def run_data_retrieval(
    data_source: str,
    code: str | None,
    file: str | None,
    upload_to_gcs: str | None,
    upload_to_zenodo: bool,
    publish_to_zenodo: bool,
    made_by_oet: bool,
) -> None:
    """
    Run the electricity demand data retrieval.

    This function runs the electricity demand data retrieval
    process. It retrieves the electricity demand time series for the
    specified countries and subdivisions from the data source, cleans
    the data, and saves it.

    Parameters
    ----------
    data_source : str
        The data source from which to retrieve the electricity demand
        time series.
    code : str | None
        The code of the country or subdivision.
    file : str | None
        The path to the yaml file containing the list of codes of the
        countries and subdivisions of interest.
    upload_to_gcs : str | None
        The bucket name of the Google Cloud Storage (GCS) to upload the
        data.
    upload_to_zenodo : bool
        Whether to upload the data to Zenodo.
    publish_to_zenodo : bool
        Whether to publish the data to Zenodo.
    made_by_oet : bool
        Whether the data was made by Open Energy Transition.
    """
    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with_demand_data(
        code, data_source, file
    )

    logging.info(
        f"Retrieving electricity data from the {data_source} website."
    )

    # Loop over the codes.
    for code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving electricity data for {code}.")

        # Retrieve the electricity demand time series.
        electricity_demand_time_series = _retrieve_data(data_source, code)

        # Save the electricity demand time series to a file and upload
        # it to GCS.
        _save_data(
            electricity_demand_time_series,
            code,
            data_source,
            upload_to_gcs,
            upload_to_zenodo,
            publish_to_zenodo,
            made_by_oet,
        )

    logging.info(
        f"Electricity data from the {data_source} website has been "
        "successfully retrieved and saved."
    )

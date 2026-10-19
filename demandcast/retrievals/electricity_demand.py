"""
License: AGPL-3.0.

Description:

    This module includes functions to download hourly or sub-hourly
    electricity demand data from various data sources. The retrieved
    data is processed to MW, at the ends of the intervals in UTC,
    without missing or zero values or duplicated times, and saved in
    the folder of processed electricity demand. It is then cleaned and
    saved in the folder of cleaned electricity demand, which the
    assembly of the data reads.
"""

import importlib
import logging
import os

import cleaning.electricity_demand
import pandas as pd
import utils.config
import utils.entities
import utils.fetcher
import utils.time_series
from tqdm import tqdm


def _retrieve_data(data_source: str, code: str) -> pd.Series | None:
    """
    Retrieve the electricity demand data.

    This function retrieves the electricity demand time series from the
    specified data source. If the data of the latest of several requests
    is not found, it is skipped, because the file of the latest period
    can be not published yet.

    Parameters
    ----------
    data_source : str
        The data source.
    code : str
        The code of the country or subdivision.

    Returns
    -------
    electricity_demand_time_series : pandas.Series | None
        The electricity demand time series in MW, or None if no request
        has data.

    Raises
    ------
    TypeError
        If the values of the time series are not numbers.
    utils.fetcher.DataNotFoundError
        If the data of an earlier request, or of the only one, is not
        found.
    """
    # Import the retrieval module for the data source.
    retrieval_module = importlib.import_module(
        f"retrievals.electricity_demand_data_sources.{data_source}"
    )

    # Get the requests for the dates of the entity in the yaml file of
    # the data source, and download each of them with the code.
    start_date, end_date = (
        utils.entities.read_date_ranges_of_electricity_demand_in_data_source(
            data_source
        )[code]
    )
    requests = retrieval_module.get_available_requests(
        code, start_date, end_date
    )
    electricity_demand_time_series_list = []
    for index, request in enumerate(requests):
        try:
            electricity_demand_time_series_list.append(
                retrieval_module.download_and_extract_data_for_request(
                    request, code
                )
            )
        except utils.fetcher.DataNotFoundError:
            # The file of the latest period can be not published yet.
            if index < len(requests) - 1 or len(requests) == 1:
                raise
            logging.warning(
                f"The data of the latest request ({request}) of "
                f"{data_source} is not found, maybe not published yet."
            )

    # Concatenate the electricity demand time series of the requests
    # with data.
    electricity_demand_time_series_list = [
        time_series
        for time_series in electricity_demand_time_series_list
        if not time_series.empty
    ]
    if not electricity_demand_time_series_list:
        return None
    electricity_demand_time_series = pd.concat(
        electricity_demand_time_series_list
    )

    # Check that the values are numbers, so that the data of a source
    # that returns text are not saved as text.
    if not pd.api.types.is_numeric_dtype(electricity_demand_time_series):
        raise TypeError(
            f"The data source {data_source} returned values of type "
            f"{electricity_demand_time_series.dtype}, not numbers."
        )

    # Clean the data.
    electricity_demand_time_series = utils.time_series.clean_data(
        electricity_demand_time_series, "Load (MW)"
    )

    return electricity_demand_time_series


def _save_data(
    electricity_demand_time_series: pd.Series,
    code: str,
    data_source: str,
) -> None:
    """
    Save the processed electricity demand time series.

    This function saves the electricity demand time series, processed
    to MW and UTC at the resolution of the data source, to a parquet
    file named after the code and the data source in the folder of
    processed electricity demand, which replaces the file of an earlier
    retrieval.

    Parameters
    ----------
    electricity_demand_time_series : pandas.Series
        The electricity demand time series in MW.
    code : str
        The code of the country or subdivision.
    data_source : str
        The data source.
    """
    file_path = utils.config.get_electricity_demand_file_path(
        "processed", code, data_source
    )
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    electricity_demand_time_series.to_frame().to_parquet(file_path)


def run_data_retrieval(
    data_source: str,
    code: str | None,
    file: str | None,
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
    """
    # Get the list of codes of the countries and subdivisions of
    # interest.
    codes = utils.entities.check_and_get_codes_with(
        "electricity_demand_data",
        code=code,
        data_source=data_source,
        file_path=file,
    )

    logging.info(
        f"Retrieving electricity data from the {data_source} website."
    )

    # Loop over the codes.
    for entity_code in tqdm(codes, desc="Countries and subdivisions"):
        logging.info(f"Retrieving electricity data for {entity_code}.")

        # Retrieve the electricity demand time series, and go on with
        # the next country or subdivision if there is none.
        electricity_demand_time_series = _retrieve_data(
            data_source, entity_code
        )
        if electricity_demand_time_series is None:
            logging.warning(
                f"The data source {data_source} has no data for "
                f"{entity_code}, which is not saved."
            )
            continue

        # Save the processed electricity demand time series, and clean
        # it.
        _save_data(
            electricity_demand_time_series,
            entity_code,
            data_source,
        )
        cleaning.electricity_demand.clean_data(entity_code, data_source)

    logging.info(
        f"Electricity data from the {data_source} website has been "
        "successfully retrieved and saved."
    )
